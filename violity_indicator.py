import logging
import os
import numpy as np
from decimal import Decimal
from typing import Dict, List

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel, ClientFieldData
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class EnhancedPMMConfig(BaseClientModel):
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))
    exchange: str = Field("binance_paper_trade", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Exchange where the bot will trade"))
    trading_pair: str = Field("ETH-USDT", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Trading pair in which the bot will place orders"))
    order_amount: Decimal = Field(0.01, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Order amount (denominated in base asset)"))
    bid_spread: Decimal = Field(0.001, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Bid order spread (in percent)"))
    ask_spread: Decimal = Field(0.001, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Ask order spread (in percent)"))
    order_refresh_time: int = Field(15, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Order refresh time (in seconds)"))
    price_type: str = Field("mid", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Price type to use (mid or last)"))
    max_inventory_pct: Decimal = Field(0.5, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Maximum inventory percentage (0-1)"))
    atr_period: int = Field(14, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "ATR period for volatility"))
    volatility_multiplier: Decimal = Field(2.0, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Volatility spread multiplier"))


class EnhancedPMM(ScriptStrategyBase):
    """
    Enhanced PMM with basic inventory management and volatility adjustment (ATR)
    """

    create_timestamp = 0
    price_source = PriceType.MidPrice

    @classmethod
    def init_markets(cls, config: EnhancedPMMConfig):
        cls.markets = {config.exchange: {config.trading_pair}}
        cls.price_source = PriceType.LastTrade if config.price_type == "last" else PriceType.MidPrice

    def __init__(self, connectors: Dict[str, ConnectorBase], config: EnhancedPMMConfig):
        super().__init__(connectors)
        self.config = config
        self.base_asset = self.config.trading_pair.split("-")[0]
        self.quote_asset = self.config.trading_pair.split("-")[1]

    def on_tick(self):
        if self.create_timestamp <= self.current_timestamp:
            self.cancel_all_orders()
            proposal: List[OrderCandidate] = self.create_proposal()
            proposal_adjusted: List[OrderCandidate] = self.adjust_proposal_to_budget(proposal)
            self.place_orders(proposal_adjusted)
            self.create_timestamp = self.config.order_refresh_time + self.current_timestamp

    def calculate_atr(self):
        """Calculate Average True Range"""
        connector = self.connectors[self.config.exchange]
        history = connector.get_trading_pairs_historical_prices(
            trading_pair=self.config.trading_pair,
            period="1m",
            number_of_rows=self.config.atr_period + 1
        )
        
        if len(history) < self.config.atr_period + 1:
            return Decimal("0")

        true_ranges = []
        for i in range(1, len(history)):
            high = float(history[i].high)
            low = float(history[i].low)
            prev_close = float(history[i-1].close)
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(tr)
        
        return Decimal(str(np.mean(true_ranges[-self.config.atr_period:]))) if true_ranges else Decimal("0")

    def create_proposal(self) -> List[OrderCandidate]:
        connector = self.connectors[self.config.exchange]
        ref_price = connector.get_price_by_type(self.config.trading_pair, self.price_source)
        

        atr = self.calculate_atr()
        volatility_spread = (atr / ref_price) * self.config.volatility_multiplier
        bid_spread = max(self.config.bid_spread + volatility_spread, Decimal("0.001"))
        ask_spread = max(self.config.ask_spread + volatility_spread, Decimal("0.001"))
        
        buy_price = ref_price * (Decimal("1") - bid_spread)
        sell_price = ref_price * (Decimal("1") + ask_spread)

        
        base_balance = connector.get_available_balance(self.base_asset)
        quote_balance = connector.get_available_balance(self.quote_asset)
        total_value = base_balance * ref_price + quote_balance
        current_base_value = base_balance * ref_price
        inventory_pct = current_base_value / total_value if total_value > Decimal("0") else Decimal("0.5")
        max_pct = self.config.max_inventory_pct
        
        if inventory_pct > max_pct:
            buy_amount = self.config.order_amount * (Decimal("1") - ((inventory_pct - max_pct) * Decimal("2")))
            buy_amount = max(buy_amount, Decimal("0.001"))
            sell_amount = self.config.order_amount
        elif inventory_pct < (Decimal("1") - max_pct):
            sell_amount = self.config.order_amount * (Decimal("1") - ((Decimal("1") - max_pct - inventory_pct) * Decimal("2")))
            sell_amount = max(sell_amount, Decimal("0.001"))
            buy_amount = self.config.order_amount
        else:
            buy_amount = self.config.order_amount
            sell_amount = self.config.order_amount

        self.log_with_clock(logging.INFO, 
            f"Volatility Spread: {volatility_spread:.4%}, "
            f"Bid/Ask Spreads: {bid_spread:.4%}/{ask_spread:.4%}, "
            f"Inventory: {inventory_pct:.2%}"
        )

        return [
            OrderCandidate(
                trading_pair=self.config.trading_pair,
                is_maker=True,
                order_type=OrderType.LIMIT,
                order_side=TradeType.BUY,
                amount=buy_amount,
                price=buy_price
            ),
            OrderCandidate(
                trading_pair=self.config.trading_pair,
                is_maker=True,
                order_type=OrderType.LIMIT,
                order_side=TradeType.SELL,
                amount=sell_amount,
                price=sell_price
            )
        ]

    def adjust_proposal_to_budget(self, proposal: List[OrderCandidate]) -> List[OrderCandidate]:
        return self.connectors[self.config.exchange].budget_checker.adjust_candidates(proposal, all_or_none=True)

    def place_orders(self, proposal: List[OrderCandidate]) -> None:
        for order in proposal:
            self.place_order(connector_name=self.config.exchange, order=order)

    def place_order(self, connector_name: str, order: OrderCandidate):
        if order.order_side == TradeType.SELL:
            self.sell(
                connector_name=connector_name,
                trading_pair=order.trading_pair,
                amount=order.amount,
                order_type=order.order_type,
                price=order.price
            )
        elif order.order_side == TradeType.BUY:
            self.buy(
                connector_name=connector_name,
                trading_pair=order.trading_pair,
                amount=order.amount,
                order_type=order.order_type,
                price=order.price
            )

    def cancel_all_orders(self):
        for order in self.get_active_orders(self.config.exchange):
            self.cancel(self.config.exchange, order.trading_pair, order.client_order_id)

    def did_fill_order(self, event: OrderFilledEvent):
        msg = (f"{event.trade_type.name} {round(event.amount, 2)} {event.trading_pair} "
               f"at {round(event.price, 2)}")
        self.log_with_clock(logging.INFO, msg)
        self.notify_hb_app_with_timestamp(msg)
