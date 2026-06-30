"""Generate an argon2id hash for the dashboard password.

Usage:
    python scripts/hash_password.py '<DASHBOARD_PASSWORD>'
Paste the output into APP_PASSWORD_HASH in your .env (never commit the plaintext).
"""

import sys

from argon2 import PasswordHasher

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python scripts/hash_password.py '<password>'", file=sys.stderr)
        raise SystemExit(2)
    print(PasswordHasher().hash(sys.argv[1]))
