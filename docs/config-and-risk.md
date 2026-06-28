# Configuration & Risk Specification

> Closes the "risk settings open" gap. **All risk limits are configurable** at runtime
> (config file + dashboard view), each expressible as an **absolute ₹ amount OR a % of
> configured trading capital**, with safe defaults. Defaults give tests concrete assertions.

---

## 1. Trading Capital Reference
A single configured figure drives all percentage-based limits:
```yaml
trading_capital: 100000        # ₹ — basis for any percent-based limit below
```
Percentage limits are computed against this value at the **start of each trading day**.

---

## 2. Risk Config Schema (`config/risk.yml`)

Every limit accepts either `{ amount: <₹> }` **or** `{ percent: <%> }`. Defaults shown.

```yaml
# --- Daily loss kill-switch (realized + unrealized) ---
daily_loss:
  enabled: true
  percent: 2.0            # OR  amount: 2000
  action: square_off_and_halt    # exit all + stop trading for the day

# --- Forced end-of-day square-off (hard, overrides strategy) ---
forced_square_off:
  enabled: true
  time: "15:15"          # IST, customizable; must be < broker auto-squareoff (~15:20)

# --- Max trades per day (round-trip entries) ---
max_trades_per_day:
  enabled: true
  count: 10              # customizable; once hit, no NEW entries (open trade still managed)

# --- Per-trade sizing cap (backstop over strategy-requested size) ---
per_trade_cap:
  enabled: true
  mode: capital          # capital | quantity | percent
  amount: 50000          # ₹ notional per trade  (mode: capital)
  # quantity: 200        #        (mode: quantity)
  # percent: 25.0        # % of trading_capital  (mode: percent)
  on_breach: clamp       # clamp = reduce qty to fit  |  reject = drop the order

# --- Optional execution-realism knobs (paper/backtest) ---
fills:
  slippage_bps: 3
  fill_delay_ticks: 1
  full_fill: true
  participation_pct: null   # set to model thin liquidity
  require_trade_through: false
```

### Resolution rules
- If both `amount` and `percent` are set on a limit, **`amount` wins** (explicit ₹ overrides).
- Disabling a limit (`enabled: false`) is allowed but logged loudly at startup.
- Invalid config (negative, percent > 100, square-off ≥ broker cutoff) → **engine refuses to
  start** with a clear error.

---

## 3. Enforcement Order (per tick)
Engine backstops run **after** strategy logic and **win** over it:
1. Strategy `entry`/`on_tick`/`exit` run first (strategy owns normal exits).
2. **`per_trade_cap`** clamps/rejects any order the strategy emits.
3. **`max_trades_per_day`** blocks new entries once reached.
4. **`daily_loss`** kill-switch — if breached, square off + halt for the day.
5. **`forced_square_off`** — at the configured time, exit everything regardless of strategy.

Any backstop firing emits a Telegram alert + `events` row.

---

## 4. Default Values (for tests & first run)
| Setting | Default |
|---------|---------|
| `daily_loss` | 2% of capital, square-off + halt |
| `forced_square_off` | 15:15 IST |
| `max_trades_per_day` | 10 |
| `per_trade_cap` | ₹50,000 notional, clamp on breach |
| `slippage_bps` | 3 |
| `fill_delay_ticks` | 1 |

> These are **starting defaults**, deliberately conservative for paper/early-live; tune in
> `config/risk.yml` (no code changes). The dashboard shows the active values (read-only — risk
> config changes go through the file, consistent with the "monitor + kill-switch" control scope).

---

## 5. Tick Archive Retention
Recorded ticks (FR-11) grow unbounded; configure rotation:
```yaml
tick_archive:
  enabled: true
  retain_days: 90        # prune older raw ticks
  instruments: traded    # traded = only symbols actually run; or an explicit list
```
When archive write volume becomes the bottleneck, that is the signal to migrate the `ticks`
table to Postgres/TimescaleDB (the DAL isolates this change).
