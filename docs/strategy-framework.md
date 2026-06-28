# Strategy Framework — Contract Specification

> The heart of the product: how the user writes algorithms.
> Style locked: **class-based with declarative returns** + **mutable per-trade state**.

---

## 1. Design Principles
1. **You write Python, the engine runs it.** Drop a file in `strategies/`, subclass
   `BaseStrategy`, implement hooks. No engine edits needed.
2. **Strategy owns its exits.** Profit/loss/trailing logic lives in your `on_tick`/`exit`.
   The engine only adds *backstops* (forced square-off, daily-loss kill-switch).
3. **Mutable per-trade state (`pos.vars`).** Create and update arbitrary variables per
   trade, live, every tick.
4. **Mode-agnostic.** Identical code runs in backtest, paper, and live — only the broker
   and data source are swapped underneath.

---

## 2. Lifecycle Hooks

| Hook | When it runs | Returns / Effect |
|------|--------------|------------------|
| `on_start(self)` | Once, before any ticks | Set up indicators, warm-up, custom state |
| `entry(self, tick)` | Every tick **while flat** | Return an `Order` (`self.buy/self.sell`) to enter, or `None` |
| `on_tick(self, tick, pos)` | Every tick **while in a trade** | Mutate `pos.vars`; no return needed |
| `exit(self, tick, pos)` | Every tick **while in a trade** | Return `True` to square off, else `False` |
| `on_order_update(self, order)` | On fill/reject/cancel (optional) | React to execution events |
| `on_stop(self)` | Once, at shutdown/square-off | Cleanup, logging |

> v1 runs **one instrument, one open position at a time**. `entry` is only polled when flat;
> `on_tick`/`exit` only while a position is open.

---

## 3. The `tick` Object (read-only)
```
tick.ltp            # last traded price
tick.volume         # cumulative volume
tick.bid / tick.ask # best bid/ask (when available)
tick.timestamp      # exchange/engine timestamp
tick.ohlc           # day OHLC snapshot from Kite
```

## 4. The `pos` / Position Object
```
pos.side            # "LONG" / "SHORT"
pos.qty             # quantity held
pos.entry_price     # average entry
pos.ltp             # current price
pos.pnl             # live P&L (₹) incl. unrealized
pos.entry_time      # when the trade opened
pos.vars            # ← mutable dict for YOUR custom state (persisted)
pos.vars.get(k, d)  # safe read
pos.vars[k] = v     # create/update live
```

## 5. Order Helpers (from `BaseStrategy`)
```python
self.buy(qty, type="MARKET", price=None)    # MARKET default; LIMIT needs price
self.sell(qty, type="MARKET", price=None)
self.square_off(reason="...")               # exit current position now
```
- Default product is **MIS** (intraday). Orders are validated against engine risk caps
  before reaching the broker.

## 6. Indicators (built-in, engine-fed)
**One model: indicators you register in `on_start` are fed automatically by the engine.**
You never call `.update()` yourself — you only **read** `.value`. This guarantees identical
behaviour across backtest / paper / live (see [execution-spec.md](execution-spec.md) §6).

```python
def on_start(self):
    self.ema = self.indicator(EMA, 20)          # registered → engine feeds it
    self.rsi = self.indicator(RSI, 14, feed="candle")  # default feed = candle close

def entry(self, tick):
    if self.ema.value and tick.ltp > self.ema.value:   # just READ .value
        return self.buy(qty=self.params["qty"])
```

- `feed="candle"` (**default**) — updates on each closed candle of the strategy `timeframe`.
  Reproducible in every mode, including OHLC backtest.
- `feed="tick"` (opt-in) — updates every tick. Faithful in tick-replay/paper/live; **degrades
  to candle-close in OHLC backtest** (run is flagged). Use only when sub-candle reaction matters.
- Registry: `EMA, SMA, RSI, VWAP, ATR, …` — extensible.
- For fully custom math, read `self.candles(n)` / `self.buffer.ticks(n)` and compute inline.

