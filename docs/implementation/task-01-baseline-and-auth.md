# Task 01 — Baseline Structuring, Deployment & Authentication

> **Goal:** Stand up the platform skeleton (shared kernel + monorepo), wire a deployable
> FastAPI+React app, and ship **two logins**: (1) the **App login** (static user) and
> (2) the **Zerodha Kite login** that mints the daily access token. After this task you can log
> into a Zerodha-styled dashboard shell and connect your Kite account end-to-end.
>
> Branch: `feature/task-01-baseline`. Read [code-reuse-strategy.md](code-reuse-strategy.md) first.

---

## 0. Scope

**In scope**
- Monorepo restructure + shared kernel (`core/`, `db/`, `integrations/`, `services/`, `api/`, `dashboard/`).
- Archive the old static site; replace the obsolete FTP CI.
- DB bootstrap (Alembic) with the two tables Task 1 needs: `kite_session`, `events`.
- App auth: login/logout/me, JWT cookie, CSRF, login throttling, `current_user` dep.
- Kite auth: login-URL, OAuth callback (request_token→access_token), status, postback stub.
- Frontend: Vite+React+TS+Tailwind, Zerodha theme tokens, `AuthLayout`/`AppLayout`,
  App-login page, Kite-connect screen, `ProtectedRoute`, shared `api.ts` + `authStore`.
- One-command local run + serve frontend from FastAPI; VPS deploy per [../deployment.md](../deployment.md).

**Out of scope** (later tasks): ticker/market data, strategy framework, brokers/engine,
trades/analytics pages, the live WebSocket cockpit (we add the `ws` plumbing stub only).

---

## 1. 🔑 Zerodha URLs — set these in the Kite developer console

Create/open your app at **https://developers.kite.trade/apps** → you'll get `api_key` & `api_secret`.
Set these two fields on the app (replace the domain with your real one):

| Field in Kite console | Value (production) | Value (local dev) |
|-----------------------|--------------------|-------------------|
| **Redirect URL** | `https://arsh.thechosenone.in/api/kite/callback` | `http://127.0.0.1:8000/api/kite/callback` |
| **Postback URL** | `https://arsh.thechosenone.in/api/kite/postback` | *(leave blank in dev — must be public HTTPS)* |

**LLD nuances (do not skip):**
- The Redirect URL must match **character-for-character** what's registered, or Kite rejects the login.
- Kite allows a `127.0.0.1`/`localhost` Redirect URL for development. The **Postback URL must be
  public HTTPS** (set it once the VPS+domain exist; the endpoint stub is built now).
- After a successful Kite login, Zerodha redirects the browser to:
  `…/api/kite/callback?request_token=XXXX&action=login&status=success`
- `request_token` is **single-use and expires in a few minutes** — exchange it immediately.
- The resulting `access_token` is valid **until ~06:00 IST next day**, then Zerodha invalidates
  it → user must re-login (the "semi-auto daily login", FR-26).

---

## 2. Prerequisites
- Python **3.12+**, Node **20+**, Git.
- Zerodha account with **Kite Connect** app (api_key/secret) and **Historical Data** add-on.
- (For VPS deploy) the Hostinger VPS + domain from [../deployment.md](../deployment.md).

---

## 3. App-login credentials (static, single user)

As requested, the dashboard login is a fixed user:

```
username: mrahuja
password: UseLess@420
```

**These live in `.env` (gitignored), and the password is stored as an argon2 hash — never plaintext, never committed.**

> ⚠️ **Security note:** committing a real password to a repo is unsafe. We store only the
> **argon2id hash** in `.env`. Rotate this before the dashboard is ever exposed publicly, and
> keep `.env` out of git. The plaintext above is documented only because you specified it for the MVP.

Generate the hash with the helper script (built in step 4.4):
```bash
python scripts/hash_password.py 'UseLess@420'
# → $argon2id$v=19$m=65536,t=3,p=4$....   (paste into APP_PASSWORD_HASH)
```

---

## 4. Step-by-step

### 4.1 Restructure the repo
```bash
git checkout develop && git pull
git checkout -b feature/task-01-baseline

mkdir -p core db/migrations integrations/kite integrations/telegram services \
         api/routes engine strategies dashboard config deploy scripts tests \
         archive/legacy-site

# archive the old Arsh static site (kept, not deleted)
git mv index.html style.css script.js archive/legacy-site/ 2>/dev/null || \
  mv index.html style.css script.js archive/legacy-site/
```
Add `.gitignore` (Python, Node, `.env`, `*.db`, `dashboard/dist`, `__pycache__`, `.venv`).

