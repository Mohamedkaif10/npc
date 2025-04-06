# Advanced Pure Market Making (PMM) Strategy - Hummingbot Custom Script

This repository implements an **enhanced Pure Market Making (PMM)** strategy using the Hummingbot framework. It is designed to **optimize spread capturing** while managing inventory, detecting market trends, and implementing robust risk control mechanisms like stop-loss and exposure limits.

---

## 🔍 Strategy Overview

This bot places buy and sell orders around a reference price (mid-price or last traded price). It periodically refreshes orders based on:

- **Inventory Position** — To avoid accumulating too much of one asset.
- **Market Trend** — To shift quotes according to bullish or bearish sentiment.
- **Volatility & Risk** — To avoid trading in high-risk or unfavorable conditions.

---

## ⚙️ Features

### ✅ Inventory Management

- Dynamically adjusts order sizes based on your current portfolio.
- Avoids over-exposure with:
  - `max_inventory_pct`: e.g., 50% base, 50% quote.
  - `max_inventory`: Absolute cap on base asset holdings.

### 📈 Trend Analysis *(Simulated due to Paper Trading)*

In a live environment, this strategy would dynamically adjust its quoting behavior based on **Simple Moving Average (SMA)** to capture short-term market momentum:

- If current price > SMA → Reduces **buy** order sizes (uptrend).
- If current price < SMA → Reduces **sell** order sizes (downtrend).

However, since this bot is currently running on the **paper trading exchange**, real-time candle data (required for SMA computation) is not available.

- Thus, **SMA-based adjustments are conceptually included but not active**.
- This showcases how the strategy can be extended for production deployment on real exchanges (e.g., Binance, KuCoin).

### 📊 Volatility-Aware Spreads (ATR Integration)

- Calculates **Average True Range (ATR)** to measure volatility.
- Dynamically widens spreads in high volatility scenarios to reduce risk.
- Formula:

```python
volatility_spread = (atr / price) * volatility_multiplier
