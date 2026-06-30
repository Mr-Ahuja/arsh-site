# Backtest Runner

The Backtest page lets you test a strategy on historical market data before risking real money.

---

## Before you run a backtest

You need:
1. **Kite connected** — historical data is fetched from Zerodha's Historical Data API. Log in to Kite from the top bar first.
2. **The instrument token** — a number that identifies the stock or index you want to test on. Find it in the Zerodha instruments CSV (available from the Kite API instruments endpoint) or look it up in the Kite Connect documentation.

---

## Running a backtest

Fill in the form on the left:

| Field | What to enter |
|---|---|
| **Strategy** | Choose from the strategies available in your `strategies/` folder |
| **Instrument token** | The numeric token for the instrument (e.g. 256265 for NIFTY 50) |
| **Timeframe** | Candle size: 1 min, 5 min, 15 min, etc. Must match what your strategy expects |
| **From / To** | Date range. Kite provides up to 400 days of minute-level historical data |
| **Param overrides** | JSON to override strategy defaults — e.g. `{"qty": 10, "fast_period": 9}` |

Click **Run Backtest**. The job is submitted and runs in the background. You'll see a spinning indicator in the results panel while it runs.

---

## Results

When the backtest finishes, the results panel shows:

- **Metrics strip** — same 9 tiles as the Analytics page (total P&L, win rate, profit factor, max drawdown, etc.) but for this backtest run only
- **Equity curve** — cumulative P&L through every trade in the backtest

If the backtest fails (e.g. Kite not connected, bad date range, strategy error), the row turns red and shows the error message.

---

## Past backtests

All previous backtests are listed on the left below the form. Click any row to load its results on the right. The list auto-refreshes every 5 seconds to pick up status changes on running jobs.

---

## Comparing backtest vs paper vs live

After running a backtest, go to the **Analytics** page and use the **Run #N** selector to pick the backtest run. You can then compare its metrics directly against a paper or live run of the same strategy — both share the same metrics format.

---

## Limitations

- Kite's Historical Data API is rate-limited and has a data lookback limit (~400 days for minute candles, ~2000 days for day candles).
- Backtests use OHLC data — they fill at the next candle's open price with a small slippage. Real tick-by-tick behaviour may differ, especially for intraday gaps.
- Only one strategy and one instrument per backtest run (same as the live engine).
