# Writing Strategies

A strategy is a small Python file that decides **when to enter a trade, and when to get
out**. The engine handles everything else — market data, orders, risk limits, the 15:15
square-off, and recording every trade.

You can write strategies right here in the browser from the **Strategies** page — no server
access needed. Save a file and it's instantly available in the Backtest dropdown.

---

## What this unlocks

- Turn a trading idea into something you can **backtest on real historical data** and, when
  you're confident, run live.
- Iterate quickly: edit, validate, save, backtest — all from the dashboard.
- Keep multiple strategies side by side and compare their results on the Analytics page.

---

## The three decisions every strategy makes

Your strategy reacts to a stream of price updates ("ticks"). On each update the engine asks
your code up to three questions:

| Hook | When it's called | What you return |
|---|---|---|
| `entry(tick)` | While you hold **no** position | An order to open a trade, or nothing |
| `on_tick(tick, pos)` | While a trade is **open** | Nothing — just update your notes on the trade |
| `exit(tick, pos)` | While a trade is **open** | `True` to close now, `False` to hold |

There are two optional hooks too: `on_start()` (runs once, before any prices — set things up
here) and `on_stop()` (runs once at shutdown).

---

## A minimal example

```python
from engine.data.types import TickData
from engine.strategy import BaseStrategy, Position, StrategyOrder

class Strategy(BaseStrategy):
    instrument = "NSE:SBIN"       # what to trade
    timeframe  = "5minute"        # candle size for indicators
    params     = {"qty": 10}      # your tunable settings

    def entry(self, tick: TickData) -> StrategyOrder | None:
        # Buy 10 shares as soon as we're flat.
        return self.buy(qty=self.params["qty"])

    def on_tick(self, tick: TickData, pos: Position) -> None:
        # Remember the highest price we've seen this trade.
        pos.vars["peak"] = max(pos.vars.get("peak", tick.ltp), tick.ltp)

    def exit(self, tick: TickData, pos: Position) -> bool:
        # Exit if we fall 1% below that peak (a trailing stop).
        return tick.ltp <= pos.vars.get("peak", 0.0) * 0.99
```

**What you can read off each `tick`:** `tick.ltp` (last price) and `tick.ts` (timestamp).
**What you can read off `pos` (the open trade):** `pos.entry_price`, `pos.ltp` (current
price), `pos.qty`, `pos.side` (`"LONG"`/`"SHORT"`), and `pos.pnl` (live profit in ₹).

**`pos.vars` is your scratchpad** — a place to remember things across ticks for the current
trade (like the running peak above). It's saved automatically, so it survives a restart.

---

## Settings you can tune (`params`)

Anything you put in `params` can be overridden per-run from the Backtest form without
editing code — so you can sweep values like quantity, thresholds, or periods. Add a
`param_schema` to have the engine reject bad values before a run starts:

```python
params = {"qty": 10, "stop_pct": 0.01}
param_schema = {
    "qty":      {"type": int,   "min": 1},
    "stop_pct": {"type": float, "min": 0.001, "max": 0.1},
}
```

---

## Built-in indicators

Register indicators in `on_start()`; the engine feeds them for you. Read `.value` (it's
`None` until it has enough data to warm up).

| Indicator | Example | Measures |
|---|---|---|
| `EMA` | `self.indicator(EMA, 20)` | Exponential moving average |
| `SMA` | `self.indicator(SMA, 50)` | Simple moving average |
| `RSI` | `self.indicator(RSI, 14)` | Momentum, 0–100 |
| `ATR` | `self.indicator(ATR, 14)` | Volatility (average range) |
| `VWAP` | `self.indicator(VWAP)` | Volume-weighted average price |

```python
from engine.strategy import EMA

def on_start(self):
    self.ema = self.indicator(EMA, 20)

def entry(self, tick):
    if self.ema.value and tick.ltp > self.ema.value:
        return self.buy(qty=self.params["qty"])
```

---

## Helpers for opening-based strategies

If your idea keys off the market open, the engine gives you:

- `self.day_open` — the first price seen this session.
- `self.first_tick_of_session` — `True` only on the very first update of a new trading day.
- `self.minutes_since_open(tick)` — minutes since 09:15 IST.
- `self.now_ist()` — the current time in IST.

The bundled **Open-Drive** strategy (`open_drive.Long` / `open_drive.Short`) uses these to
enter at the open, hold a fixed 1% stop, then switch to a ratcheting 0.2% trailing stop once
the trade runs 1% in profit. Open it in the editor as a worked example.

---

## Using the editor

1. **New** — start from a template. Pick a filename like `my_idea.py`.
2. **Validate** — checks your code compiles and finds your strategy class. Errors (with line
   numbers) show below the editor.
3. **Save** — writes the file. It appears in the Backtest dropdown immediately, and the next
   backtest or run uses your latest code.
4. **Delete** — removes a file (blocked if that strategy is currently running).

> **Tip:** Always **Backtest** a new strategy before running it live. Backtests replay
> historical candles, so stops are checked at each candle's close — intraday spikes between
> candles aren't seen, and results are an approximation, not a guarantee.

---

## Good habits

- Keep the hooks **fast** — they run on every tick. Avoid heavy loops or network calls.
- Never `print()` — use `self.log("message", key=value)` so it shows in the activity feed.
- Only write to `pos.vars`; treat everything else on `pos` and `tick` as read-only.
- Start with paper/backtest, small quantity, and one instrument.
