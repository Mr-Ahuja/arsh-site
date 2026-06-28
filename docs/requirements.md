# Product Requirements — Intraday Algo Trade Engine

> **Working title:** Intraday Trade Engine (branding TBD)
> **Status:** Requirements baseline — locked via discovery on 2026-06-28
> **Owner:** Preetam Ahuja (developer, single user)

---

## 1. Product Summary

A **personal, single-user algorithmic intraday trading system** for Indian equities,
executing on **Zerodha Kite Connect**. It has two halves:

1. **Trade Engine** — runs strategy code (Python) that reacts to live market ticks,
   places/manages/exits intraday positions, and enforces safety guardrails. The same
   strategy code runs unchanged in **backtest**, **paper**, and **live** modes.
2. **Viewer / Dashboard** — a Zerodha-styled web cockpit to monitor live activity,
   review trade history & analytics, run backtests, and trigger an emergency kill-switch.

The engine **trades on the user's behalf** once a strategy is started, but every strategy
is validated in **paper mode against live ticks before going live**.

---

## 2. Goals & Non-Goals

### Goals
- Let the user (a developer) express a strategy as a **Python file** with clear lifecycle
  hooks and **mutable per-trade state**, then run it intraday automatically.
- One **unified strategy contract** that behaves identically across backtest / paper / live.
- A reliable, always-on runtime on a **Hostinger VPS** during market hours (09:15–15:30 IST).
- A real-time **web cockpit** + **trade history/analytics** + **backtest runner**.
- Strong safety: strategy-owned exits, engine-level backstops, kill-switch, Telegram alerts.

### Non-Goals (for v1)
- ❌ Multiple concurrent strategies/instruments (v1 = **one strategy, one instrument**).
- ❌ Multi-user / multi-account SaaS (single user, single set of Kite credentials).
- ❌ Asset classes other than **NSE/BSE equities intraday** (no F&O, crypto, forex).
- ❌ Approval-gated / manual order entry from the UI (UI control = monitor + kill-switch only).
- ❌ Fully automated daily Kite login (login is **semi-auto via dashboard**).
- ❌ Mobile native app (responsive web is enough).

---

## 3. Locked Decisions (Discovery)

| Area | Decision |
|------|----------|
| **Market** | Indian equities, **intraday only**, via Zerodha Kite Connect |
| **Signal source** | User's own algo, expressed in a personal **strategy-as-code framework** |
| **Concurrency (v1)** | One strategy, one instrument (architect to grow later) |
| **Autonomy** | **Paper first → live** after validation |
| **Scale** | Personal / single-user |
| **Runtime** | **Hostinger VPS**, always-on during market hours |
| **Backtesting** | **Unified** — same code in backtest / paper / live |
| **Backtest data** | **Kite Historical API (OHLC)** + self-built **tick archive** in DB |
| **Stack** | **FastAPI + SQLite** (DAL kept swappable to Postgres) |
| **Strategy API** | **Class + declarative returns** (`BaseStrategy`, `pos.vars`) |
| **Data to strategy** | Built-in indicators, historical candles, rolling buffer, raw ticks |
| **Exits** | **Strategy-owned** (profit/loss/trailing logic in `on_tick`/`exit`) |
| **Risk backstops** | Engine-level: forced square-off time + daily-loss kill-switch (under strategy logic) |
| **Order type** | Strategy chooses MARKET/LIMIT; **default MARKET (MIS)** |
| **Token refresh** | **Semi-auto** via dashboard "Login to Kite" each morning |
| **Dashboard control** | **Monitor + emergency kill-switch** (no manual order placement) |
| **Live updates** | **WebSocket push** to browser |
| **Dashboard panels** | Live cockpit · Trade history/journal · Analytics & equity curve · Backtest runner |
| **Alerts** | **Telegram bot** (entry, exit, kill-switch, errors, token expiry) |
| **Aesthetic** | **Zerodha Kite** look-and-feel (light, Kite-blue `#387ED1`, dense tables) |

---

## 4. Core Concept — Strategy-as-Code

The user drops a Python file into a `strategies/` folder. It subclasses `BaseStrategy`
and implements lifecycle hooks. The engine discovers, loads, and runs it.

