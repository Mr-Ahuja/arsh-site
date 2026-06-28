#!/usr/bin/env bash
# Local bring-up: venv + deps + .env + DB migrate + build SPA + run FastAPI (serves the SPA).
# Usage:  bash run.sh            (prompts for dashboard password on first run)
#         APP_PASSWORD=secret bash run.sh   (non-interactive)
#         bash run.sh --rebuild  (force-rebuild the frontend)
set -euo pipefail
cd "$(dirname "$0")"

# 1. venv
if [ ! -d .venv ]; then
  (python -m venv .venv) 2>/dev/null || python3 -m venv .venv
fi
if [ -f .venv/Scripts/python.exe ]; then PY=".venv/Scripts/python.exe"; else PY=".venv/bin/python"; fi

# 2. backend deps
"$PY" -m pip install --upgrade pip -q
"$PY" -m pip install -e ".[dev]" -q

# 3. .env (created once; password prompted unless $APP_PASSWORD is set)
"$PY" scripts/init_env.py

# 4. database
"$PY" -m alembic upgrade head

# 5. frontend build (served by FastAPI at dashboard/dist)
if [ "${1:-}" = "--rebuild" ] || [ ! -d dashboard/dist ]; then
  ( cd dashboard && npm install && npm run build )
fi

# 6. run
echo ""
echo "==> http://127.0.0.1:8000   (login: mrahuja / your password)"
exec "$PY" -m uvicorn api.app:app --reload --port 8000