### 4.2 Python project + deps
`pyproject.toml` (or `requirements.txt`) with:
```
fastapi uvicorn[standard] pydantic pydantic-settings
sqlalchemy[asyncio] aiosqlite alembic
kiteconnect argon2-cffi pyjwt cryptography
structlog httpx python-multipart
# dev: pytest pytest-asyncio ruff black mypy
```
```bash
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -e ".[dev]"     # or: pip install -r requirements.txt
```

### 4.3 `.env.example` (commit this) and `.env` (don't)
```ini
APP_ENV=dev
BASE_URL=http://127.0.0.1:8000
DB_PATH=./data/trade.db
APP_SECRET=change-me-long-random
KILL_TOKEN=change-me-random
APP_USERNAME=mrahuja
APP_PASSWORD_HASH=<paste argon2 hash of UseLess@420>
KITE_API_KEY=<from kite console>
KITE_API_SECRET=<from kite console>
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

### 4.4 Shared kernel — `core/`

`core/config.py` — see [code-reuse-strategy.md](code-reuse-strategy.md) §3.1 (`Settings` + `get_settings()`).

`core/crypto.py` — Fernet for encrypting the stored Kite token at rest:
```python
from cryptography.fernet import Fernet
import base64, hashlib
def _key(secret: str) -> bytes:
    return base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
def encrypt(s: str, secret: str) -> str: return Fernet(_key(secret)).encrypt(s.encode()).decode()
def decrypt(s: str, secret: str) -> str: return Fernet(_key(secret)).decrypt(s.encode()).decode()
```

`core/security.py` — auth primitives (reused everywhere):
```python
import jwt, time
from argon2 import PasswordHasher
from fastapi import Request, HTTPException, Depends
from core.config import get_settings

ph = PasswordHasher()
def verify_password(hash_: str, pw: str) -> bool:
    try: return ph.verify(hash_, pw)
    except Exception: return False

def issue_jwt(sub: str, secret: str, ttl_s: int = 8*3600) -> str:
    now = int(time.time())
    return jwt.encode({"sub": sub, "iat": now, "exp": now + ttl_s}, secret, algorithm="HS256")

def current_user(request: Request) -> str:
    token = request.cookies.get("session")
    if not token: raise HTTPException(401, "not authenticated")
    try:
        return jwt.decode(token, get_settings().app_secret, algorithms=["HS256"])["sub"]
    except jwt.PyJWTError:
        raise HTTPException(401, "invalid session")

def require_csrf(request: Request):
    cookie = request.cookies.get("csrf"); header = request.headers.get("x-csrf-token")
    if not cookie or cookie != header: raise HTTPException(403, "csrf failed")
```
> **LLD — cookies & CSRF:** `session` cookie = **HttpOnly, Secure, SameSite=Strict**, 8h.
> `csrf` cookie = readable (not HttpOnly); the SPA echoes it in `X-CSRF-Token` on every
> mutating request (double-submit). In `dev` over http, set `Secure=False`.

`scripts/hash_password.py`:
```python
import sys; from argon2 import PasswordHasher
print(PasswordHasher().hash(sys.argv[1]))
```

Also add `core/logging.py` (structlog `get_logger`), `core/errors.py` (`AppError` + handlers),
`core/schemas.py` (`ApiResponse[T]`, `Page[T]`), `core/events.py` (async bus) — per
code-reuse-strategy.md §3. They're small and reused by every later task.

### 4.5 Database — `db/` + first migration
`db/base.py`: async `create_async_engine(f"sqlite+aiosqlite:///{db_path}")` with
`connect_args` + PRAGMas (`journal_mode=WAL`, `busy_timeout=5000`), `async_session` factory,
`get_session()` dependency, `Base = DeclarativeBase`.

`db/models.py` (Task-1 tables only):
```python
class KiteSession(Base):           # one row, the day's token
    __tablename__ = "kite_session"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str]
    access_token_enc: Mapped[str]          # Fernet-encrypted
    valid_for_date: Mapped[str]            # YYYY-MM-DD (IST)
    created_at: Mapped[datetime]

