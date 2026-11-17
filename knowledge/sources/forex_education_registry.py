"""Read-only registry helpers for curated Forex education sources.

This module does not download, scrape, or execute source material. It deliberately
fails closed until source ownership, access terms, and licence permissions are
verified in the registry.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REGISTRY_PATH = Path(__file__).with_name("forex_education_registry.json")
REQUIRED_FIELDS = {
    "id", "title", "category", "source_type", "official_url",
    "access_status", "license_status", "redistribution_allowed",
    "download_allowed", "ingestion_status", "review_status",
}
VALID_ACCESS = {"not_verified", "public", "registration_required", "paid", "restricted", "unavailable"}
VALID_LICENSE = {"unknown", "verified", "permission_required", "all_rights_reserved", "public_domain_review_required"}


def load_registry(path: str | Path = REGISTRY_PATH) -> dict[str, Any]:
    """Load and validate the source registry."""
    registry_path = Path(path)
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    validate_registry(data)
    return data


def validate_registry(data: dict[str, Any]) -> None:
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("Unsupported Forex education registry schema.")
    sources = data.get("sources")
    if not isinstance(sources, list):
        raise ValueError("Registry sources must be a list.")

    seen: set[str] = set()
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            raise ValueError(f"Source at index {index} must be an object.")
        missing = REQUIRED_FIELDS - source.keys()
        if missing:
            raise ValueError(f"Source at index {index} is missing: {sorted(missing)}")
        source_id = source["id"]
        if not isinstance(source_id, str) or not source_id.strip() or source_id in seen:
            raise ValueError(f"Source at index {index} has an invalid or duplicate id.")
        seen.add(source_id)

        if source["access_status"] not in VALID_ACCESS:
            raise ValueError(f"Invalid access_status for {source_id}.")
        if source["license_status"] not in VALID_LICENSE:
            raise ValueError(f"Invalid license_status for {source_id}.")
        if not isinstance(source["redistribution_allowed"], bool):
            raise ValueError(f"redistribution_allowed must be boolean for {source_id}.")
        if not isinstance(source["download_allowed"], bool):
            raise ValueError(f"download_allowed must be boolean for {source_id}.")

        url = source["official_url"]
        if url is not None and (
            not isinstance(url, str) or not url.startswith("https://")
        ):
            raise ValueError(f"official_url must be null or HTTPS for {source_id}.")

        # Permission flags may only be enabled after a verified licence and access review.
        if source["download_allowed"] and not (
            source["access_status"] in {"public", "registration_required"}
            and source["license_status"] == "verified"
            and source["redistribution_allowed"] is True
            and url is not None
        ):
            raise ValueError(f"Unsafe download permission configuration for {source_id}.")


def list_sources(category: str | None = None, *, path: str | Path = REGISTRY_PATH) -> list[dict[str, Any]]:
    sources = load_registry(path)["sources"]
    if category is None:
        return sources
    return [source for source in sources if source["category"] == category]


def pending_sources(*, path: str | Path = REGISTRY_PATH) -> list[dict[str, Any]]:
    """Return sources still awaiting URL/access/licence verification."""
    return [
        source for source in load_registry(path)["sources"]
        if source["access_status"] == "not_verified"
        or source["license_status"] != "verified"
        or source["official_url"] is None
    ]


def downloadable_sources(*, path: str | Path = REGISTRY_PATH) -> list[dict[str, Any]]:
    """Return only sources explicitly cleared for lawful redistribution."""
    return [
        source for source in load_registry(path)["sources"]
        if source["download_allowed"]
        and source["redistribution_allowed"]
        and source["license_status"] == "verified"
        and source["official_url"] is not None
    ]


__all__ = [
    "REGISTRY_PATH", "load_registry", "validate_registry",
    "list_sources", "pending_sources", "downloadable_sources",
]
