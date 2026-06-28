# Architecture — Intraday Algo Trade Engine

> Companion to [requirements.md](requirements.md) and [strategy-framework.md](strategy-framework.md).
> Stack: **Python · FastAPI · SQLite (SQLAlchemy DAL) · Kite Connect · WebSocket · Telegram**.

---

## 1. High-Level View

```
                          ┌──────────────────────────────────────────────┐
                          │                 Hostinger VPS                  │
                          │                                                │
   Browser (Kite-style)   │   ┌──────────────┐      ┌──────────────────┐  │
   ──── HTTPS/WSS ───────────▶│  FastAPI App  │◀────▶│   Trade Engine    │ │
   live cockpit / history  │   │  REST + WS    │      │  (event loop)    │  │
                          │   │  auth + kite  │      │                  │  │
                          │   └──────┬───────┘      └───┬─────────┬────┘  │
                          │          │                  │         │       │
                          │      ┌───▼────┐      ┌───────▼──┐  ┌───▼────┐  │
                          │      │ SQLite │◀────▶│  Broker  │  │  Data  │  │
                          │      │  (DAL) │      │ L/P/B *  │  │ Layer  │  │
                          │      └────────┘      └────┬─────┘  └───┬────┘  │
                          └───────────────────────────┼───────────┼───────┘
                                                       │           │
                                            Kite REST (orders)   Kite Ticker (WS)
                                                       │           Kite Historical
                                                       ▼
                                                  Telegram Bot (alerts)

   * Broker: Live (Kite REST) | Paper (sim) | Backtest (historical/recorded)
```

Two long-running processes on the VPS:
- **Trade Engine** — the event loop that consumes ticks and runs strategy hooks.
- **FastAPI app** — serves the dashboard, REST API, WebSocket push, and Kite OAuth.

They share the **SQLite database** and communicate via DB + an in-process/IPC event bus
(see §6). v1 may run both in one process with asyncio; the design keeps them separable.

---

## 2. Modules / Package Layout (proposed)

```
repo/
├── engine/
│   ├── core/
│   │   ├── runner.py        # event loop: feeds ticks → strategy → orders → DB
│   │   ├── mode.py          # backtest | paper | live wiring
│   │   └── state.py         # run/trade state persistence & recovery
│   ├── strategy/
│   │   ├── base.py          # BaseStrategy, order helpers, hook dispatch
│   │   ├── position.py      # Position/Trade object + pos.vars
│   │   ├── indicators.py    # EMA, SMA, RSI, VWAP, ATR... registry
│   │   └── loader.py        # discover & import strategy files
│   ├── data/
│   │   ├── ticker.py        # Kite Ticker (WS) client + reconnect
│   │   ├── historical.py    # Kite Historical API client + cache
│   │   ├── candles.py       # tick→candle aggregator (per timeframe)
│   │   ├── buffer.py        # rolling tick/candle window
│   │   └── archive.py       # persist recorded ticks → DB (replay source)
│   ├── execution/
│   │   ├── broker.py        # Broker interface (buy/sell/square_off/positions)
│   │   ├── live.py          # LiveBroker  (Kite REST, MIS)
│   │   ├── paper.py         # PaperBroker (simulated fills + slippage)
│   │   └── backtest.py      # BacktestBroker (historical/recorded fills)
│   ├── risk/
│   │   └── guards.py        # forced square-off, daily-loss kill-switch, caps
│   ├── notify/
│   │   └── telegram.py      # alert dispatcher
│   └── kite/
│       ├── auth.py          # OAuth/session, daily token, instruments dump
│       └── client.py        # shared Kite Connect client wrapper
├── db/
│   ├── models.py            # SQLAlchemy models
│   ├── dal.py               # data-access layer (swappable to Postgres)
│   └── migrations/          # alembic
├── api/
│   ├── app.py               # FastAPI app factory
│   ├── auth.py              # single-user dashboard auth (session/token)
│   ├── routes/              # history, analytics, backtest, control, kite-login
│   └── ws.py                # WebSocket push (ticks/positions/pnl/events)
├── dashboard/               # Kite-styled frontend (build output served by FastAPI)
├── strategies/              # ← user drops strategy .py files here
├── config/                  # settings, risk thresholds, .env loading
├── deploy/                  # systemd units, nginx/Caddy, backup scripts
└── docs/                    # these documents
```

