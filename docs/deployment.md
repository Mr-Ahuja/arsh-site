# Deployment — Intraday Trade Engine on Hostinger VPS

> **Replaces** the previous static-site FTP runbook (obsolete). This product is a
> long-running Python service, not static files — it requires a VPS, not shared hosting.
> Companion to [architecture.md](architecture.md) §8.

---

## 1. Topology

```
Internet ──HTTPS/WSS──▶ Caddy (reverse proxy + auto-TLS) ──▶ FastAPI (api.service :8000)
                                                          │
                                                          ├──▶ Trade Engine (engine.service)
                                                          │        ├─ Kite Ticker (WSS, outbound)
                                                          │        ├─ Kite REST (orders/historical, outbound)
                                                          │        └─ Telegram (outbound)
                                                          └──▶ SQLite (WAL) on local disk
```

Two systemd-managed processes share one SQLite DB on the VPS local disk.

---

## 2. Prerequisites
- Hostinger **VPS** plan (KVM), Ubuntu LTS, ≥1 vCPU / 1–2 GB RAM (SQLite + Python is light).
- A **domain/subdomain** (e.g. `trade.example.com`) pointed (A record) to the VPS IP.
- **Zerodha Kite Connect** app (`api_key`, `api_secret`) with a **redirect URL** set to
  `https://trade.example.com/api/kite/callback`, and the **Historical Data** add-on.
- A **Telegram bot** token + chat id.

---

## 3. One-Time Server Setup
```bash
# system deps
sudo apt update && sudo apt install -y python3-venv python3-pip git caddy ufw

# firewall: only SSH + HTTPS (Caddy handles 80→443)
sudo ufw allow OpenSSH && sudo ufw allow 80,443/tcp && sudo ufw enable

# app user + code
sudo useradd -r -m -d /opt/trade-engine trader
sudo -u trader git clone <repo-url> /opt/trade-engine/app
cd /opt/trade-engine/app
sudo -u trader python3 -m venv .venv
sudo -u trader .venv/bin/pip install -r requirements.txt
```

## 4. Secrets (never in the repo)
`/opt/trade-engine/app/.env` (chmod 600, owned by `trader`):
```
KITE_API_KEY=...
KITE_API_SECRET=...
APP_SECRET=...                 # session/JWT signing
DASHBOARD_PASSWORD_HASH=...    # argon2id hash (see §8 of architecture)
KILL_TOKEN=...                 # pre-shared emergency kill-switch token
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
DB_PATH=/opt/trade-engine/data/trade.db
RISK_CONFIG=/opt/trade-engine/app/config/risk.yml
```
Sensitive at-rest values (e.g. stored daily token) are encrypted with a key derived from `APP_SECRET`.

## 5. systemd Units
`/etc/systemd/system/api.service`
```ini
[Unit]
Description=Trade Engine API
After=network-online.target
[Service]
User=trader
WorkingDirectory=/opt/trade-engine/app
EnvironmentFile=/opt/trade-engine/app/.env
ExecStart=/opt/trade-engine/app/.venv/bin/uvicorn api.app:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3
[Install]
WantedBy=multi-user.target
```
`/etc/systemd/system/engine.service` — same pattern, `ExecStart=... -m engine.core.runner`.
The engine runs continuously and **self-gates to market hours** (09:15–15:30 IST) internally,
so it survives restarts without external cron. (Optional: a `systemd timer` can hard-stop it
nightly to free resources.)

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now api.service engine.service
```

## 6. Reverse Proxy + TLS (Caddy)
`/etc/caddy/Caddyfile`
```
trade.example.com {
    reverse_proxy 127.0.0.1:8000
    encode gzip
}
```
Caddy auto-provisions/renews Let's Encrypt TLS. WebSocket upgrades pass through automatically.

## 7. Daily Operating Procedure
1. **Morning (before 09:15 IST):** open `https://trade.example.com`, log in, click
   **"Login to Kite"** → complete Kite OAuth → engine stores the day's token + instruments dump.
2. Select strategy + params + mode (**paper** until validated, then **live**); start.
3. Engine trades the session; dashboard shows live cockpit; Telegram alerts on events.
4. **15:15 IST:** forced square-off fires; EOD summary alert sent.
5. Token expires overnight → repeat step 1 next trading day.

## 8. Backups
- SQLite **WAL-safe** online backup nightly:
  `sqlite3 $DB_PATH ".backup '/opt/trade-engine/backups/trade-$(date +%F).db'"`
- Sync `backups/` off-box (e.g. rclone to object storage). Retain 30 days.
- Tick archive can grow large → separate retention/rotation policy (see config-and-risk.md).

## 9. Migrations & Releases
- Schema changes via **Alembic**: `alembic upgrade head` on deploy.
- Deploy = `git pull && pip install -r requirements.txt && alembic upgrade head && systemctl restart api engine`.
- **Always restart during non-market hours.** A mid-session restart triggers the recovery
  & reconciliation flow (see [execution-spec.md](execution-spec.md) §5) — safe, but avoid if possible.

## 10. Rollback
- `git checkout <last-good-sha>`, reinstall deps, `alembic downgrade` if schema changed, restart services.
- Restore DB from the latest backup only if data corruption is suspected (you lose intra-day rows since backup).

## 11. Monitoring & Health
- `journalctl -u engine -f` / `-u api -f` for logs.
- `/api/health` returns engine state, ticker connectivity, token validity, last tick age.
- Telegram alerts on: ticker disconnect, token expiry, kill-switch, order errors, crash/restart.