```python
class Strategy(BaseStrategy):
    instrument = "NSE:SBIN"
    timeframe  = "5minute"
    params     = {"qty": 10}

    def on_start(self):
        self.ema = self.indicator(EMA, 20)       # engine feeds it; strategy only reads .value

    def entry(self, tick):                       # decides WHEN to enter
        if self.ema.value and tick.ltp > self.ema.value:
            return self.buy(qty=self.params["qty"])   # return Order, or None

    def on_tick(self, tick, pos):                # runs every tick while in a trade
        pos.vars["peak"]   = max(pos.vars.get("peak", tick.ltp), tick.ltp)
        pos.vars["cutoff"] = pos.vars["peak"] * 0.99   # create/update live vars

    def exit(self, tick, pos):                   # decides WHEN to square off
        return tick.ltp <= pos.vars["cutoff"]    # True = exit
```

**Central primitive:** every open trade carries a **mutable state bag** (`pos.vars`)
that strategy code freely creates and mutates each tick (trailing stops, cutoffs,
counters, etc.). The engine never hardcodes exit logic — it only provides backstops.

See **[strategy-framework.md](strategy-framework.md)** for the full contract.

---

## 5. Functional Requirements

### 5.1 Strategy Framework
- FR-1: Discover & load strategy files from `strategies/`.
- FR-2: Provide lifecycle hooks: `on_start`, `entry(tick)`, `on_tick(tick, pos)`,
  `exit(tick, pos)`, `on_stop`; optional `on_order_update(order)`.
- FR-3: Provide order helpers `self.buy()/self.sell()` returning Order objects
  (MARKET default, LIMIT optional).
- FR-4: Expose `pos.vars` mutable per-trade state, persisted so it survives restarts.
- FR-5: Provide built-in indicators (EMA, SMA, RSI, VWAP, ATR…) fed automatically.
- FR-6: Provide access to historical candles, a rolling tick/candle buffer, and raw ticks.
- FR-7: Strategy `params` configurable without code edits (per run).

### 5.2 Market Data
- FR-8: Live ticks via **Kite Ticker (WebSocket)** for the subscribed instrument.
- FR-9: Aggregate ticks into candles for the strategy timeframe.
- FR-10: Pull historical OHLC via **Kite Historical API** for backtests & warm-up.
- FR-11: **Persist recorded ticks** (per instrument/timeframe) to DB to build a
  replayable backtest dataset.
- FR-12: Map trading symbol → Kite instrument token (instruments dump, refreshed daily).

### 5.3 Execution & Modes
- FR-13: Three interchangeable brokers behind one interface:
  **Live** (Kite REST), **Paper** (simulated fills from live ticks),
  **Backtest** (fills from historical/recorded data).
- FR-14: Fill models (slippage, spread, partial fills, rejections, circuit limits, liquidity,
  gaps) and the **live order lifecycle** (states, idempotency via `order_ref`, retries,
  duplicate prevention, cancellation, Kite reconciliation) are specified in
  **[execution-spec.md](execution-spec.md)**.
- FR-15: Same strategy code runs in all three modes unchanged (mode chosen at run start).
- FR-15a: **Restart recovery** — on restart the engine resolves in-flight orders by `order_ref`,
  reconciles DB state ↔ live Kite positions, rehydrates `pos.vars`, warms up indicators, and
  resumes only if reconciliation succeeds (else SAFE-mode halt). See execution-spec.md §5.

### 5.4 Risk & Safety (engine-level backstops, under strategy logic)
> All thresholds are **configurable** (absolute ₹ **or** % of capital) with safe defaults —
> full schema in **[config-and-risk.md](config-and-risk.md)**.
- FR-16: **Forced square-off** of all positions at a configurable time (default 15:15 IST).
- FR-17: **Daily-loss kill-switch**: when day P&L ≤ limit (default 2% of capital), square off
  + halt for the day.
- FR-18: Configurable **max-trades/day** (default 10) and **per-trade cap** (default ₹50,000
  notional, clamp on breach).
- FR-19: Manual **emergency kill-switch** from the dashboard (+ `KILL_TOKEN` fast path).
- FR-20: Auto-halt on broker disconnect / token expiry / repeated order errors + alert.
- FR-20a: Enforcement order is strategy → per-trade cap → max-trades → daily-loss → forced
  square-off (backstops win); see config-and-risk.md §3.

### 5.5 Viewer / Dashboard (Zerodha Kite look-and-feel)
- FR-21: **Live cockpit** — current position, live LTP & P&L, active `pos.vars`
  (peak/cutoff…), run status, "Login to Kite" button, kill-switch. Real-time via WebSocket.
