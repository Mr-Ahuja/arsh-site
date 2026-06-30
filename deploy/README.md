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

## Updating an existing deployment (manual)

```bash
cd /opt/trade-engine/app
sudo -u trader bash deploy/deploy.sh        # pull + deps + migrate + build
sudo systemctl restart api.service
```

Run during non-market hours. Logs: `journalctl -u api -f`.

---

## Automatic deployment (GitHub Actions → VPS)

`.github/workflows/deploy.yml` deploys on every push to **main** (merge a `develop → main`
release PR) and via **Run workflow** (manual). It builds the server `.env` from GitHub
Secrets/Variables, then SSHes in to `git reset --hard origin/main` → `deploy.sh` →
`systemctl restart api.service`. If the SSH secrets are absent it skips and stays green.

### What's already configured in this repo
| Kind | Name | Value |
|------|------|-------|
| Variable | `APP_USERNAME` | `mrahuja` |
| Variable | `BASE_URL` | `https://arsh.thechosenone.in` |
| Secret | `APP_PASSWORD_HASH` | argon2id hash of the dashboard password |
| Secret | `APP_SECRET` | random 32-byte hex (session/JWT + at-rest key) |
| Secret | `KILL_TOKEN` | random 16-byte hex |

### What YOU must add for end-to-end automation
Settings → Secrets and variables → Actions:

| Kind | Name | Required | Notes |
|------|------|----------|-------|
| Secret | `VPS_HOST` | ✅ | VPS IP or hostname |
| Secret | `VPS_USER` | ✅ | SSH user (e.g. `trader`) — see sudoers below |
| Secret | `VPS_SSH_KEY` | ✅ | **private** key; its public half in the user's `~/.ssh/authorized_keys` |
| Secret | `VPS_PORT` | optional | SSH port, default `22` |
| Secret | `VPS_APP_DIR` | optional | default `/opt/trade-engine/app` |
| Secret | `KITE_API_KEY` / `KITE_API_SECRET` | optional | better to set them in the in-app Settings page |
| Secret | `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | optional | alerts (later tasks) |

Generate a dedicated deploy key locally and add it:
```bash
ssh-keygen -t ed25519 -f deploy_key -N "" -C "github-deploy"
# put the PUBLIC key on the VPS:
ssh-copy-id -i deploy_key.pub trader@<VPS_HOST>     # or append deploy_key.pub to ~trader/.ssh/authorized_keys
# add the PRIVATE key as the VPS_SSH_KEY secret:
gh secret set VPS_SSH_KEY < deploy_key
gh secret set VPS_HOST --body "<VPS_IP>"
gh secret set VPS_USER --body "trader"
rm deploy_key deploy_key.pub        # don't keep the private key around locally
```

### VPS prerequisites for the workflow
1. **Repo already cloned** at `VPS_APP_DIR` with `origin` = this repo (do the one-time setup above once).
2. **Node + npm + python3-venv + git** installed (the SPA is built on the VPS by `deploy.sh`).
3. **Passwordless sudo** for the restart only — `sudo visudo -f /etc/sudoers.d/trade-engine`:
   ```
   trader ALL=(root) NOPASSWD: /usr/bin/systemctl restart api.service, /usr/bin/systemctl status api.service
   ```
   (`which systemctl` → adjust the path if it's `/bin/systemctl`.)
4. `api.service` + Caddy installed once (first-time setup section above).

After that, **merging to `main` deploys automatically**; check Actions → Deploy for logs.
