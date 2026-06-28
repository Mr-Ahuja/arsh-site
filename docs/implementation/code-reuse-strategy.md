# Code-Reuse Strategy — Platform Blueprint

> This is a **platform**, not a one-off script. The rule: **a shared kernel of generic,
> reusable modules** + **thin feature slices** that compose them. Every task builds on this.
> Refines [../architecture.md](../architecture.md) §2 with the concrete, reuse-first layout.

---

## 1. Guiding Principles
1. **Write once, compose everywhere.** Cross-cutting concerns (config, logging, errors, auth,
   DB access, DTOs, events, Kite access) live in **one** place and are imported, never copied.
2. **Dependency direction is one-way:** `features → services → core/db/integrations`.
   Core never imports features. This keeps the kernel reusable and testable.
3. **Same building blocks across modes.** API and engine share the *same* kernel, DAL, Kite
   wrapper, and DTOs — so paper/live/backtest and the dashboard all speak one vocabulary.
4. **Generic over specific.** Prefer a `BaseRepository[T]` over per-entity CRUD; a `<DataTable>`
   over per-page tables; an `ApiResponse[T]` envelope over ad-hoc JSON.

---

## 2. Canonical Repository Structure

```
repo/
├── core/                  # ── SHARED KERNEL (backend) — reused by api + engine ──
│   ├── config.py          #   single typed Settings (pydantic-settings)
│   ├── logging.py         #   structlog factory: get_logger(__name__)
│   ├── errors.py          #   AppError hierarchy + FastAPI exception handlers
│   ├── security.py        #   argon2 hash/verify, JWT issue/verify, current_user dep, CSRF
│   ├── events.py          #   async pub/sub event bus (used by ws + alerts + audit)
│   ├── schemas.py         #   BaseSchema, ApiResponse[T] envelope, pagination
│   └── clock.py           #   IST time, market-hours/session helpers
├── db/
│   ├── base.py            #   async engine, SessionLocal, get_session() dep, Base
│   ├── repository.py      #   BaseRepository[T]: get/list/create/update/delete (generic)
│   ├── models.py          #   SQLAlchemy models
│   └── migrations/        #   alembic
├── integrations/          # ── SHARED EXTERNAL ADAPTERS ──
│   ├── kite/
│   │   ├── client.py      #   KiteClientWrapper (REST) — one place for api_key/token
│   │   ├── auth.py        #   login URL, request_token→access_token, checksum, session store
│   │   ├── ticker.py      #   KiteTicker WS wrapper (Task 03)
│   │   └── instruments.py #   daily instruments dump + symbol→token map (Task 03)
│   └── telegram/notifier.py  # Notifier interface + Telegram impl (email later)
├── services/              # ── BUSINESS LOGIC (reused by api routes AND engine) ──
│   ├── auth_service.py
│   ├── kite_service.py
│   └── ...                #   trade_service, backtest_service (later tasks)
├── api/                   # ── FastAPI delivery layer ──
│   ├── app.py             #   app factory: middleware, handlers, routers, static mount
│   ├── deps.py            #   shared Depends (db session, current_user, csrf, settings)
│   ├── ws.py              #   WebSocket endpoint bridging core.events → browser
│   └── routes/            #   auth.py, kite.py, health.py, (history/analytics/... later)
├── engine/                # ── TRADE ENGINE (Tasks 04-07) ──
│   ├── runner.py  modes.py  risk.py
│   ├── strategy/  execution/  data/
├── strategies/            # user strategy .py files
├── dashboard/             # ── FRONTEND SPA (React+TS+Vite) ──
│   └── src/
│       ├── lib/           #   api.ts (axios), ws.ts (reconnecting socket), queryClient.ts
│       ├── theme/         #   tokens.css (Zerodha palette), tailwind config
│       ├── components/ui/ #   Button, Input, Card, StatTile, DataTable, Badge, Modal, Toast…
│       ├── hooks/         #   useAuth, useWebSocket, usePaginatedQuery…
│       ├── stores/        #   authStore, liveStore (Zustand)
│       ├── layouts/       #   AuthLayout (centered card), AppLayout (nav + content)
│       ├── features/      #   auth/, cockpit/, history/, analytics/, backtest/
│       └── routes/        #   router + ProtectedRoute wrapper
├── config/                # risk.yml, etc.
├── deploy/                # systemd units, Caddyfile, backup scripts
├── tests/                 # mirrors package layout
├── archive/legacy-site/   # old Arsh static site (index.html, style.css, script.js)
├── .env.example
└── pyproject.toml
```

