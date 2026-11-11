"""Broker-aware discovery and classification of MT5 instruments.

Discovery is metadata-driven: canonical names are matched to broker symbols
without assuming a particular suffix or account naming convention.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable


@dataclass(frozen=True)
class Instrument:
    canonical: str
    broker_symbol: str
    asset_class: str
    description: str = ""


# Common instruments are search targets, not a claim that every broker lists them.
_WATCHLIST: dict[str, tuple[str, ...]] = {
    "XAUUSD": ("GOLD", "XAUUSD"),
    "XAGUSD": ("SILVER", "XAGUSD"),
    "EURUSD": ("EURUSD",), "GBPUSD": ("GBPUSD",),
    "USDJPY": ("USDJPY",), "USDCHF": ("USDCHF",),
    "AUDUSD": ("AUDUSD",), "NZDUSD": ("NZDUSD",),
    "USDCAD": ("USDCAD",), "EURGBP": ("EURGBP",),
    "EURJPY": ("EURJPY",), "GBPJPY": ("GBPJPY",),
    "AUDJPY": ("AUDJPY",), "EURAUD": ("EURAUD",),
    "GBPAUD": ("GBPAUD",), "GBPCHF": ("GBPCHF",),
    "CADJPY": ("CADJPY",), "CHFJPY": ("CHFJPY",),
    "US30": ("US30", "DJ30", "DOW30", "WS30"),
    "NAS100": ("NAS100", "USTEC", "US100", "NASDAQ"),
    "SPX500": ("SPX500", "US500", "SP500", "USA500"),
    "GER40": ("GER40", "DAX40", "DE40"),
    "UK100": ("UK100", "FTSE100"),
}


def _compact(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _classify(canonical: str) -> str:
    if canonical in {"XAUUSD", "XAGUSD"}:
        return "metal"
    if canonical in {"US30", "NAS100", "SPX500", "GER40", "UK100"}:
        return "index"
    if len(canonical) == 6 and canonical.isalpha():
        return "forex"
    return "other"


def discover_instruments(
    mt5_module: Any,
    *,
    include_unwatchlisted: bool = False,
    watchlist: dict[str, tuple[str, ...]] | None = None,
) -> list[Instrument]:
    """Return available watchlist instruments mapped to actual broker symbols.

    MT5 symbol names and descriptions are both considered. A suffix such as
    .a, m, _pro or broker-specific prefixes is tolerated. Ambiguous matches
    are resolved deterministically, preferring exact names and shorter names.
    """
    raw = mt5_module.symbols_get()
    if raw is None:
        return []
    symbols = list(raw)
    targets = watchlist or _WATCHLIST
    found: list[Instrument] = []
    used: set[str] = set()

    for canonical, aliases in targets.items():
        alias_tokens = {_compact(alias) for alias in aliases}
        candidates: list[tuple[int, int, str, str]] = []
        for item in symbols:
            name = str(getattr(item, "name", "") or "")
            description = str(getattr(item, "description", "") or "")
            name_token = _compact(name)
            desc_token = _compact(description)
            if not name or name in used:
                continue
            rank = None
            canonical_token = _compact(canonical)
            for alias in alias_tokens:
                alias_priority = 0 if alias == canonical_token else 2
                if name_token == alias:
                    rank = min(rank if rank is not None else 99, alias_priority)
                elif name_token.startswith(alias) or name_token.endswith(alias):
                    rank = min(rank if rank is not None else 99, alias_priority + 1)
                elif alias in name_token or alias in desc_token:
                    rank = min(rank if rank is not None else 99, alias_priority + 2)
            if rank is not None:
                candidates.append((rank, len(name), name, description))
        if candidates:
            _, _, broker_name, description = sorted(candidates)[0]
            found.append(Instrument(canonical, broker_name, _classify(canonical), description))
            used.add(broker_name)

    if include_unwatchlisted:
        known = {item.broker_symbol for item in found}
        for item in symbols:
            name = str(getattr(item, "name", "") or "")
            if name and name not in known:
                found.append(Instrument(name, name, "other", str(getattr(item, "description", "") or "")))
    return found


def resolve_instrument(canonical_or_broker_name: str, instruments: Iterable[Instrument]) -> str:
    """Resolve a canonical instrument or already-known broker symbol."""
    requested = _compact(canonical_or_broker_name)
    for item in instruments:
        if requested in {_compact(item.canonical), _compact(item.broker_symbol)}:
            return item.broker_symbol
    raise ValueError(f"Instrument '{canonical_or_broker_name}' is not available in this broker's MT5 symbol list.")


__all__ = ["Instrument", "discover_instruments", "resolve_instrument"]
