@echo off
REM Local bring-up (Windows): venv + deps + .env + DB migrate + build SPA + run FastAPI.
REM Usage:  run.bat            (prompts for dashboard password on first run)
REM         run.bat --rebuild  (force-rebuild the frontend)
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [error] Python not found on PATH. Install Python 3.12+ and retry.
  exit /b 1
)

if not exist .venv (
  echo ==^> Creating virtualenv
  python -m venv .venv
)
set "PY=.venv\Scripts\python.exe"

echo ==^> Installing backend deps
"%PY%" -m pip install --upgrade pip -q
"%PY%" -m pip install -e ".[dev]" -q

echo ==^> Ensuring .env
"%PY%" scripts\init_env.py
if errorlevel 1 exit /b 1

echo ==^> Database migrations
"%PY%" -m alembic upgrade head

if /I "%~1"=="--rebuild" goto build
if not exist dashboard\dist goto build
goto run

:build
echo ==^> Building frontend
pushd dashboard
call npm install
call npm run build
popd

:run
echo.
echo ==^> http://127.0.0.1:8000   (login: mrahuja / your password)
"%PY%" -m uvicorn api.app:app --reload --port 8000
endlocal
