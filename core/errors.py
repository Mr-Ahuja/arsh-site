"""One error model. Services/engine raise AppError; the API serializes to ApiResponse(error=...).

No bare HTTPException in routes — raise an AppError subclass instead.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.logging import get_logger

log = get_logger(__name__)


class AppError(Exception):
    code: str = "app_error"
    http_status: int = 400

    def __init__(self, message: str, *, code: str | None = None, http_status: int | None = None):
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status


class AuthError(AppError):
    code = "auth_error"
    http_status = 401


class ForbiddenError(AppError):
    code = "forbidden"
    http_status = 403


class NotFoundError(AppError):
    code = "not_found"
    http_status = 404


class ValidationError(AppError):
    code = "validation_error"
    http_status = 422


class KiteError(AppError):
    code = "kite_error"
    http_status = 400


def _payload(err: AppError) -> dict:
    return {"ok": False, "data": None, "error": {"code": err.code, "message": err.message}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        log.info("app_error", code=exc.code, message=exc.message, path=request.url.path)
        return JSONResponse(status_code=exc.http_status, content=_payload(exc))
