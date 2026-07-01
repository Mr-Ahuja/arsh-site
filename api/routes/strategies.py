"""Strategy source API — list / read / write / validate / delete strategy files.

Lets the dashboard author strategy `.py` files in the `strategies/` package without
shell access. Every path is confined to that directory; writes are CSRF-guarded.

SECURITY: writing a strategy file is, by design, arbitrary server-side Python that the
engine will import and run. This is acceptable for this single-user, password-protected
deployment — but filenames are still strictly validated to block path traversal.
"""

from __future__ import annotations

import ast
import re
import sys
import types
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core.errors import ValidationError
from core.schemas import ApiResponse
from core.security import current_user, require_csrf
from engine.strategy.base import BaseStrategy

router = APIRouter(tags=["strategies"])

# repo_root/strategies — this file lives at repo_root/api/routes/strategies.py
_STRATEGIES_DIR = Path(__file__).resolve().parents[2] / "strategies"
_NAME_RE = re.compile(r"^[A-Za-z0-9_]+\.py$")
_PROTECTED = {"__init__.py"}


# ── Path safety ────────────────────────────────────────────────────────────────

def _resolve(file: str) -> Path:
    """Validate a user-supplied filename and return its safe absolute path.

    Rejects path separators, traversal, non-.py names, and anything that escapes
    the strategies/ directory.
    """
    if not _NAME_RE.match(file):
        raise ValidationError(
            "Filename must be letters/digits/underscores ending in .py (no paths)."
        )
    path = (_STRATEGIES_DIR / file).resolve()
    if path.parent != _STRATEGIES_DIR.resolve():
        raise ValidationError("Resolved path escapes the strategies directory.")
    return path


def _stem(file: str) -> str:
    return file[:-3]  # strip ".py"


# ── Validation ─────────────────────────────────────────────────────────────────

def _validate_source(stem: str, content: str, path: Path) -> dict:
    """Compile + import the source in isolation; report errors and discovered classes.

    Returns {"ok": bool, "errors": [...], "strategies": [names]}.
    """
    errors: list[dict] = []

    # 1. Syntax
    try:
        ast.parse(content)
    except SyntaxError as exc:
        return {
            "ok": False,
            "errors": [{"type": "syntax", "line": exc.lineno, "message": exc.msg}],
            "strategies": [],
        }

    # 2. Import-time execution in a throwaway module namespace
    mod = types.ModuleType(f"strategies.{stem}")
    mod.__file__ = str(path)
    mod.__dict__["__name__"] = f"strategies.{stem}"
    try:
        exec(compile(content, str(path), "exec"), mod.__dict__)  # noqa: S102
    except Exception as exc:  # noqa: BLE001 — surface any import/runtime error to the UI
        return {
            "ok": False,
            "errors": [{"type": type(exc).__name__, "message": str(exc)}],
            "strategies": [],
        }

    # 3. Find runnable strategy classes
    names: list[str] = []
    for attr, obj in vars(mod).items():
        if not (isinstance(obj, type) and issubclass(obj, BaseStrategy) and obj is not BaseStrategy):
            continue
        if attr.startswith("_") or obj.__dict__.get("abstract", False):
            continue
        names.append(f"{stem}.{attr}")

    if not names:
        errors.append({
            "type": "no_strategy",
            "message": "No runnable BaseStrategy subclass found (is it marked abstract?).",
        })

    return {"ok": not errors, "errors": errors, "strategies": names}


# ── Models ─────────────────────────────────────────────────────────────────────

class SourceIn(BaseModel):
    file: str
    content: str


class ValidateIn(BaseModel):
    file: str | None = None
    content: str | None = None


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/files")
async def list_files(user: str = Depends(current_user)) -> ApiResponse:
    """List editable strategy files (excludes __init__.py and dunders)."""
    files = sorted(
        p.name
        for p in _STRATEGIES_DIR.glob("*.py")
        if p.name not in _PROTECTED and not p.name.startswith("__")
    )
    return ApiResponse(data={"files": files})


@router.get("/source")
async def get_source(file: str, user: str = Depends(current_user)) -> ApiResponse:
    path = _resolve(file)
    if not path.exists():
        raise ValidationError(f"{file} does not exist.")
    return ApiResponse(data={"file": file, "content": path.read_text(encoding="utf-8")})


@router.post("/source")
async def save_source(
    body: SourceIn,
    user: str = Depends(current_user),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse:
    if body.file in _PROTECTED:
        raise ValidationError(f"{body.file} is protected and cannot be edited here.")
    path = _resolve(body.file)
    stem = _stem(body.file)

    # Validate before persisting so the editor can show problems, but still save
    # (authors may want to keep work-in-progress).
    result = _validate_source(stem, body.content, path)
    path.write_text(body.content, encoding="utf-8")

    # Evict the cached module so the next backtest/run imports the new source.
    sys.modules.pop(f"strategies.{stem}", None)

    return ApiResponse(data={"file": body.file, "saved": True, **result})


@router.post("/validate")
async def validate_source(
    body: ValidateIn,
    user: str = Depends(current_user),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse:
    if body.content is not None and body.file:
        stem, path = _stem(body.file), _resolve(body.file)
        content = body.content
    elif body.content is not None:
        stem, path, content = "_scratch", _STRATEGIES_DIR / "_scratch.py", body.content
    elif body.file:
        path = _resolve(body.file)
        if not path.exists():
            raise ValidationError(f"{body.file} does not exist.")
        stem, content = _stem(body.file), path.read_text(encoding="utf-8")
    else:
        raise ValidationError("Provide either 'file' or 'content'.")

    return ApiResponse(data=_validate_source(stem, content, path))


@router.delete("/source")
async def delete_source(
    file: str,
    user: str = Depends(current_user),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse:
    if file in _PROTECTED:
        raise ValidationError(f"{file} is protected and cannot be deleted.")
    path = _resolve(file)
    if not path.exists():
        raise ValidationError(f"{file} does not exist.")

    # Don't delete the file backing the currently-running strategy.
    from engine.runner import get_engine_state
    st = get_engine_state()
    if st.running and st.strategy_name and st.strategy_name.split(".")[0] == _stem(file):
        raise ValidationError("This strategy is currently running. Stop the engine first.")

    path.unlink()
    sys.modules.pop(f"strategies.{_stem(file)}", None)
    return ApiResponse(data={"file": file, "deleted": True})
