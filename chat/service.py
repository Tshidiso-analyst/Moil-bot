from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class ChatMessage:
    room: str
    author: str
    message: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ChatRoom:
    name: str
    description: str = ""


class ChatBoardService:
    def __init__(self):
        self._rooms = {
            "general": ChatRoom(name="general", description="Main strategy and coordination room."),
            "signals": ChatRoom(name="signals", description="Trade idea and confirmation discussion."),
            "news": ChatRoom(name="news", description="Macro and high-impact event room."),
        }
        self._messages = {"general": [], "signals": [], "news": []}

    def rooms(self):
        return list(self._rooms.values())

    def post_message(self, author: str, message: str, room: str = "general") -> ChatMessage:
        room_name = (room or "general").strip().lower() or "general"
        content = message.strip()
        if not content:
            raise ValueError("Message cannot be empty.")
        if room_name not in self._rooms:
            self._rooms[room_name] = ChatRoom(name=room_name, description="Custom room")
            self._messages.setdefault(room_name, [])
        entry = ChatMessage(room=room_name, author=(author or "System").strip() or "System", message=content)
        self._messages.setdefault(room_name, []).append(entry)
        return entry

    def list_messages(self, room: str = "general", limit: int = 25):
        return list(self._messages.get((room or "general").strip().lower(), []))[-limit:]


chat_service = ChatBoardService()

__all__ = ["ChatBoardService", "ChatMessage", "ChatRoom", "chat_service"]
