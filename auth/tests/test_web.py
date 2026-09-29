from auth.web import (
    SESSION_COOKIE_NAME,
    build_expired_session_cookie,
    build_session_cookie,
    get_session_token,
    parse_form,
)


class FakeHeaders:
    def __init__(self, values):
        self.values = values

    def get(self, key):
        return self.values.get(key)


def test_parse_form():
    body = b"username=moiltest01&password=TestPassword123"

    result = parse_form(body)

    assert result["username"] == "moiltest01"
    assert result["password"] == "TestPassword123"


def test_build_session_cookie():
    cookie = build_session_cookie("abc123")

    assert f"{SESSION_COOKIE_NAME}=abc123" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert "Path=/" in cookie


def test_parse_session_cookie():
    headers = FakeHeaders(
        {
            "Cookie": "other=value; moil_session=abc123"
        }
    )

    token = get_session_token(headers)

    assert token == "abc123"


def test_missing_session_cookie():
    headers = FakeHeaders({})

    assert get_session_token(headers) is None


def test_expired_session_cookie():
    cookie = build_expired_session_cookie()

    assert f"{SESSION_COOKIE_NAME}=" in cookie
    assert "Max-Age=0" in cookie
    assert "HttpOnly" in cookie