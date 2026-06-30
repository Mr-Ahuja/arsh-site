"""In-memory login throttle: 5 fails -> 5-minute lockout, per username.

Fine for the single-process MVP. NOTE: a Redis-backed limiter is required if the API ever
scales to multiple workers.
"""

from __future__ import annotations

import time

from core.errors import ForbiddenError

_MAX_FAILS = 5
_LOCKOUT_S = 5 * 60

# {username: (fails, locked_until_epoch)}
_state: dict[str, tuple[int, float]] = {}


def check(username: str) -> None:
    fails, locked_until = _state.get(username, (0, 0.0))
    if locked_until and time.time() < locked_until:
        remaining = int(locked_until - time.time())
        raise ForbiddenError(f"too many attempts — locked out for {remaining}s")


def fail(username: str) -> None:
    fails, _ = _state.get(username, (0, 0.0))
    fails += 1
    locked_until = time.time() + _LOCKOUT_S if fails >= _MAX_FAILS else 0.0
    _state[username] = (fails, locked_until)


def reset(username: str) -> None:
    _state.pop(username, None)
