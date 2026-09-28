from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


def read_url(url: str, timeout: int = 15) -> dict:
    """
    Read text content from a web URL.

    Returns metadata and extracted HTML text.
    """
    if not url.startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://")

    request = Request(
        url,
        headers={
            "User-Agent": "Moil-Bot-Knowledge-Engine/1.0"
        },
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
            content_type = response.headers.get("Content-Type", "")

            return {
                "url": url,
                "status": response.status,
                "content_type": content_type,
                "content": raw.decode("utf-8", errors="replace"),
            }

    except HTTPError as exc:
        raise RuntimeError(
            f"HTTP error while reading {url}: {exc.code}"
        ) from exc

    except URLError as exc:
        raise RuntimeError(
            f"Unable to read {url}: {exc.reason}"
        ) from exc