> **Key reuse moves vs architecture.md §2:** (a) a top-level **`core/` shared kernel**;
> (b) **`integrations/kite`** promoted to a top-level package so *both* API (login/callback)
> and engine (ticker/orders) reuse one Kite wrapper; (c) a **`services/`** layer so business
> logic is shared between HTTP routes and the engine loop.

---

## 3. Backend Reuse Contracts

### 3.1 `core/config.py` — one Settings
```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "dev"
    db_path: str
    app_secret: str
    app_username: str
    app_password_hash: str
    kill_token: str
    kite_api_key: str
    kite_api_secret: str
    base_url: str                 # e.g. https://arsh.thechosenone.in  (for redirect URL)
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

@lru_cache
def get_settings() -> Settings: return Settings()
```
Everything imports `get_settings()` — never reads env directly.

### 3.2 `core/schemas.py` — one response envelope
```python
class ApiResponse(BaseModel, Generic[T]):
    ok: bool = True
    data: T | None = None
    error: ErrorBody | None = None
class Page(BaseModel, Generic[T]):
    items: list[T]; total: int; page: int; size: int
```
All routes return `ApiResponse[...]`; the frontend axios layer unwraps it uniformly.

### 3.3 `core/errors.py` — one error model
`AppError(code, message, http_status)` subclasses (`AuthError`, `NotFound`, `KiteError`,
`ValidationError`…) + FastAPI handlers that serialize to `ApiResponse(error=…)`. Strategies/
engine raise `AppError`; the API turns them into consistent JSON. No bare `HTTPException` in routes.

### 3.4 `db/repository.py` — generic CRUD
```python
class BaseRepository(Generic[T]):
    model: type[T]
    def __init__(self, session): self.s = session
    async def get(self, id): ...
    async def list(self, *, where=None, order=None, page=1, size=50): ...
    async def create(self, **kw): ...
    async def update(self, id, **kw): ...
    async def delete(self, id): ...
```
Per-entity repos subclass and add only entity-specific queries.

### 3.5 `core/events.py` — one event bus
In-process async pub/sub. The engine publishes (`tick`, `position`, `order`, `pnl`, `event`);
`api/ws.py` subscribes and pushes to browsers; `telegram/notifier` subscribes to alert-worthy
events. Decouples producers from consumers → reuse + testability.

### 3.6 `services/*` — shared business logic
Pure functions/classes that take a session + DTOs and return DTOs. Called by **both** API
routes and the engine, so logic (e.g. "record a trade", "validate Kite session") is never duplicated.

---

## 4. Frontend Reuse Contracts

- **`lib/api.ts`** — one Axios instance: base URL, `withCredentials`, request interceptor adds
  CSRF header, response interceptor unwraps `ApiResponse` and normalizes errors → every feature
  calls typed functions, never raw axios.
- **`lib/ws.ts`** — one reconnecting WebSocket service with topic subscription; `useWebSocket`
  hook exposes it to components.
- **`components/ui/*`** — the design system (Zerodha tokens). Pages are assembled from these;
  no bespoke buttons/tables per page. `<DataTable>` powers history/orders/positions.
- **`stores/authStore`** — auth state + actions (`login`, `logout`, `me`); `ProtectedRoute`
  reads it. **`stores/liveStore`** — live tick/position/pnl fed by `ws.ts`.
- **`layouts/`** — `AuthLayout` (login/Kite-connect screens) and `AppLayout` (nav shell) reused
  by all feature pages.
- **`theme/tokens.css`** — single source of Zerodha look:
  `--kite-blue:#387ED1; --green:#4CAF50; --red:#FF5722; --bg:#FFFFFF; --bg-alt:#F9F9F9;
  --text:#3C3C3C; --muted:#9B9B9B; --border:#E0E0E0;` font **Inter**.

---

## 5. What this buys us per future task
- Task 02 adds models → reuse `BaseRepository`.
- Task 08 adds endpoints → reuse `deps`, `ApiResponse`, error handlers, `events`.
- Tasks 09–12 add pages → reuse `ui/`, `DataTable`, `api.ts`, `ws.ts`, layouts, theme.
- Engine tasks reuse `core`, `db`, `integrations/kite`, `services`, `events`.

The whole point: **after Task 01, new features are mostly composition, not new plumbing.**
