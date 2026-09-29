from http.cookies import SimpleCookie
from urllib.parse import parse_qs


SESSION_COOKIE_NAME = "moil_session"


def parse_form(body: bytes) -> dict[str, str]:
    data = parse_qs(body.decode("utf-8"), keep_blank_values=True)

    return {
        key: values[0]
        for key, values in data.items()
    }


def get_session_token(headers) -> str | None:
    cookie_header = headers.get("Cookie")

    if not cookie_header:
        return None

    cookie = SimpleCookie()
    cookie.load(cookie_header)

    morsel = cookie.get(SESSION_COOKIE_NAME)

    if morsel is None:
        return None

    return morsel.value


def build_session_cookie(token: str) -> str:
    return (
        f"{SESSION_COOKIE_NAME}={token}; "
        "HttpOnly; "
        "SameSite=Lax; "
        "Path=/"
    )


def build_expired_session_cookie() -> str:
    return (
        f"{SESSION_COOKIE_NAME}=; "
        "HttpOnly; "
        "SameSite=Lax; "
        "Path=/; "
        "Max-Age=0"
    )


def redirect_response(handler, location: str, cookie: str | None = None):
    handler.send_response(302)
    handler.send_header("Location", location)

    if cookie:
        handler.send_header("Set-Cookie", cookie)

    handler.end_headers()


def html_response(
    handler,
    html: str,
    status: int = 200,
    cookie: str | None = None,
):
    body = html.encode("utf-8")

    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))

    if cookie:
        handler.send_header("Set-Cookie", cookie)

    handler.end_headers()
    handler.wfile.write(body)