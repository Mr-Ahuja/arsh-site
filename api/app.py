"""FastAPI app factory: error handlers, routers, WebSocket, and the built SPA mount."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from api import ws
from api.routes import analytics, auth, backtest, engine, health, history, kite, settings
from core.config import get_settings
from core.errors import register_error_handlers
from core.logging import get_logger
from db.base import async_session
from integrations.telegram.alerts import run_alert_subscriber
from services import kite_service

log = get_logger(__name__)

_DIST = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dashboard", "dist")


class SPAStaticFiles(StaticFiles):
    """Serve built assets; fall back to index.html for client-side routes (deep links)."""

    async def get_response(self, path: str, scope):  # noqa: ANN001
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return FileResponse(os.path.join(_DIST, "index.html"))
            raise


@asynccontextmanager
async def _lifespan(app: FastAPI):  # noqa: ANN001
    # Re-arm the shared Kite client from today's stored token (survives restarts).
    try:
        async with async_session() as session:
            if await kite_service.restore_client(session):
                log.info("kite_client_restored")
    except Exception as exc:  # DB may not be migrated yet — non-fatal at startup
        log.info("kite_restore_skipped", error=str(exc))

    # Start Telegram alert subscriber (runs in background, never blocks)
    alert_task = asyncio.ensure_future(run_alert_subscriber())
    yield
    alert_task.cancel()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="Trade Engine", lifespan=_lifespan)

    if s.app_env == "dev":
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    register_error_handlers(app)

    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api/auth")
    app.include_router(settings.router, prefix="/api/settings")
    app.include_router(kite.router, prefix="/api/kite")
    app.include_router(engine.router, prefix="/api/engine")
    app.include_router(history.router, prefix="/api/history")
    app.include_router(analytics.router, prefix="/api/analytics")
    app.include_router(backtest.router, prefix="/api/backtest")
    app.include_router(ws.router, prefix="/api")

    # Serve the built SPA when present (production-style single deployable unit).
    if os.path.isdir(_DIST):
        app.mount("/", SPAStaticFiles(directory=_DIST, html=True), name="spa")
    else:
        log.info("spa_not_built", dist=_DIST, hint="run `npm run build` in dashboard/")

    return app


app = create_app()
