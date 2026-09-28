from datetime import datetime, timezone


def consolidate_knowledge(
    source_id: str,
    title: str,
    text: str,
    concepts: list[str],
) -> dict:
    """
    Build a normalized knowledge record from extracted source content.
    """
    cleaned_text = " ".join(text.split())

    return {
        "source_id": source_id,
        "title": title,
        "text": cleaned_text,
        "concepts": sorted(set(concepts)),
        "consolidated_at": datetime.now(timezone.utc).isoformat(),
        "version": 1,
    }
