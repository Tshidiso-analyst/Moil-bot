from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path


INPUT_PATH = Path("knowledge/reports/strategy_source_evidence.json")
JSON_OUTPUT = Path("knowledge/reports/strategy_source_review.json")
CSV_OUTPUT = Path("knowledge/reports/strategy_source_review.csv")


TOPIC_MAP = {
    "liquidity and liquidity sweeps": "liquidity",
    "market structure higher highs higher lows": "market_structure",
    "fair value gap entry conditions": "fair_value_gap",
    "order blocks and market structure": "order_blocks",
    "higher timeframe bias and alignment": "timeframe_alignment",
    "trading sessions and kill zones": "sessions",
    "stop loss invalidation and take profit": "stop_loss_and_invalidation",
    "risk management position sizing": "risk_management",
    "risk reward and trade management": "trade_management",
    "fundamental news economic events": "fundamentals",
    "strategy entry and exit rules": "entry_and_exit",
}


SPECIFIC_TERMS = {
    "liquidity": [
        "liquidity sweep", "sweep liquidity", "swept liquidity",
        "buy-side liquidity", "sell-side liquidity",
        "buy side liquidity", "sell side liquidity",
        "equal highs", "equal lows", "liquidity pool",
        "stop hunt", "stop run", "liquidity raid",
    ],
    "market_structure": [
        "higher high", "higher highs", "higher low", "higher lows",
        "lower high", "lower highs", "lower low", "lower lows",
        "break of structure", "change of character",
        "swing high", "swing low", "bos", "choch",
    ],
    "fair_value_gap": [
        "fair value gap", "fvg", "imbalance",
    ],
    "order_blocks": [
        "order block", "breaker block", "mitigation block",
    ],
    "timeframe_alignment": [
        "higher timeframe", "higher time frame",
        "multi-timeframe", "multi timeframe",
        "top-down analysis", "timeframe alignment",
        "time frame alignment", "daily bias",
    ],
    "sessions": [
        "kill zone", "killzone", "london session",
        "new york session", "new york open", "london open",
        "asian session", "london close",
    ],
    "stop_loss_and_invalidation": [
        "stop loss", "stop-loss", "invalidation",
        "invalidation condition", "stop placement",
    ],
    "risk_management": [
        "position sizing", "risk per trade", "risk amount",
        "risk limit", "maximum drawdown", "risk management",
        "account risk", "lot size",
    ],
    "trade_management": [
        "risk reward", "risk/reward", "take profit",
        "partial profit", "breakeven", "break even",
        "trailing stop", "trade management",
    ],
    "fundamentals": [
        "economic calendar", "nonfarm payroll", "nfp",
        "consumer price index", "cpi", "fomc",
        "central bank", "interest rate decision",
        "forecast", "actual", "rate hike", "rate cut",
        "high impact news",
    ],
    "entry_and_exit": [
        "entry condition", "entry conditions", "entry trigger",
        "entry signal", "exit condition", "exit conditions",
        "invalidation", "confirmation", "trade plan",
    ],
}


OPERATIONAL_TERMS = {
    "fair_value_gap": [
        "entry", "displacement", "mitigation",
        "inversion", "premium", "discount", "rejection",
    ],
    "order_blocks": [
        "entry", "mitigation", "displacement",
        "rejection", "invalidation", "confirmation",
    ],
    "timeframe_alignment": [
        "alignment", "agree", "agreement", "bias",
        "direction", "trend", "confluence",
    ],
    "sessions": [
        "time", "open", "close", "entry", "liquidity",
        "volatility", "range",
    ],
    "stop_loss_and_invalidation": [
        "take profit", "risk reward", "invalidation",
        "position size", "position sizing", "breakeven",
    ],
    "risk_management": [
        "position sizing", "risk per trade", "stop loss",
        "risk reward", "risk/reward", "drawdown",
        "maximum loss", "risk amount",
    ],
    "trade_management": [
        "partial", "breakeven", "break even",
        "take profit", "stop loss", "invalidation",
    ],
    "fundamentals": [
        "forecast", "actual", "previous", "revision",
        "interest rate", "currency", "impact",
        "before release", "after release",
    ],
    "entry_and_exit": [
        "entry", "exit", "invalidation", "confirmation",
        "stop loss", "take profit", "trigger",
    ],
}


def _matches(text: str, phrases: list[str]) -> list[str]:
    return [phrase for phrase in phrases if phrase in text]