---

## 3. The Unifying Abstraction: Mode = Data Source + Broker

The single most important architectural lever. Strategy code is identical; only two
pluggable pieces change per mode:

| Mode | Data Source | Broker | Clock |
|------|-------------|--------|-------|
| **Backtest** | Kite Historical OHLC + recorded tick archive | `BacktestBroker` (fills from data) | simulated, fast-forward |
| **Paper** | Live Kite Ticker | `PaperBroker` (sim fills + slippage) | real-time |
| **Live** | Live Kite Ticker | `LiveBroker` (Kite REST, MIS) | real-time |

`runner.py` is mode-agnostic: it pulls ticks from the data source, dispatches hooks,
sends resulting orders to the broker, records everything to the DB. This is what makes
"validate in paper, then flip to live" a one-flag change.

---

## 4. Engine Event Loop (per tick)

```
tick ──▶ update candles + rolling buffer + indicators
     ──▶ persist tick to archive (if recording)
     ──▶ if FLAT:   order = strategy.entry(tick)  → if order: place via broker
         if IN POS: strategy.on_tick(tick, pos)   → mutate pos.vars (persist)
                    if strategy.exit(tick, pos):   → square_off
     ──▶ risk guards: forced square-off time? daily-loss breached? → override
     ──▶ push state (position, pnl, vars) over WebSocket
     ──▶ on fill/exit: write trade to DB + Telegram alert
```

Errors in any hook are caught → position protected (halt + square-off + alert), never
silently swallowed (NFR-3).

---

## 5. Data Model (SQLite, initial)

| Table | Purpose |
|-------|---------|
| `runs` | one row per engine run (mode, strategy, params, start/stop, status) |
| `trades` | completed/open trades (symbol, side, qty, entry/exit, pnl, reason, mode) |
| `orders` | every order + broker status (placed/filled/rejected/cancelled) |
| `trade_vars` | snapshots of `pos.vars` over a trade (audit of cutoff/peak evolution) |
| `ticks` | recorded tick archive (instrument, ts, ltp, vol) → backtest replay |
| `candles` | aggregated OHLC cache per instrument/timeframe |
| `equity` | equity/P&L time series for the curve |
| `events` | system log (connects, errors, kill-switch, token expiry) |
| `kite_session` | current day's access token + instruments dump metadata |
| `settings` | encrypted key-value config (Kite `api_key`/`api_secret` set via Settings UI, …) |
| `backtests` | backtest run config + summary metrics |

Access only through `db/dal.py` so a future Postgres/TimescaleDB swap is localized.

---

## 6. Realtime Path (Dashboard)
- Engine emits state changes onto an internal async event bus.
- FastAPI `ws.py` relays them to connected browsers over **WebSocket** (FR-21/NFR-1).
- REST endpoints serve historical/analytics/backtest data (paginated).
- Frontend renders a **Zerodha Kite-style** UI (light theme, Kite-blue `#387ED1`,
  dense tables, compact P&L tiles).

**Frontend framework — LOCKED:** **React 18 + TypeScript + Vite + Tailwind** SPA, built to
static assets and served by FastAPI (one deployable). Charts via **lightweight-charts**
(TradingView). Chosen for maximum component reuse — see
[implementation/code-reuse-strategy.md](implementation/code-reuse-strategy.md).

---

## 7. Security
- **Dashboard auth** on all control + data endpoints (single user). HTTPS only.
- **Password storage:** **argon2id** hash (no plaintext); hash lives in env/secret, not repo.
- **Sessions:** signed cookie/JWT, **expiry 8h**, sliding refresh; cookies `HttpOnly`,
  `Secure`, `SameSite=Strict`.