class Event(Base):                 # audit log
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime]; level: Mapped[str]; kind: Mapped[str]; message: Mapped[str]
```
```bash
alembic init -t async db/migrations          # configure env.py to import Base + settings
alembic revision --autogenerate -m "task01: kite_session, events"
alembic upgrade head
```

### 4.6 Kite integration — `integrations/kite/`
`client.py` — `KiteClientWrapper` holding a `KiteConnect(api_key)` and (when available) the
access token; single shared instance via `get_kite()`.

`auth.py` — the OAuth flow:
```python
from kiteconnect import KiteConnect
from core.config import get_settings
from core.crypto import encrypt

def login_url() -> str:
    s = get_settings()
    return KiteConnect(api_key=s.kite_api_key).login_url()   # kite.zerodha.com/connect/login?...

def exchange(request_token: str) -> dict:
    s = get_settings()
    kite = KiteConnect(api_key=s.kite_api_key)
    data = kite.generate_session(request_token, api_secret=s.kite_api_secret)
    # data has: access_token, public_token, user_id, ...
    return data
```
> **LLD:** `generate_session()` computes the Kite checksum `SHA-256(api_key + request_token +
> api_secret)` internally. Persist `data["access_token"]` **encrypted** (`core.crypto.encrypt`)
> into `kite_session` with today's IST date + `user_id`. Set it on the shared client
> (`kite.set_access_token(...)`) so later API calls are authenticated.

### 4.7 API layer — `api/`
`api/app.py` — app factory: CORS (dev), exception handlers, routers, mount the built SPA:
```python
def create_app() -> FastAPI:
    app = FastAPI(title="Trade Engine")
    register_error_handlers(app)
    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router,   prefix="/api/auth")
    app.include_router(kite.router,   prefix="/api/kite")
    # serve built SPA + client-side routing fallback
    app.mount("/", SPAStaticFiles(directory="dashboard/dist", html=True), name="spa")
    return app
```

`api/routes/auth.py`:
```python
@router.post("/login")
def login(body: LoginIn, response: Response):
    s = get_settings()
    throttle.check(body.username)                         # 5 fails → 5-min lockout
    if body.username != s.app_username or not verify_password(s.app_password_hash, body.password):
        throttle.fail(body.username);  raise AuthError("invalid credentials")
    throttle.reset(body.username)
    token = issue_jwt(body.username, s.app_secret)
    secure = s.app_env != "dev"
    response.set_cookie("session", token, httponly=True, secure=secure, samesite="strict", max_age=8*3600)
    response.set_cookie("csrf", secrets.token_urlsafe(16), secure=secure, samesite="strict", max_age=8*3600)
    return ApiResponse(data={"username": body.username})

@router.get("/me")
def me(user: str = Depends(current_user)): return ApiResponse(data={"username": user})

@router.post("/logout")
def logout(response: Response, _=Depends(require_csrf)):
    response.delete_cookie("session"); response.delete_cookie("csrf"); return ApiResponse()
```
> **LLD — throttling:** in-memory `{username: (fails, locked_until)}` is fine for the single-process
> MVP; note in code that a Redis-backed limiter is needed if the API ever scales to multiple workers.

`api/routes/kite.py`:
```python
@router.get("/login-url")
def kite_login_url(user=Depends(current_user)):
    return ApiResponse(data={"url": login_url()})

@router.get("/callback")                       # Zerodha redirects the browser here
def kite_callback(request_token: str, status: str = "success"):
    if status != "success": raise KiteError("kite login failed")
    data = exchange(request_token)
    kite_service.store_session(data)           # encrypt + upsert kite_session + set token
    return RedirectResponse(url="/?kite=connected", status_code=302)

@router.get("/status")
def kite_status(user=Depends(current_user)):
    return ApiResponse(data=kite_service.status())   # {connected, user_id, valid_for_date}

@router.post("/postback")                      # public; Kite order updates (Task 07 consumes)
async def kite_postback(request: Request):
    payload = await request.json()
    # TODO(Task07): verify checksum SHA-256(order_id+order_timestamp+api_secret); enqueue update
    log.info("kite_postback", payload=payload); return {"ok": True}
