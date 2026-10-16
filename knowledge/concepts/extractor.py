import re


# Canonical names are returned even when a transcript uses an alias.
CONCEPT_PATTERNS = {
    "market structure": [
        r"market structure",
        r"price structure",
    ],
    "liquidity": [
        r"liquidity",
        r"buy[- ]side liquidity",
        r"sell[- ]side liquidity",
        r"\bbsl\b",
        r"\bssl\b",
    ],
    "liquidity sweep": [
        r"liquidity sweeps?",
        r"liquidity grabs?",
        r"stop hunts?",
        r"raids? on liquidity",
        r"sweeps? of liquidity",
    ],
    "order block": [
        r"order blocks?",
    ],
    "fair value gap": [
        r"fair value gaps?",
        r"\bfvgs?\b",
    ],
    "imbalance": [
        r"imbalances?",
        r"price inefficienc(?:y|ies)",
    ],
    "break of structure": [
        r"breaks? of structure",
        r"\bbos\b",
    ],
    "change of character": [
        r"change of character",
        r"\bchoch\b",
        r"\bmarket structure shift\b",
        r"\bmss\b",
    ],
    "support": [r"support"],
    "resistance": [r"resistance"],
    "supply": [r"supply zone", r"supply"],
    "demand": [r"demand zone", r"demand"],
    "risk management": [r"risk management"],
    "stop loss": [r"stop[- ]loss"],
    "take profit": [r"take[- ]profit"],
    "position sizing": [r"position sizing", r"lot sizing"],
    "trend": [r"trend", r"trending"],
    "premium and discount": [
        r"premium and discount",
        r"premium zone",
        r"discount zone",
    ],
    "equilibrium": [
        r"equilibrium",
        r"\b50% level\b",
        r"\bmidpoint\b",
    ],
    "optimal trade entry": [
        r"optimal trade entry",
        r"\bote\b",
    ],
    "kill zone": [
        r"kill zones?",
    ],
    "displacement": [r"displacement"],
    "inducement": [r"inducement"],
    "consequent encroachment": [r"consequent encroachment"],
    "breaker block": [r"breaker blocks?"],
    "mitigation block": [r"mitigation blocks?"],
    "turtle soup": [r"turtle soup"],
    "opening range": [r"opening range"],
    "previous day high and low": [
        r"previous day high",
        r"previous day low",
        r"\bpdh\b",
        r"\bpdl\b",
    ],
    "previous week high and low": [
        r"previous week high",
        r"previous week low",
        r"\bpwh\b",
        r"\bpwl\b",
    ],
}


def extract_concepts(text: str) -> list[str]:
    """Return canonical trading concepts detected in source text."""
    if not text:
        return []

    normalized = re.sub(r"\s+", " ", text.lower())
    found = []

    for concept, patterns in CONCEPT_PATTERNS.items():
        if any(
            re.search(r"(?<!\w)(?:" + pattern + r")(?!\w)", normalized)
            for pattern in patterns
        ):
            found.append(concept)

    return sorted(found)


# Retain the previous public constant for compatibility.
TRADING_CONCEPTS = set(CONCEPT_PATTERNS)
