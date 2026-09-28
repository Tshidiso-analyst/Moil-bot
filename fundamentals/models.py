from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class NewsItem:
    title: str
    source: str
    published_at: datetime
    url: str
    summary: str = ""
    impact: str = "unknown"


@dataclass(frozen=True)
class FundamentalContext:
    symbol: str
    bias: str
    high_impact_events: int
    news_count: int
    summary: str
