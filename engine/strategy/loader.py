"""Strategy loader — discovers and loads BaseStrategy subclasses from strategies/.

Usage:
    cls = load_strategy("ema.Strategy")          # module.ClassName
    all_cls = discover_strategies()              # scan strategies/ for all subclasses
    instance = instantiate(cls, params_override={"qty": 5})
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Any

from core.logging import get_logger
from engine.strategy.base import BaseStrategy

log = get_logger(__name__)


class StrategyLoadError(Exception):
    """Raised when a strategy file cannot be loaded or fails validation."""


# ── Public API ────────────────────────────────────────────────────────────────

def load_strategy(name: str) -> type[BaseStrategy]:
    """Load a strategy class by 'module.ClassName' (e.g. 'ema.Strategy').

    The module is imported from the `strategies` package.
    Raises StrategyLoadError on any failure.
    """
    parts = name.rsplit(".", 1)
    if len(parts) != 2:
        raise StrategyLoadError(
            f"Strategy name must be 'module.ClassName', got {name!r}"
        )
    module_name, class_name = parts
    full_module = f"strategies.{module_name}"

    try:
        mod = importlib.import_module(full_module)
    except ImportError as exc:
        raise StrategyLoadError(f"Cannot import {full_module}: {exc}") from exc

    cls = getattr(mod, class_name, None)
    if cls is None:
        raise StrategyLoadError(f"Class {class_name!r} not found in {full_module}")
    if not (isinstance(cls, type) and issubclass(cls, BaseStrategy) and cls is not BaseStrategy):
        raise StrategyLoadError(
            f"{class_name!r} in {full_module} is not a BaseStrategy subclass"
        )
    return cls


def discover_strategies() -> dict[str, type[BaseStrategy]]:
    """Scan the `strategies` package and return all BaseStrategy subclasses found.

    Returns a dict of { "module.ClassName": StrategyClass }.
    Import errors are logged and skipped (don't crash on a broken file).
    """
    import strategies as _pkg  # noqa: PLC0415

    found: dict[str, type[BaseStrategy]] = {}
    for info in pkgutil.iter_modules(_pkg.__path__):
        module_name = info.name
        full_module = f"strategies.{module_name}"
        try:
            mod = importlib.import_module(full_module)
        except Exception as exc:  # noqa: BLE001
            log.warning("strategy_discover_skip", module=full_module, error=str(exc))
            continue
        for attr_name, obj in inspect.getmembers(mod, inspect.isclass):
            if issubclass(obj, BaseStrategy) and obj is not BaseStrategy and obj.__module__ == full_module:
                key = f"{module_name}.{attr_name}"
                found[key] = obj
                log.info("strategy_discovered", name=key)
    return found


def instantiate(
    cls: type[BaseStrategy],
    *,
    params_override: dict[str, Any] | None = None,
) -> BaseStrategy:
    """Instantiate a strategy class, merge param overrides, validate params.

    Raises StrategyLoadError if param validation fails.
    """
    instance = cls()
    # Merge class-level params with run-time overrides
    merged = dict(cls.params)
    if params_override:
        merged.update(params_override)
    instance.params = merged

    # Validate against param_schema if defined
    if cls.param_schema:
        _validate_params(merged, cls.param_schema, cls.__name__)

    # Ensure required class-level declarations are present
    if not instance.instrument:
        raise StrategyLoadError(f"{cls.__name__}.instrument must be set (e.g. 'NSE:SBIN')")
    if not instance.timeframe:
        raise StrategyLoadError(f"{cls.__name__}.timeframe must be set (e.g. '5minute')")

    log.info(
        "strategy_instantiated",
        name=cls.__name__,
        instrument=instance.instrument,
        timeframe=instance.timeframe,
        params=instance.params,
    )
    return instance


# ── Param validation ──────────────────────────────────────────────────────────

def _validate_params(params: dict[str, Any], schema: dict[str, Any], name: str) -> None:
    """Validate params dict against schema at load time. Fails fast on bad config."""
    for key, rules in schema.items():
        if key not in params:
            raise StrategyLoadError(f"{name}: missing required param '{key}'")
        val = params[key]
        expected_type = rules.get("type")
        if expected_type is not None and not isinstance(val, expected_type):
            raise StrategyLoadError(
                f"{name}: param '{key}' must be {expected_type.__name__}, "
                f"got {type(val).__name__} ({val!r})"
            )
        if "min" in rules and val < rules["min"]:
            raise StrategyLoadError(
                f"{name}: param '{key}' must be >= {rules['min']}, got {val}"
            )
        if "max" in rules and val > rules["max"]:
            raise StrategyLoadError(
                f"{name}: param '{key}' must be <= {rules['max']}, got {val}"
            )
        allowed = rules.get("choices")
        if allowed is not None and val not in allowed:
            raise StrategyLoadError(
                f"{name}: param '{key}' must be one of {allowed}, got {val!r}"
            )
