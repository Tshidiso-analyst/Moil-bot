from datetime import datetime, timezone

from fundamentals.analyzer import FundamentalAnalyzer
from fundamentals.models import NewsItem


def test_fundamental_analysis_bullish():
    news = [
        NewsItem(
            title="Central bank signals rate cut",
            source="Test",
            published_at=datetime.now(timezone.utc),
            url="https://example.com",
            summary="Officials signal easing.",
        )
    ]

    result = FundamentalAnalyzer().analyse(
        "EURUSDm",
        news,
    )

    assert result.bias == "bullish"
    assert result.news_count == 1


def test_fundamental_analysis_bearish():
    news = [
        NewsItem(
            title="Inflation remains strong",
            source="Test",
            published_at=datetime.now(timezone.utc),
            url="https://example.com",
            summary="Markets expect tighter policy.",
        )
    ]

    result = FundamentalAnalyzer().analyse(
        "EURUSDm",
        news,
    )

    assert result.bias == "bearish"


def test_fundamental_analysis_neutral():
    result = FundamentalAnalyzer().analyse(
        "EURUSDm",
        [],
    )

    assert result.bias == "neutral"
    assert result.news_count == 0
