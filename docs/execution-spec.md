# Execution & Data Specification

> Closes the fill-model, order-lifecycle, restart-recovery, and backtest-data-quality gaps.
> Companion to [architecture.md](architecture.md) §3 and [requirements.md](requirements.md).

This is the contract for the three `Broker` implementations (Paper, Backtest, Live) and the
data layer that feeds them. All three sit behind one interface so strategy code is unchanged.

---

## 1. Order Model (common to all modes)

Every order created by a strategy gets a **client-side `order_ref` (UUID4)** assigned and
persisted **before** it is sent anywhere. This is the idempotency key used for dedup,
retries, and reconciliation.

```
Order(order_ref, symbol, side, qty, type=MARKET|LIMIT, price?, product=MIS,
      state, broker_order_id?, filled_qty, avg_fill_price, reason, ts_*)
```

### Order state machine (all modes)
```
CREATED ─▶ PENDING ─▶ OPEN ─┬─▶ COMPLETE
                            ├─▶ PARTIAL ─▶ COMPLETE | CANCELLED
                            ├─▶ REJECTED
                            └─▶ CANCELLED
```
- `CREATED` persisted with `order_ref` before transmission (crash-safe).
- Transitions are driven by broker order updates (live) or the simulator (paper/backtest).
- **One in-flight order per position transition.** The engine will not emit a second entry/exit
  order while one is `PENDING`/`OPEN` for the same transition (duplicate prevention).

---

## 2. Paper Fill Model (live ticks, simulated)

Runs on the **live Kite Ticker** stream; we simulate fills. Defaults are **pessimistic**
(favor realism over flattering backtests). All parameters are configurable (see config-and-risk.md).

| Aspect | Rule (default) |
|--------|----------------|
| **MARKET fill price** | Cross the spread: BUY at best ask, SELL at best bid. If depth unavailable, `LTP ± slippage` where slippage = `max(1 tick, slippage_bps·LTP)` (default 3 bps). |
| **MARKET fill timing** | Filled on the **next tick** after the signal (models reaction latency); configurable `fill_delay_ticks` (default 1). |
| **LIMIT fill** | Fills only when a tick **trades at/through** the limit: BUY when `tick.ltp ≤ limit`, SELL when `tick.ltp ≥ limit`. Optional `require_trade_through` for stricter fills. |
| **Partial fills** | Default **full fill** (retail single-instrument size). Optional volume-participation cap: fill ≤ `participation_pct` of the tick's traded volume, remainder stays OPEN. |
| **Rejections** | Simulated when: order violates a risk cap, price is outside the **circuit band**, or instrument shows zero liquidity. Rejected orders alert + are logged. |
| **Circuit limits** | Orders priced beyond the day's upper/lower circuit are rejected; no fills occur while LTP is locked at a circuit. |
| **Liquidity** | Default assumes sufficient depth; the participation cap above models thin instruments when enabled. |
| **Gaps** | Natural — paper consumes real live ticks, so opening gaps/halts appear as they happen. |

---

### 2a. Data sources for circuit-limit & liquidity simulation
These rules need concrete inputs. Sources (all from Kite, so paper == live):

