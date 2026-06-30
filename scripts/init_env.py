"""Create a local .env (dev) if one doesn't exist — used by run.sh / run.bat.

Password source (in order): $APP_PASSWORD env var, else interactive prompt.
Random APP_SECRET / KILL_TOKEN are generated. Never overwrites an existing .env unless --force.
"""

from __future__ import annotations

import getpass
import os
import secrets
import sys

from argon2 import PasswordHasher

ENV_PATH = ".env"


def main() -> int:
    if os.path.exists(ENV_PATH) and "--force" not in sys.argv:
        print(".env already exists — leaving it as-is (pass --force to overwrite).")
        return 0

    pw = os.environ.get("APP_PASSWORD")
    if not pw:
        pw = getpass.getpass("Set dashboard password for user 'mrahuja': ")
    if not pw:
        print("error: empty password", file=sys.stderr)
        return 1

    hash_ = PasswordHasher().hash(pw)
    username = os.environ.get("APP_USERNAME", "mrahuja")

    content = (
        "APP_ENV=dev\n"
        "BASE_URL=http://127.0.0.1:8000\n"
        "DB_PATH=./data/trade.db\n"
        f"APP_SECRET={secrets.token_hex(32)}\n"
        f"KILL_TOKEN={secrets.token_hex(16)}\n"
        f"APP_USERNAME={username}\n"
        f"APP_PASSWORD_HASH={hash_}\n"
        "KITE_API_KEY=\n"
        "KITE_API_SECRET=\n"
        "TELEGRAM_BOT_TOKEN=\n"
        "TELEGRAM_CHAT_ID=\n"
    )
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"wrote {ENV_PATH} (user={username})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
