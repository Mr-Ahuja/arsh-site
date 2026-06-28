"""KiteClientWrapper — one shared place for the api_key + access token.

A single process-wide instance (get_kite()) is reused by the API (login/callback) and, later,
the engine (orders/historical). The access token is set after a successful daily login.
"""

from __future__ import annotations

from kiteconnect import KiteConnect


class KiteClientWrapper:
    def __init__(self) -> None:
        self._kite: KiteConnect | None = None
        self._api_key: str | None = None
        self._access_token: str | None = None

    def configure(self, api_key: str) -> None:
        """(Re)create the underlying KiteConnect if the api_key changed."""
        if self._kite is None or self._api_key != api_key:
            self._kite = KiteConnect(api_key=api_key)
            self._api_key = api_key
            self._access_token = None

    def set_access_token(self, access_token: str) -> None:
        if self._kite is None:
            raise RuntimeError("KiteClientWrapper.configure(api_key) must be called first")
        self._kite.set_access_token(access_token)
        self._access_token = access_token

    @property
    def connected(self) -> bool:
        return self._access_token is not None

    @property
    def kite(self) -> KiteConnect:
        if self._kite is None:
            raise RuntimeError("KiteClientWrapper not configured")
        return self._kite


_instance = KiteClientWrapper()


def get_kite() -> KiteClientWrapper:
    return _instance
