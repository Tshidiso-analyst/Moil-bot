import json
import re
from pathlib import Path

DEFAULT_KNOWLEDGE_PATH = (
    Path(__file__).resolve().parent
    / "videos"
    / "processed_knowledge.json"
)


def search_knowledge(query, limit=5, path=None):
    """Search saved knowledge, prioritising strong phrase and concept matches."""
    if not isinstance(query, str) or not query.strip():
        return []

    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("limit must be a positive integer")

    knowledge_path = Path(path) if path is not None else DEFAULT_KNOWLEDGE_PATH

    with knowledge_path.open("r", encoding="utf-8-sig") as file:
        data = json.load(file)

    records = data.get("records", []) if isinstance(data, dict) else []
    if not isinstance(records, list):
        return []

    terms = list(dict.fromkeys(re.findall(r"[a-z0-9]+", query.lower())))
    if not terms:
        return []

    phrase = " ".join(terms)
    phrase_pattern = re.compile(
        r"\b" + r"\s+".join(re.escape(term) for term in terms) + r"\b"
    )
    results = []

    for record in records:
        if not isinstance(record, dict):
            continue

        title = str(record.get("title") or "")
        transcript = str(record.get("text") or "")
        concepts = record.get("concepts", [])

        if not isinstance(concepts, list):
            concepts = []

        # Split legacy comma-separated values into separate concepts.
        normalized_concepts = []
        for item in concepts:
            if item is None:
                continue
            normalized_concepts.extend(
                part.strip()
                for part in str(item).split(",")
                if part.strip()
            )
        concepts = list(dict.fromkeys(normalized_concepts))

        title_lower = title.lower()
        transcript_lower = transcript.lower()
        concept_values = [item.lower().strip() for item in concepts]
        concept_text = " ".join(concept_values)

        title_terms = set(re.findall(r"[a-z0-9]+", title_lower))
        transcript_terms = set(re.findall(r"[a-z0-9]+", transcript_lower))
        concept_terms = set(re.findall(r"[a-z0-9]+", concept_text))

        score = 0

        # Prefer instructional sources over otherwise similar trade reviews.
        if re.search(
            r"\b(tutorial|lesson|teaching|lecture|guide|how to|explained)\b",
            title_lower,
        ):
            score += 12

        if re.search(
            r"\b(review|commentary)\b",
            title_lower,
        ):
            score -= 5

        # Exact extracted concepts are the strongest initial signal.
        if phrase in concept_values:
            score += 50
        elif phrase in concept_text:
            score += 30

        # A relevant title is stronger evidence than a transcript mention.
        if phrase_pattern.search(title_lower):
            score += 35

        phrase_matches = list(phrase_pattern.finditer(transcript_lower))
        if phrase_matches:
            score += 15
            score += min(len(phrase_matches) - 1, 5) * 2

        # Reward all query terms appearing together in a field.
        if all(term in title_terms for term in terms):
            score += 12
        if all(term in concept_terms for term in terms):
            score += 12
        if all(term in transcript_terms for term in terms):
            score += 6

        # Partial matches remain searchable but score lower.
        for term in terms:
            if term in title_terms:
                score += 3
            if term in concept_terms:
                score += 2
            if term in transcript_terms:
                score += 1

        if score == 0:
            continue

        # Prefer a snippet around the complete phrase when available.
        if phrase_matches:
            position = phrase_matches[0].start()
            snippet_length = phrase_matches[0].end() - position
        else:
            positions = [
                transcript_lower.find(term)
                for term in terms
                if transcript_lower.find(term) >= 0
            ]
            position = min(positions) if positions else 0
            snippet_length = max(len(phrase), 1)

        start = max(0, position - 160)
        end = min(len(transcript), position + snippet_length + 240)
        snippet = transcript[start:end].strip()

        if start > 0:
            snippet = "..." + snippet
        if end < len(transcript):
            snippet += "..."

        results.append({
            "title": title,
            "video_id": record.get("video_id"),
            "url": record.get("url"),
            "concepts": concepts,
            "snippet": snippet,
            "score": score,
        })

    # Use title and video ID as deterministic tie-breakers.
    results.sort(
        key=lambda item: (
            -item["score"],
            item["title"].lower(),
            str(item.get("video_id") or ""),
        )
    )
    return results[:limit]