- **CSRF:** `SameSite=Strict` + a CSRF token required on all state-changing POSTs
  (kill-switch, Kite-login init, start/stop).
- **Login throttling:** rate-limit + exponential **lockout** after N failed attempts; repeated
  failures raise a Telegram alert.
- **Kill-switch hardening:** auth + CSRF protected, audited, **idempotent**, and additionally
  reachable via a **pre-shared `KILL_TOKEN`** fast path so it works even if the session has
  expired (true emergency stop). Rate-limited and logged.
- **Kite OAuth (semi-auto):** dashboard button → Kite redirect → callback stores the **day's
  access token** in `kite_session` (encrypted at rest). **No TOTP secret stored.**
- **Secrets** (`APP_SECRET`, `KILL_TOKEN`, Telegram token) live in `.env` / VPS environment,
  **never in the repo**. **Kite `api_key`/`api_secret`** are entered via the **Settings UI** and
  stored **encrypted in the `settings` table** (Fernet, key derived from `APP_SECRET`), with
  `.env` as an optional bootstrap. The api_secret is write-only — never returned to the browser.
- All control + auth events are audited to the `events` table.

## 7a. SQLite Concurrency & Durability
The engine (writer) and API (mostly reader) share one SQLite file — handled deliberately:
- **WAL mode** (`journal_mode=WAL`, `synchronous=NORMAL`): concurrent readers + one writer.
- **Single-writer discipline:** the **engine is the sole writer** to hot tables
  (`ticks`, `trades`, `orders`, `equity`). The API is read-only except a tiny serialized
  control path (e.g. setting the kill-switch flag), which uses a short transaction.
- **`busy_timeout`** (5 s) absorbs transient write contention.
- **Transaction boundaries:** per-tick state writes are minimal; the **tick archive is buffered
  and flushed in batches** (every N ticks / interval) to avoid write amplification at high tick
  rates — the main write-throughput concern.
- **Backups:** WAL-safe online backup (`.backup` / `VACUUM INTO`) on a nightly schedule, synced
  off-box (see [deployment.md](deployment.md) §8).
- **Migrations:** **Alembic**, versioned; run on deploy during non-market hours.
- **Scaling trigger:** if tick write volume saturates SQLite, migrate the `ticks` table to
  Postgres/TimescaleDB — isolated to `db/dal.py`.

---

## 8. Deployment (Hostinger VPS) — outline
- OS: Linux; Python venv; app code under `/opt/trade-engine`.
- **systemd** units: `engine.service` + `api.service` (auto-restart, journald logs).
- **Reverse proxy + TLS:** Caddy (simplest) or nginx + certbot → the dashboard domain.
- **Daily lifecycle:** market-hours window 09:15–15:30 IST; morning **semi-auto Kite login**;
  daily instruments dump; forced square-off + EOD summary alert.
- **Backups:** scheduled copy of the SQLite file (+ WAL) off-box.
- Full VPS runbook lives in **[deployment.md](deployment.md)** (the old static-site FTP runbook has been replaced).

---

## 9. Build Phasing (suggested)
1. **Foundation:** repo restructure, config, DB schema/DAL, Kite client + auth (semi-auto login).
2. **Data layer:** ticker (WS) + historical + candle aggregator + tick archive + buffer.
3. **Strategy framework:** `BaseStrategy`, position/`pos.vars`, indicators, loader.
4. **Execution + modes:** Paper & Backtest brokers, then Live broker; the unified runner.
5. **Risk backstops:** forced square-off, daily-loss kill-switch, caps.
6. **API + WebSocket + Telegram alerts.**
7. **Dashboard:** live cockpit → history/journal → analytics → backtest runner.
8. **VPS deployment + runbook** (rewrite deployment.md), then paper-trade validation → live.

> Recommended first runnable milestone: **Backtest + Paper of the EMA example strategy**
> end-to-end (data → framework → paper broker → DB → minimal cockpit) before Live.
