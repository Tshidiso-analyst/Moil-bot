import json

import fitz

from knowledge.concepts.extractor import extract_concepts
from knowledge.consolidated.consolidator import consolidate_knowledge
from knowledge.documents.pdf_extractor import extract_pdf_text
from knowledge.registry.source_registry import SourceRegistry
from knowledge.rules.rule_versioning import RuleStore
from knowledge.sources.url_reader import read_url


def test_pdf_extraction(tmp_path):
    pdf_path = tmp_path / "trading.pdf"

    document = fitz.open()
    page = document.new_page()
    page.insert_text(
        (72, 72),
        "Market structure and liquidity are important trading concepts.",
    )
    document.save(pdf_path)
    document.close()

    text = extract_pdf_text(str(pdf_path))

    assert "Market structure" in text
    assert "liquidity" in text


def test_concept_extraction():
    text = """
    Market structure can show a break of structure.
    Liquidity and order blocks can also be analysed.
    """

    concepts = extract_concepts(text)

    assert "market structure" in concepts
    assert "break of structure" in concepts
    assert "liquidity" in concepts
    assert "order block" in concepts


def test_source_registry(tmp_path):
    registry = SourceRegistry(
        str(tmp_path / "sources.json")
    )

    registry.register(
        source_id="test-source",
        title="Test Trading Source",
        source_type="reference",
        location="test.pdf",
    )

    source = registry.get("test-source")

    assert source is not None
    assert source["title"] == "Test Trading Source"
    assert len(registry.list_sources()) == 1


def test_duplicate_source_is_rejected(tmp_path):
    registry = SourceRegistry(
        str(tmp_path / "sources.json")
    )

    registry.register(
        source_id="duplicate",
        title="First",
        source_type="reference",
        location="first.pdf",
    )

    try:
        registry.register(
            source_id="duplicate",
            title="Second",
            source_type="reference",
            location="second.pdf",
        )
        assert False
    except ValueError:
        assert True


def test_consolidation():
    result = consolidate_knowledge(
        source_id="source-1",
        title="Trading Concepts",
        text="  Liquidity   and market structure  ",
        concepts=["liquidity", "market structure"],
    )

    assert result["source_id"] == "source-1"
    assert result["text"] == "Liquidity and market structure"
    assert result["concepts"] == ["liquidity", "market structure"]
    assert result["version"] == 1


def test_rule_versioning(tmp_path):
    store = RuleStore(str(tmp_path / "rules.json"))

    first = store.create_rule(
        rule_id="structure-entry",
        name="Structure Entry",
        description="Test strategy rule",
        conditions=["bullish structure"],
        actions=["prepare entry"],
    )

    second = store.create_rule(
        rule_id="structure-entry",
        name="Structure Entry",
        description="Updated test strategy rule",
        conditions=["bullish structure", "liquidity sweep"],
        actions=["prepare entry"],
    )

    assert first.version == 1
    assert second.version == 2

    versions = store.get_versions("structure-entry")

    assert len(versions) == 2


def test_initial_sources_manifest():
    with open(
        "knowledge/sources/initial_sources.json",
        "r",
        encoding="utf-8",
    ) as file:
        sources = json.load(file)

    assert len(sources) >= 5

    source_ids = {source["source_id"] for source in sources}

    assert "smc-market-structure" in source_ids
    assert "smc-liquidity" in source_ids


def test_url_reader_rejects_invalid_url():
    try:
        read_url("not-a-url")
        assert False
    except ValueError:
        assert True
