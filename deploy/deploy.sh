#!/usr/bin/env bash
# Idempotent deploy/update for the Trade Engine on the VPS.
# Run as the `trader` user from the app directory:
#   sudo -u trader bash deploy/deploy.sh
#
# Always run during NON-market hours (a mid-session restart triggers recovery/reconciliation).
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/trade-engine/app}"
cd "$APP_DIR"

echo "==> Pulling latest code"
git pull --ff-only

echo "==> Python venv + deps"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt

echo "==> Database migrations"
mkdir -p "$(dirname "$(./.venv/bin/python -c 'from core.config import get_settings; print(get_settings().db_path)')")"
./.venv/bin/alembic upgrade head

echo "==> Building frontend (served by FastAPI at dashboard/dist)"
pushd dashboard >/dev/null
npm ci
npm run build
popd >/dev/null

echo "==> Done. Restart the service to pick up changes:"
echo "    sudo systemctl restart api.service"
