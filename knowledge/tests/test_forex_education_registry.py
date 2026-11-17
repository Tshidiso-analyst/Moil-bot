import json

import pytest

from knowledge.sources.forex_education_registry import (
    downloadable_sources,
    list_sources,
    load_registry,
    pending_sources,
    validate_registry,
)


def test_registry_contains_all_requested_leads():
    registry = load_registry()
    assert len(registry["sources"]) == 45
    assert len({source["id"] for source in registry["sources"]}) == 45


def test_all_new_leads_start_blocked_until_verified():
    sources = load_registry()["sources"]
    assert all(source["official_url"] is None for source in sources)
    assert all(source["download_allowed"] is False for source in sources)
    assert all(source["redistribution_allowed"] is False for source in sources)
    assert len(pending_sources()) == 45
    assert downloadable_sources() == []


def test_category_filter_returns_only_matching_sources():
    sources = list_sources("ict_smc")
    assert len(sources) == 8
    assert all(source["category"] == "ict_smc" for source in sources)


def test_duplicate_ids_are_rejected():
    data = load_registry()
    data["sources"].append(dict(data["sources"][0]))
    with pytest.raises(ValueError, match="duplicate id"):
        validate_registry(data)


def test_download_cannot_be_enabled_without_verified_permission():
    data = load_registry()
    source = data["sources"][0]
    source["download_allowed"] = True
    with pytest.raises(ValueError, match="Unsafe download permission"):
        validate_registry(data)


def test_non_https_official_url_is_rejected():
    data = load_registry()
    data["sources"][0]["official_url"] = "http://example.com/book.pdf"
    with pytest.raises(ValueError, match="must be null or HTTPS"):
        validate_registry(data)
