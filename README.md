# Advanced Pure Market Making (PMM) Strategy - Hummingbot Custom Script

This repository implements an **enhanced Pure Market Making (PMM)** strategy using the Hummingbot framework. It is designed to **optimize spread capturing** while managing inventory, detecting market trends, and risk control mechanisms like stop-loss and exposure limits.

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

### 📈 Trend Analysis
- Uses **Simple Moving Average (SMA)** over configurable `sma_period`.
- If current price > SMA, the bot reduces **buy** order sizes.
- If current price < SMA, it reduces **sell** order sizes.
- Smoothly tracks short-term momentum while maintaining market presence.

### 🔐 Risk Management
- `stop_loss_pct`: Cancels all orders and halts trading when triggered.
- `max_inventory`: Stops placing new buy orders when base holdings exceed threshold.

---

## 🧠 Key Concepts

### 💡 Inventory Skew Logic

```python
if inventory_pct > max_inventory_pct:
    # Reduce buy orders
elif inventory_pct < (1 - max_inventory_pct):
    # Reduce sell orders

trend_factor = (current_price - sma) / sma
# Reduces buy orders in uptrend, reduces sell orders in downtrend
 
price_change = (current_price - last_price) / last_price
if price_change < -stop_loss_pct:
    # Stop trading