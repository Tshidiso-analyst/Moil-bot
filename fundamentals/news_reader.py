from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from fundamentals.models import NewsItem


DEFAULT_HEADERS = {
    "User-Agent": "Moil-Bot/1.0"
}


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


class NewsReader:
    def fetch_rss(
        self,
        url: str,
        source: str = "unknown",
        timeout: int = 10,
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

        items = []

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
                    url=link.strip(),
                    summary=description.strip(),
                )
            )

        return items
