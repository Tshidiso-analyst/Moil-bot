from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from fundamentals.models import NewsItem


DEFAULT_HEADERS = {
    "User-Agent": "Moil-Bot/1.0"
}

DEFAULT_RSS_SOURCES = [
    ("Reuters Markets", "https://feeds.reuters.com/reuters/marketsNews"),
    ("Reuters Business", "https://feeds.reuters.com/reuters/businessNews"),
    ("CNBC Markets", "https://www.cnbc.com/id/10001054/device/rss/rss.html"),
]


def _parse_date(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)

    try:
        parsed = parsedate_to_datetime(value)

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc)

    except (TypeError, ValueError):
        return datetime.now(timezone.utc)


def _normalise_impact(value: str | None) -> str:
    text = (value or "unknown").strip().lower()
    if text in {"high", "major", "important"}:
        return "high"
    if text in {"medium", "moderate", "normal"}:
        return "medium"
    if text in {"low", "minor"}:
        return "low"
    return "unknown"


def _dedupe_news(items: list[NewsItem]) -> list[NewsItem]:
    seen: set[str] = set()
    deduped: list[NewsItem] = []
    for item in items:
        key = (item.title.strip() + "|" + item.source.strip() + "|" + item.url.strip()).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


class NewsReader:
    def fetch_rss(
        self,
        url: str,
        source: str = "unknown",
        timeout: int = 15,
    ) -> list[NewsItem]:
        if not url.startswith(("http://", "https://")):
            raise ValueError("RSS URL must use HTTP or HTTPS.")

        request = Request(
            url,
            headers=DEFAULT_HEADERS,
        )

        try:
            with urlopen(request, timeout=timeout) as response:
                content = response.read()
        except Exception as exc:
            raise RuntimeError(
                f"Unable to retrieve RSS feed: {exc}"
            ) from exc

        try:
            root = ElementTree.fromstring(content)
        except ElementTree.ParseError as exc:
            raise RuntimeError(
                "RSS feed contains invalid XML."
            ) from exc

        items: list[NewsItem] = []

        for item in root.findall(".//item"):
            title = item.findtext("title") or ""
            link = item.findtext("link") or ""
            description = item.findtext("description") or ""
            published = item.findtext("pubDate")

            if not title:
                continue

            items.append(
                NewsItem(
                    title=title.strip(),
                    source=source,
                    published_at=_parse_date(published),
                    url=link.strip() or "https://example.com",
                    summary=description.strip(),
                )
            )

        return items

    def fetch_api_news(
        self,
        api_url: str,
        symbol: str = "",
        timeout: int = 15,
    ) -> list[NewsItem]:
        if not api_url:
            return []

        params = {}
        if symbol:
            params["symbol"] = symbol

        final_url = api_url
        if params:
            final_url = f"{api_url}{'&' if '?' in api_url else '?'}{urlencode(params)}"

        request = Request(
            final_url,
            headers={**DEFAULT_HEADERS, "Accept": "application/json"},
        )

        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))

        articles = payload.get("articles") if isinstance(payload, dict) else payload
        if not isinstance(articles, list):
            return []

        items: list[NewsItem] = []
        for article in articles[:20]:
            if not isinstance(article, dict):
                continue
            title = str(article.get("title") or "").strip()
            if not title:
                continue
            items.append(
                NewsItem(
                    title=title,
                    source=str(article.get("source") or article.get("source_name") or "API"),
                    published_at=_parse_date(str(article.get("published_at") or article.get("publishedAt") or "")),
                    url=str(article.get("url") or "https://example.com"),
                    summary=str(article.get("summary") or article.get("description") or ""),
                    impact=_normalise_impact(str(article.get("impact") or article.get("importance") or "").strip()),
                )
            )

        return items

    def fetch_symbol_news(
        self,
        symbol: str = "EURUSD",
        sources: list[tuple[str, str]] | None = None,
        timeout: int = 15,
    ) -> list[NewsItem]:
        env_sources = os.getenv("MOILBOT_NEWS_URLS", "").strip()
        if sources is None:
            sources = []
            if env_sources:
                values = [v.strip() for v in env_sources.split(",") if v.strip()]
                for value in values:
                    source_name = os.getenv("MOILBOT_NEWS_SOURCE_NAME", "configured").strip() or "configured"
                    if value.startswith("http"):
                        sources.append((source_name, value))
            if not sources:
                sources = list(DEFAULT_RSS_SOURCES)

        api_url = os.getenv("MOILBOT_NEWS_API_URL", "").strip()
        if api_url:
            try:
                items = self.fetch_api_news(api_url, symbol=symbol, timeout=timeout)
                if items:
                    return _dedupe_news(items)[:12]
            except Exception:
                pass

        collected: list[NewsItem] = []
        for source_name, url in sources:
            try:
                items = self.fetch_rss(url, source=source_name, timeout=timeout)
                collected.extend(items)
            except Exception:
                continue

        collected.extend(self.fetch_api_news(api_url, symbol=symbol, timeout=timeout) if api_url else [])
        return _dedupe_news(collected)[:12]


def fetch_symbol_news(symbol: str = "EURUSD") -> list[NewsItem]:
    return NewsReader().fetch_symbol_news(symbol=symbol)


__all__ = [
    "DEFAULT_HEADERS",
    "DEFAULT_RSS_SOURCES",
    "NewsReader",
    "fetch_symbol_news",
]
