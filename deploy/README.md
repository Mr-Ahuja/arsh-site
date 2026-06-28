# Deploy artifacts — Trade Engine on Hostinger VPS

Concrete files for the runbook in [../docs/deployment.md](../docs/deployment.md). Nothing here
contains secrets. Target layout on the VPS:

```
/opt/trade-engine/
├── app/         # this git repo
│   ├── .venv/
│   ├── .env     # secrets (chmod 600, owned by trader) — NOT in git
│   └── dashboard/dist/   # built SPA, served by FastAPI
└── data/trade.db          # SQLite (WAL)
```

| File | Purpose | Goes to |
|------|---------|---------|
| `api.service` | systemd unit running uvicorn on 127.0.0.1:8000 | `/etc/systemd/system/api.service` |
| `Caddyfile` | reverse proxy + auto-TLS (edit the domain) | `/etc/caddy/Caddyfile` |
| `.env.production.example` | env template | copy to `/opt/trade-engine/app/.env` |
| `deploy.sh` | idempotent pull + install + migrate + build | run on the box |

> The trade `engine.service` (continuous strategy loop) is **not** part of Task 01 — it arrives
> with the engine in Task 06. Only the API + dashboard run today.

---

## First-time setup (≈30 min)

Assumes the VPS exists and the domain's **A record** already points at the VPS IP.

```bash
# 1. System deps + firewall
sudo apt update && sudo apt install -y python3-venv python3-pip git caddy ufw nodejs npm
sudo ufw allow OpenSSH && sudo ufw allow 80,443/tcp && sudo ufw enable

# 2. App user + code
sudo useradd -r -m -d /opt/trade-engine trader
sudo mkdir -p /opt/trade-engine/data && sudo chown -R trader:trader /opt/trade-engine
sudo -u trader git clone https://github.com/Mr-Ahuja/arsh-site.git /opt/trade-engine/app
cd /opt/trade-engine/app
sudo -u trader git checkout main            # deploy the released branch

# 3. Secrets — create /opt/trade-engine/app/.env from the template
sudo -u trader cp deploy/.env.production.example .env
sudo -u trader python3 -m venv .venv
sudo -u trader ./.venv/bin/pip install -r requirements.txt
#   set APP_PASSWORD_HASH:
sudo -u trader ./.venv/bin/python scripts/hash_password.py '<DASHBOARD_PASSWORD>'
#   set APP_SECRET / KILL_TOKEN:  openssl rand -hex 32
sudo -u trader nano .env                     # paste hash + secrets + BASE_URL=https://<domain>
sudo chmod 600 .env

# 4. Build + migrate (deploy.sh does steps 4 onward on every update)
sudo -u trader bash deploy/deploy.sh

# 5. systemd
sudo cp deploy/api.service /etc/systemd/system/api.service
sudo systemctl daemon-reload
sudo systemctl enable --now api.service

# 6. Caddy (edit the domain in deploy/Caddyfile first)
sudo cp deploy/Caddyfile /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

Then in the **Kite developer console** set the Redirect URL to
`https://<your-domain>/api/kite/callback` (character-for-character).

Visit `https://<your-domain>` → log in → **Settings** (enter Kite api_key/secret) →
**Login to Kite**. Verify `https://<your-domain>/api/health` returns `{"status":"ok",...}`.

---

## Updating an existing deployment

```bash
cd /opt/trade-engine/app
sudo -u trader bash deploy/deploy.sh        # pull + deps + migrate + build
sudo systemctl restart api.service
```

Run during non-market hours. Logs: `journalctl -u api -f`.