## 7. Data Access Helpers
```python
self.candles(n=50)              # last N OHLC candles (timeframe)
self.history(from_, to_)        # historical OHLC (Kite Historical API)
self.buffer.ticks(n=200)        # rolling recent tick window
self.log(msg, level="info")     # structured log → DB + dashboard
```

## 8. Configuration
- `instrument` — e.g. `"NSE:SBIN"` (mapped to Kite instrument token at load).
- `timeframe` — candle interval (`"minute"`, `"5minute"`, …).
- `params` — dict of tunables; overridable per run (UI/CLI) without editing code.

## 9. Full Example — EMA breakout with trailing cutoff
```python
class Strategy(BaseStrategy):
    instrument = "NSE:SBIN"
    timeframe  = "5minute"
    params     = {"qty": 10, "trail_pct": 0.99}

    def on_start(self):
        self.ema = self.indicator(EMA, 20)      # engine feeds it; you only read .value

    def entry(self, tick):
        if self.ema.value and tick.ltp > self.ema.value:
            return self.buy(qty=self.params["qty"])

    def on_tick(self, tick, pos):
        pos.vars["peak"]   = max(pos.vars.get("peak", tick.ltp), tick.ltp)
        pos.vars["cutoff"] = pos.vars["peak"] * self.params["trail_pct"]

    def exit(self, tick, pos):
        return tick.ltp <= pos.vars.get("cutoff", 0)
```

## 10. Guarantees & Constraints
- `pos.vars` is **persisted** each update → survives an engine restart mid-trade.
- Engine **backstops always win**: forced square-off time and daily-loss kill-switch
  fire even if `exit()` never returns `True`.
- Exceptions inside a hook are caught → trade is protected (halt + alert), never silently dropped.
- Same hooks, same `pos.vars`, same indicators in **backtest / paper / live**.

---

## 11. Strict Contract — Types, Limits & Trust

### Hook signatures & return types (enforced)
| Hook | Signature | Must return |
|------|-----------|-------------|
| `on_start` | `(self) -> None` | nothing |
| `entry` | `(self, tick: Tick) -> Order \| None` | an `Order` (from `self.buy/self.sell`) or `None` |
| `on_tick` | `(self, tick: Tick, pos: Position) -> None` | nothing (mutate `pos.vars`) |
| `exit` | `(self, tick: Tick, pos: Position) -> bool` | `True` to square off, else `False` |
| `on_order_update` | `(self, order: Order) -> None` | nothing |
| `on_stop` | `(self) -> None` | nothing |

`Tick`, `Position`, `Order` are typed dataclasses (see [execution-spec.md](execution-spec.md) §1).
A wrong return type is treated as a strategy error → fail-safe halt.

### Parameter validation
- Optional `param_schema` declares types/ranges; `params` are validated **at load**.
  Invalid params → the strategy **fails to load** (never runs with bad config).
```python
param_schema = {"qty": {"type": int, "min": 1}, "trail_pct": {"type": float, "min": 0.5, "max": 1.0}}
```

### Exceptions = fail-safe, never ignored
Any exception raised in a hook → engine **protects the position** (square off if open),
**halts** new entries, logs to `events`, and sends a Telegram alert. Strategies must not rely
on exceptions for control flow.

### Timeout / hot-path limits (single-threaded loop)
- Each hook should return within **50 ms (soft)**; **200 ms (hard)** overrun is logged; repeated
  hard overruns **halt** the strategy (a slow hook blocks tick processing).
- **No blocking I/O in hooks**: no network calls, file reads, `sleep`, or heavy CPU. Use the
  provided data helpers and `self.log()` (async, off the hot path). Do all warm-up in `on_start`.

### Side effects
- Strategies interact with the world **only** through `self.buy/sell/square_off` and `self.log`.
  Direct broker/DB/network access from a strategy is unsupported and unsafe.

### Trust model (v1)
- Strategies are **your own, trusted code** (single user). They are loaded from the local
  `strategies/` folder via `importlib` — there is **no hostile sandbox**, and none is needed
  for v1. Do **not** load third-party/untrusted strategy files. (A capability sandbox would be a
  prerequisite if this ever becomes multi-user.)