```
`api/routes/health.py` → `{status, kite_connected, env}`. `api/deps.py` centralizes
`Depends` (`get_session`, `current_user`, `require_csrf`, `get_settings`).

### 4.8 Frontend — `dashboard/` (React + TS + Vite + Tailwind)
```bash
cd dashboard
npm create vite@latest . -- --template react-ts
npm i axios @tanstack/react-query zustand react-router-dom
npm i -D tailwindcss postcss autoprefixer && npx tailwindcss init -p
```
- `src/theme/tokens.css` — Zerodha palette (see code-reuse-strategy.md §4); import in `main.tsx`.
- `src/lib/api.ts` — one axios instance (`baseURL:"/api"`, `withCredentials:true`, CSRF header
  from the `csrf` cookie, response interceptor unwraps `ApiResponse`).
- `src/stores/authStore.ts` — `login/logout/me` calling `api`; holds `user`.
- `src/routes/ProtectedRoute.tsx` — redirects to `/login` if `!user` (calls `/auth/me` once).
- `src/layouts/AuthLayout.tsx` — centered Kite-blue card. `AppLayout.tsx` — top nav (logo,
  placeholder links Cockpit/History/Analytics/Backtest, **Kite status pill**, Logout).
- `src/features/auth/LoginPage.tsx` — username/password form → `authStore.login`.
- `src/features/auth/KiteConnect.tsx` — reads `/kite/status`; **"Login to Kite"** button →
  `GET /kite/login-url` then `window.location.href = url`; shows "Connected as <user_id>" when
  back with `?kite=connected`.
- `src/App.tsx` routes: `/login` (public) · `/` & `/connect` (ProtectedRoute → AppLayout).
- `vite.config.ts` dev proxy: `/api → http://127.0.0.1:8000`.

> **Login look (Zerodha):** white card, Inter font, Kite-blue primary button, thin borders,
> minimal. Reuse `components/ui/{Button,Input,Card}` so later pages inherit the same style.

### 4.9 Local run
```bash
# terminal 1 — backend
uvicorn api.app:create_app --factory --reload --port 8000
# terminal 2 — frontend (dev, proxied)
cd dashboard && npm run dev      # http://localhost:5173
# production-style: npm run build  → FastAPI serves dashboard/dist at http://127.0.0.1:8000
```

### 4.10 CI + deployment
- **Delete** the obsolete `.github/workflows/deploy.yml` (it FTPs the old static site).
- Add `.github/workflows/ci.yml`: backend `ruff` + `mypy` + `pytest`; frontend `npm ci && npm run build`.
- **VPS deploy** follows [../deployment.md](../deployment.md): clone, venv, `alembic upgrade head`,
  build frontend, `api.service` via systemd, Caddy TLS. (Full VPS deploy automation = Task 13;
  Task 1 just needs it running behind Caddy with the real Redirect URL set.)

---

## 5. Definition of Done
- [ ] Repo restructured; old static site in `archive/legacy-site/`; FTP workflow removed.
- [ ] `.env.example` committed; `.env` gitignored; `APP_PASSWORD_HASH` generated for `UseLess@420`.
- [ ] `alembic upgrade head` creates `kite_session` + `events` (WAL enabled).
- [ ] Shared kernel (`core/*`) + `db/{base,repository,models}` + `BaseRepository` in place.
- [ ] App login works: bad creds rejected + throttled; good creds set HttpOnly+CSRF cookies; `/me` returns user; logout clears.
- [ ] Kite login works end-to-end: button → Zerodha login → callback exchanges token →
      encrypted token stored → `/kite/status` shows connected.
- [ ] `/api/kite/postback` stub returns 200 and logs payload.
- [ ] Zerodha-styled shell renders; `ProtectedRoute` blocks unauthenticated access.
- [ ] `ruff`/`mypy`/`pytest` green in CI; frontend builds; app served by FastAPI in one process.

## 6. How to verify (manual)
1. `python scripts/hash_password.py 'UseLess@420'` → paste into `.env`.
2. Start backend + frontend. Visit `/login`, enter `mrahuja` / `UseLess@420` → land on dashboard.
   Try a wrong password 5× → locked out (verify 403/lockout message).
3. Click **Login to Kite** → complete Zerodha login → you return to `/?kite=connected`;
   the nav **Kite status pill** shows connected; `GET /api/kite/status` → `connected:true` with `valid_for_date` = today.
4. `curl -X POST localhost:8000/api/kite/postback -d '{}' -H 'content-type: application/json'` → `{"ok":true}` and an `events`/log line.
5. Restart backend → `/me` still works within 8h (JWT cookie); Kite stays connected for today's date.

## 7. Tests to write (pytest)
- `verify_password` true/false; `issue_jwt`/`current_user` round-trip; expired/invalid token → 401.
- `/auth/login` happy + wrong-password + lockout-after-5.
- CSRF: mutating call without `X-CSRF-Token` → 403.
- `/kite/callback` with a mocked `exchange()` stores an (encrypted) session row; `/kite/status` reflects it.
- `crypto.encrypt/decrypt` round-trip.
