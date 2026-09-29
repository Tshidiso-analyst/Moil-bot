from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class User:
    id: int
    full_name: str
    username: str
    email: str
    password_hash: str
    email_verified_at: datetime | None
    is_active: bool


@dataclass(frozen=True)
class Session:
    id: int
    user_id: int
    session_token_hash: str
    expires_at: datetime
    created_at: datetime
    last_seen_at: datetime