| Input | Source | Notes |
|-------|--------|-------|
| **Circuit band** (upper/lower) | Kite **`quote()` REST** fields `upper_circuit_limit` / `lower_circuit_limit` | Fetched once at strategy start and cached for the day (KiteTicker does not carry it reliably). |
| **Best bid/ask + spread** | **KiteTicker "full" mode** market depth (5 levels) | Subscribe in *full* mode (not *ltp*/*quote*) so depth is present. |
| **Depth / liquidity** | KiteTicker full-mode depth quantities | Empty/zero depth ⇒ treated as no liquidity. |
| **Tick volume** (participation) | Tick `last_traded_quantity` / `volume_traded` | Drives the optional participation cap. |

**Per-mode availability (rules auto-disable when their data is absent — and the run is flagged):**
- **Paper (live full-mode ticks):** depth + circuit band available → all rules active.
- **Backtest tick-replay:** active **only if** the tick archive recorded full-mode **depth** and the
  day's **circuit band**. Therefore the archiver (FR-11) must persist depth snapshots + the cached
  circuit band; otherwise depth/circuit rejection is disabled for that replay.
- **Backtest OHLC:** no depth, no circuit band in historical OHLC → **circuit & liquidity
  simulation disabled**; only price-based slippage applies (run labelled approximate).

Toggle via `fills.enforce_circuit_limits` / `fills.enforce_liquidity` (config-and-risk.md);
both **auto-off** when the required data isn't available rather than fabricating values.

## 3. Backtest Fill Model

Two data granularities, chosen automatically by availability/strategy needs (see §6):

### 3a. Tick-replay (preferred)
Replays the **recorded tick archive** → uses the **exact same fill logic as Paper (§2)**,
making paper and tick-backtest results directly comparable. This is the high-fidelity path.

### 3b. OHLC-candle (Kite Historical)
When only OHLC candles exist, sub-candle price path is **unknown**, so fills use
**conservative worst-case assumptions** (never optimistic):

| Aspect | Rule |
|--------|------|
| **MARKET entry** | Fill at the **next candle's open** + slippage. |
| **LIMIT** | Fills only if `low ≤ limit ≤ high` of a candle; fill **at the limit price**. |
| **Intra-candle exit/trigger** | **Adverse-path assumption:** for a long, assume price hit the **low before the high** (and vice-versa for shorts), so stops are triggered before targets when both are within one candle. |
| **Gaps** | A gap through a stop fills at the **candle open** (gap price), not the stop price. |

> OHLC backtests are explicitly labelled **approximate** in results; tick-replay backtests are labelled **tick-accurate**.

---

## 4. Live Order Lifecycle (Kite REST)

- **Placement:** persist `CREATED` (with `order_ref`) → call Kite → store `broker_order_id`,
  move to `PENDING`. Order updates arrive via **Kite postback + polling fallback**.
- **Idempotency / no duplicates:** before any retry, **reconcile by `order_ref`** against the
  Kite order book to check whether the order actually reached the exchange. Never blindly re-send.
- **Retries:** only **transient** failures (network timeout, HTTP 5xx, rate-limit 429) are
  retried with exponential backoff (default 3 attempts) — and only after the reconciliation
  check confirms the prior attempt did **not** place an order. Hard rejects are **not** retried.
- **Cancellation:** open LIMIT orders are cancelled on exit/square-off; the engine **waits for
  cancel confirmation** before issuing a replacement (no overlapping orders).
- **Reconciliation:** on startup and every N seconds, fetch Kite **positions + order book** and
  compare to the engine's view. Any mismatch → **SAFE mode** (halt new entries, alert, await
  resolution). See §5.
- **Failure policy:** repeated order errors, ticker loss, or token expiry → engine halts new
  entries, attempts to protect/square-off any open position, and alerts (NFR-3).

---

## 5. Restart Recovery (engine restarts with broker state live)

On every engine start, before processing ticks:

1. **Load** last `run`, any open trade, and its `pos.vars` from the DB.
2. **Resolve in-flight orders:** for any order left `CREATED`/`PENDING`/`OPEN`, query Kite by
   `order_ref`/`broker_order_id` to determine its **final** state; update the DB accordingly.
3. **Fetch live truth** from Kite: current positions + order book.
4. **Reconcile** (DB view ↔ broker truth):

   | DB says | Kite shows | Action |
   |---------|-----------|--------|
   | Open position | Same position | **Resume**: rehydrate `pos.vars`, re-attach management. |
   | Open position | No position | Position closed while down (broker auto/manual). **Close** the trade in DB with reconciled exit, alert, go flat. |
   | Flat | A position exists | Unexpected. **SAFE mode** + alert; operator decides to adopt or manually square off. |
   | Flat | Flat | Clean start. |

5. **Warm up** indicators & rolling buffer from **historical candles** so indicators aren't cold.
6. **Re-subscribe** the ticker and resume — **only if reconciliation succeeded**; otherwise
   stay halted and alert.

`pos.vars` is persisted on every mutation (FR-4), so trailing cutoffs/peaks survive the restart.

### 5a. SAFE mode — exact operator actions
SAFE mode is entered whenever reconciliation finds a mismatch the engine must not auto-resolve
(e.g. DB flat but Kite holds a position, or an in-flight order can't be resolved). In SAFE mode
the engine **halts new entries, stops emitting orders, keeps streaming/monitoring, and alerts**
(Telegram + `events`) with the mismatch detail. It stays halted until the operator resolves it.

The cockpit shows a **SAFE-mode banner** with the broker position vs engine view and **three
buttons**, each backed by an auth+CSRF API (these are *reconciliation* controls, an explicit
extension of the "monitor + kill-switch" scope — they place/await at most one order):

| UI action | API | Engine behaviour |
|-----------|-----|------------------|
| **Adopt position** | `POST /api/engine/reconcile/adopt` | Create an engine `Position` from the broker's actual position (symbol, side, qty, avg price), initialise empty `pos.vars`, attach it to the running strategy so `on_tick`/`exit` manage it from now on. Logs an adoption event. |
| **Square off now** | `POST /api/engine/reconcile/square-off` | Place a MARKET MIS order to flatten the broker position immediately; wait for fill confirmation; record the trade; stay halted. |
| **Resume** | `POST /api/engine/resume` | Only enabled once the position view is consistent (flat-flat or adopted). Clears SAFE mode and re-enables entries. |

**LLD nuances:**
- **Adopt** hands an externally-created position to the strategy with **fresh `pos.vars`** — the
  strategy's trailing/cutoff state is rebuilt from scratch on subsequent ticks (it has no memory
  of how the position was opened). The banner warns about this before confirming.
- **Square off now** is the safe default when the position is unexpected/unknown.
- All three are **idempotent** and audited; they are rejected (409) if SAFE mode is not active.
- The emergency **kill-switch** remains available in SAFE mode and force-flattens everything.

---

## 6. Backtest Data Quality — OHLC vs Tick Replay

**Rule of thumb for which source is acceptable:**

| Strategy decides on… | Acceptable source |
|----------------------|-------------------|
| **Candle close values** only (e.g. EMA-on-close crossover, decisions at bar close) | **OHLC** is acceptable (and fast). |
| **Intra-candle LTP** (trailing stops, tick-level cutoffs, intrabar triggers — e.g. our `pos.vars["cutoff"]` example) | **Tick replay required** for fidelity; OHLC results are approximate and flagged. |

- Default: use **tick replay** when a recorded archive covers the requested range; otherwise
  fall back to **OHLC** and **label the run approximate**.
- The tick archive is built automatically during paper/live runs (FR-11), so coverage grows
  over time; OHLC (Kite Historical) provides deep history and indicator warm-up.

### Indicator behaviour across modes (consistency guarantee)
- **Candle-fed indicators** (default) update on **candle close** and are **identical** in OHLC
  backtest, tick replay, paper, and live — because the same candles close in every mode.
- **Tick-fed indicators** (opt-in) update on every tick. They are faithful in tick replay /
  paper / live. In **OHLC backtest** there are no ticks, so a tick-fed indicator **degrades to
  candle-close updates** and the run is flagged so results aren't misread.
- This is why **candle-fed is the default** (see [strategy-framework.md](strategy-framework.md) §6) —
  it guarantees cross-mode reproducibility.
