from fundamentals.models import FundamentalContext, NewsItem


POSITIVE_TERMS = {
    "rate cut",
    "rate cuts",
    "dovish",
    "stimulus",
    "growth",
    "strong",
    "positive",
    "recovery",
    "easing",
    "lower rates",
    "economic expansion",
}

NEGATIVE_TERMS = {
    "rate hike",
    "rate hikes",
    "hawkish",
    "inflation",
    "recession",
    "weak",
    "negative",
    "crisis",
    "tightening",
    "tighter policy",
    "higher rates",
    "economic contraction",
}


class FundamentalAnalyzer:
    def analyse(
        self,
        symbol: str,
        news_items: list[NewsItem],
    ) -> FundamentalContext:

        positive = 0
        negative = 0
        high_impact = 0

        for item in news_items:
            text = (
                f"{item.title} {item.summary}"
            ).lower()

            positive += sum(
                1
                for term in POSITIVE_TERMS
                if term in text
            )

            negative += sum(
                1
                for term in NEGATIVE_TERMS
                if term in text
            )

            if item.impact.lower() == "high":
                high_impact += 1

        if positive > negative:
            bias = "bullish"
        elif negative > positive:
            bias = "bearish"
        else:
            bias = "neutral"

        summary = (
            f"Positive signals: {positive}; "
            f"negative signals: {negative}; "
            f"high-impact events: {high_impact}."
        )

        return FundamentalContext(
            symbol=symbol,
            bias=bias,
            high_impact_events=high_impact,
            news_count=len(news_items),
            summary=summary,
        )