- FR-22: **Trade history / journal** — filterable table (entry/exit, P&L, reason,
  duration, mode), CSV export.
- FR-23: **Analytics & equity curve** — cumulative P&L, win rate, avg win/loss,
  drawdown, daily/monthly breakdown, per-strategy stats.
- FR-24: **Backtest runner** — pick strategy + date range + params, run, view results
  (trades, equity curve, metrics) comparable with live.

### 5.6 Auth, Session & Notifications
- FR-25: **Single-user dashboard auth** (login required — it controls real money).
- FR-26: **Semi-auto Kite login**: dashboard initiates Kite OAuth; engine stores the
  day's access token (no TOTP secret stored).
- FR-27: **Telegram alerts** on: entry, exit, kill-switch, errors, token expiry, daily summary.

---

## 6. Non-Functional Requirements
- NFR-1: **Latency** (measured per component, not lumped):
  - *Local decision time* (tick received by engine → order decision computed): target **< 50 ms**
    — the part we control; measured & logged per tick.
  - *Order round-trip* (engine → Kite REST ack): network-bound (~100–300 ms typical); logged
    separately, **not** counted against the decision budget.
  - *DB writes*: off the hot path (async/batched); excluded from decision latency.
  - *WebSocket push to browser*: best-effort, non-safety-critical; measured separately.
- NFR-2: **Reliability** — auto-reconnect Kite Ticker; resume strategy/trade state after restart.
- NFR-3: **Safety-first** — no silent failures; any unhandled error halts trading + alerts.
- NFR-4: **Deployability** — runs on a single Hostinger VPS (systemd + reverse proxy + TLS).
- NFR-5: **Security** — secrets encrypted/at-rest off-repo; HTTPS only; auth on all control endpoints.
- NFR-6: **Auditability** — every order, fill, decision, and system event is logged to DB.
- NFR-7: **Extensibility** — DAL swappable to Postgres; engine ready for multi-strategy later.

---

## 7. Zerodha / Kite Constraints (must design around)
- **Daily token expiry:** access token dies each morning → semi-auto login flow (FR-26).
- **No native paper trading:** paper mode is simulated by us from the live tick stream.
- **Rate limits:** orders ~10/sec; Historical API quota-limited → cache + tick archive.
- **MIS auto square-off** by broker (~15:20); our forced square-off runs earlier (FR-16).
- **Instrument tokens** required for ticker subscription → daily instruments dump (FR-12).
- **Historical API** is a paid add-on subscription on the Kite account.

---

## 8. Open Items / To Confirm Later
- Project / product **name & branding**.
- Final **VPS plan & domain** (deployment doc has the full runbook; just need the concrete values).

### Resolved since baseline
- ✅ **Risk thresholds** — now **configurable** (₹ or %) with safe defaults → [config-and-risk.md](config-and-risk.md).
- ✅ **Fill models, order lifecycle, restart recovery, backtest data quality** → [execution-spec.md](execution-spec.md).
- ✅ **Indicator feeding model** — engine-fed (read `.value`) → [strategy-framework.md](strategy-framework.md) §6.
- ✅ **Strategy contracts** (types/exceptions/timeouts/validation/trust) → strategy-framework.md §11.
- ✅ **SQLite concurrency, auth hardening, latency definition** → [architecture.md](architecture.md) §7/§7a, NFR-1.
- ✅ **VPS deployment runbook** — [deployment.md](deployment.md) rewritten (was obsolete static-site FTP).
- ✅ **Frontend framework** — locked to React + TS + Vite + Tailwind ([implementation/code-reuse-strategy.md](implementation/code-reuse-strategy.md)).
- ✅ **Implementation plan** — task breakdown in [implementation/](implementation/README.md); Task 01 detailed.

## 9. Document Map
| Doc | Scope |
|-----|-------|
| [requirements.md](requirements.md) | This PRD — decisions, FRs/NFRs, constraints |
| [architecture.md](architecture.md) | System design, modules, DB, security, concurrency |
| [strategy-framework.md](strategy-framework.md) | Strategy API contract & indicators |
| [execution-spec.md](execution-spec.md) | Fill models, order lifecycle, recovery, data quality |
| [config-and-risk.md](config-and-risk.md) | Configurable risk schema & defaults |
| [deployment.md](deployment.md) | Hostinger VPS runbook |
