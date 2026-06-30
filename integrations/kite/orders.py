"""Kite REST order operations — thin wrappers around kiteconnect SDK calls.

All SDK calls are blocking → wrapped in asyncio.to_thread.
Callers (LiveBroker) handle retry logic; these functions raise on any error.
"""

from __future__ import annotations

import asyncio
from typing import Any

from kiteconnect import KiteConnect

from core.logging import get_logger
from integrations.kite.client import get_kite

log = get_logger(__name__)


async def place_order(
    *,
    symbol: str,
    exchange: str,
    side: str,
    qty: int,
    order_type: str = "MARKET",
    price: float | None = None,
    product: str = "MIS",
    tag: str | None = None,
) -> str:
    """Place a Kite order. Returns broker_order_id (string).

    tag is used as the idempotency key (mapped to order_ref / UUID4).
    Raises kiteconnect.exceptions.KiteException on any Kite error.
    """
    kite: KiteConnect = get_kite().kite

    def _call() -> str:
        kwargs: dict[str, Any] = {
            "tradingsymbol": symbol.split(":")[-1] if ":" in symbol else symbol,
            "exchange": exchange,
            "transaction_type": side,               # "BUY" | "SELL"
            "quantity": qty,
            "order_type": order_type,
            "product": product,
            "variety": kite.VARIETY_REGULAR,
        }
        if order_type == "LIMIT" and price is not None:
            kwargs["price"] = price
        if tag:
            kwargs["tag"] = tag[:20]                # Kite tag limit: 20 chars

        order_id = kite.place_order(**kwargs)
        return str(order_id)

    broker_order_id = await asyncio.to_thread(_call)
    log.info("kite_order_placed", broker_order_id=broker_order_id, symbol=symbol, side=side)
    return broker_order_id


async def cancel_order(broker_order_id: str) -> None:
    """Cancel an open Kite order."""
    kite: KiteConnect = get_kite().kite

    def _call() -> None:
        kite.cancel_order(variety=kite.VARIETY_REGULAR, order_id=broker_order_id)

    await asyncio.to_thread(_call)
    log.info("kite_order_cancelled", broker_order_id=broker_order_id)


async def get_order(broker_order_id: str) -> dict[str, Any] | None:
    """Fetch a single order by Kite order id. Returns None if not found."""
    kite: KiteConnect = get_kite().kite

    def _call() -> list[dict]:
        return kite.order_history(broker_order_id)

    history = await asyncio.to_thread(_call)
    return history[-1] if history else None


async def get_all_orders() -> list[dict[str, Any]]:
    """Fetch today's order book from Kite (used for reconciliation)."""
    kite: KiteConnect = get_kite().kite
    return await asyncio.to_thread(kite.orders)


async def get_positions() -> dict[str, Any]:
    """Fetch live positions (net + day) from Kite (used for reconciliation)."""
    kite: KiteConnect = get_kite().kite
    return await asyncio.to_thread(kite.positions)


async def get_quote(symbols: list[str]) -> dict[str, Any]:
    """Fetch full quote for a list of instruments (exchange:symbol strings)."""
    kite: KiteConnect = get_kite().kite
    return await asyncio.to_thread(kite.quote, symbols)
