import re


TRADING_CONCEPTS = {
    "market structure",
    "support",
    "resistance",
    "liquidity",
    "order block",
    "fair value gap",
    "imbalance",
    "break of structure",
    "change of character",
    "supply",
    "demand",
    "risk management",
    "stop loss",
    "take profit",
    "position sizing",
    "trend",
}


def extract_concepts(text: str) -> list[str]:
    """
    Identify known trading concepts from source text.
    """
    if not text:
        return []

    normalized = re.sub(r"\s+", " ", text.lower())

    found = [
        concept
        for concept in TRADING_CONCEPTS
        if concept in normalized
    ]

    return sorted(found)