def assess_passage(record: dict, query: str) -> dict:
    topic = TOPIC_MAP.get(query)
    text = " ".join([
        str(record.get("title") or ""),
        str(record.get("snippet") or ""),
    ]).casefold()

    if topic is None:
        return {
            "topic": "unknown",
            "relevance": "weak",
            "matched_terms": [],
            "reason": "No relevance policy is defined for this query.",
        }

    specific = _matches(text, SPECIFIC_TERMS.get(topic, []))
    operational = _matches(text, OPERATIONAL_TERMS.get(topic, []))

    if topic == "liquidity":
        level = "direct" if specific else (
            "partial" if "liquidity" in text else "weak"
        )
    elif topic == "market_structure":
        level = "direct" if specific else (
            "partial" if "market structure" in text else "weak"
        )
    elif topic == "fair_value_gap":
        level = "direct" if specific and operational else (
            "partial" if specific else "weak"
        )
    elif topic == "order_blocks":
        level = "direct" if specific and operational else (
            "partial" if specific else "weak"
        )
    elif topic == "timeframe_alignment":
        level = "direct" if specific and operational else (
            "partial" if specific else "weak"
        )
    elif topic == "sessions":
        level = "direct" if specific and operational else (
            "partial" if "session" in text else "weak"
        )
    elif topic in {
        "stop_loss_and_invalidation",
        "risk_management",
        "trade_management",
        "fundamentals",
        "entry_and_exit",
    }:
        level = "direct" if specific and operational else (
            "partial" if specific else "weak"
        )
    else:
        level = "weak"

    reasons = {
        "direct": "Specific topic terminology and operational context found.",
        "partial": "Topic is mentioned, but actionable context is incomplete.",
        "weak": "Passage does not contain enough topic-specific evidence.",
    }

    return {
        "topic": topic,
        "relevance": level,
        "matched_terms": sorted(set(specific + operational)),
        "reason": reasons[level],
    }


def review_catalogue(input_path=INPUT_PATH) -> dict:
    path = Path(input_path)
    if not path.is_file():
        raise FileNotFoundError(f"Source evidence catalogue not found: {path}")

    catalogue = json.loads(path.read_text(encoding="utf-8-sig"))
    records = catalogue.get("records", [])
    assessments = []
    counts_by_query = {}

    for record in records:
        queries = record.get("matched_queries", [])
        if not queries:
            queries = ["unmatched"]

        for query in queries:
            result = assess_passage(record, query)
            assessment = {
                "evidence_id": record.get("evidence_id", ""),
                "source_type": record.get("source_type", ""),
                "title": record.get("title", ""),
                "locator": record.get("locator", ""),
                "url": record.get("url", ""),
                "video_id": record.get("video_id", ""),
                "page": record.get("page"),
                "query": query,
                **result,
                "search_score": record.get("search_score", 0),
                "snippet": record.get("snippet", ""),
                "review_status": "requires_human_review",
                "rule_status": "not_approved",
            }
            assessments.append(assessment)

            query_counts = counts_by_query.setdefault(
                query,
                Counter(),
            )
            query_counts[result["relevance"]] += 1

    summary = {
        query: dict(counts)
        for query, counts in counts_by_query.items()
    }

    return {
        "input_path": str(path),
        "input_record_count": len(records),
        "assessment_count": len(assessments),
        "summary_by_query": summary,
        "relevance_policy": (
            "Heuristic screening only; 'direct' means candidate for "
            "human review, not proof that a trading rule is supported."
        ),
        "assessments": assessments,
    }


def write_review_report():
    report = review_catalogue()
    JSON_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    JSON_OUTPUT.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    fields = [
        "evidence_id", "source_type", "title", "locator",
        "query", "topic", "relevance", "matched_terms",
        "reason", "search_score", "review_status", "rule_status",
        "url", "video_id", "page", "snippet",
    ]

    with CSV_OUTPUT.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()

        for record in report["assessments"]:
            row = dict(record)
            row["matched_terms"] = "; ".join(row["matched_terms"])
            writer.writerow({field: row.get(field, "") for field in fields})

    print("===== SOURCE RELEVANCE REVIEW =====")
    print("Passages in input:", report["input_record_count"])
    print("Query assessments:", report["assessment_count"])
    print("JSON report:", JSON_OUTPUT)
    print("CSV report:", CSV_OUTPUT)

    for query, counts in report["summary_by_query"].items():
        print(f"{query}: {counts}")

    print(
        "\nNo passages were promoted to approved trading rules. "
        "Every assessment still requires review."
    )


if __name__ == "__main__":
    write_review_report()
