# Implementation Plan — Index & Roadmap

> How we build the intraday trade engine **platform**, task by task, so anyone can follow
> it blindly. Read this first, then [code-reuse-strategy.md](code-reuse-strategy.md), then the
> numbered task docs in order.

Parent specs: [../requirements.md](../requirements.md) · [../architecture.md](../architecture.md) ·
[../strategy-framework.md](../strategy-framework.md) · [../execution-spec.md](../execution-spec.md) ·
[../config-and-risk.md](../config-and-risk.md) · [../deployment.md](../deployment.md)

---

## 1. How to use these docs
- Each **Task = one branch = one PR** cut from `develop` (`feature/task-01-baseline`, …).
- Every task doc has: **Goal → Scope/Out-of-scope → Prerequisites → Step-by-step subtasks
  (with commands + code + LLD nuances) → Definition of Done → How to verify**.
- Do the subtasks **in order**. Don't skip the "Definition of Done" checklist — it's the gate.
- If a step needs a secret/value you don't have, it's called out explicitly with where to get it.

## 2. Locked Tech Stack (chosen for maximum reuse — see code-reuse-strategy.md)

### Backend (Python 3.12)
| Concern | Choice | Why (reuse angle) |
|--------|--------|-------------------|
| Web/API | **FastAPI** + **Uvicorn** | One app, DI via `Depends`, async, shared deps |
| Config | **pydantic-settings** | Single typed `Settings` object imported everywhere |
| Validation/DTO | **Pydantic v2** | One schema layer for API + engine + config |
| ORM / DAL | **SQLAlchemy 2.0 (async)** + **aiosqlite** | Generic `BaseRepository[T]` reused per entity |
| Migrations | **Alembic** | Versioned schema |
| Broker SDK | **kiteconnect** (official) | One shared Kite wrapper for api + engine |
| Auth | **argon2-cffi** + **PyJWT** | Shared `security.py` (hash, JWT, current-user, CSRF) |
| Logging | **structlog** | One logger factory, structured, shared |
| HTTP client | **httpx** (async) | Telegram + any outbound |
| Scheduling | **APScheduler** (optional) | Market-hours / daily jobs |
| Tests | **pytest** + **pytest-asyncio** | — |
| Quality | **ruff** + **black** + **mypy** | Enforced in CI |

### Frontend (TypeScript)
| Concern | Choice | Why (reuse angle) |
|--------|--------|-------------------|
| Framework | **React 18 + TypeScript + Vite** | Largest component-reuse ecosystem |
| Styling | **Tailwind CSS** + design tokens | Zerodha-Kite theme as reusable tokens |
| Server state | **TanStack Query** | One caching/fetch layer for all API data |
| Client state | **Zustand** | Tiny stores (auth, live data) |
| Routing | **React Router** | Protected-route wrapper reused |
| HTTP | **Axios** (single instance) | Interceptors: auth, CSRF, error envelope |
| Realtime | native **WebSocket** wrapper | One reconnecting ws service |
| Charts | **lightweight-charts** (TradingView) | Candles + equity curve |
| Tests | **Vitest** + **React Testing Library** | — |

> The frontend SPA is **built to static assets and served by FastAPI** → one deployable unit
> on the VPS (see [../deployment.md](../deployment.md)).

## 3. Task Roadmap

| # | Task | Outcome | Status |
|---|------|---------|--------|
| **01** | **Baseline structuring, deployment & auth** | Monorepo skeleton, shared kernel, App login (static) + Zerodha login/token, Kite-styled UI shell, deployable | ✅ **detailed → [task-01-baseline-and-auth.md](task-01-baseline-and-auth.md)** |
| 02 | Persistence & DAL | Full DB schema + repositories + migrations | planned |
| 03 | Kite data layer | Instruments dump, KiteTicker WS, candle aggregator, rolling buffer, tick archive | planned |
| 04 | Strategy framework | `BaseStrategy`, `Position`/`pos.vars`, indicators, loader, param validation | planned |
| 05 | Execution & brokers | Broker interface, order state machine, PaperBroker, BacktestBroker | planned |
| 06 | Engine core / runner | Event loop, mode wiring, risk backstops, restart recovery | planned |
| 07 | Live broker | Kite REST orders, idempotency, retries, reconciliation, postback consumer | planned |
| 08 | API + WebSocket + Telegram | REST endpoints, live ws push, alerts | planned |
| 09 | Dashboard — live cockpit | Real-time position/P&L/`pos.vars`, kill-switch | planned |
| 10 | Dashboard — trade history/journal | Filterable table + CSV export | planned |
| 11 | Dashboard — analytics & equity curve | Metrics, drawdown, breakdowns | planned |
| 12 | Backtest runner | UI + orchestration (tick-replay / OHLC) | planned |
| 13 | Hardening & go-live | Monitoring, backups, paper→live checklist | planned |

Tasks 02–13 will be expanded to the same depth as Task 01 when we reach them.

## 4. Conventions
- **Branching:** `feature/task-NN-<slug>` from `develop`; PR `develop → main` to release.
- **Commits:** Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`).
- **Definition of Done (every task):** code + tests pass, `ruff`/`mypy` clean, docs updated,
  app runs locally, acceptance checks in the task doc verified.
- **No secrets in git.** Everything sensitive lives in `.env` (gitignored) — see `.env.example`.
- **Reuse first:** before writing code, check `code-reuse-strategy.md` for an existing shared
  module/component. New cross-cutting code goes in the shared kernel, not in a feature folder.
