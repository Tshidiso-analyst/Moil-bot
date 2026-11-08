from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


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
            "analysis": ChatRoom(name="analysis", description="Market structure and setup analysis."),
        }
        self._messages = {name: [] for name in self._rooms}

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
        entry = ChatMessage(
            room=room_name,
            author=(author or "System").strip() or "System",
            message=content,
        )
        self._messages.setdefault(room_name, []).append(entry)
        return entry

    def list_messages(self, room: str = "general", limit: int = 25):
        return list(self._messages.get((room or "general").strip().lower(), []))[-limit:]

    def post_analysis(
        self,
        symbol: str,
        summary: str,
        *,
        direction: str = "neutral",
        status: str = "watch",
        reasons: list[str] | None = None,
        levels: dict[str, Any] | None = None,
        room: str = "analysis",
        author: str = "Moil Analysis",
    ) -> ChatMessage:
        """Post a readable market-analysis summary into the chatboard."""
        lines = [
            f"**{symbol.upper()}** · {direction} · {status}",
            summary.strip(),
        ]
        if levels:
            level_bits = []
            for key in ("entry", "stop_loss", "take_profit"):
                value = levels.get(key)
                if value is not None:
                    level_bits.append(f"{key}={value}")
            if level_bits:
                lines.append("Levels: " + ", ".join(level_bits))
        if reasons:
            for reason in reasons[:6]:
                lines.append(f"- {reason}")
        return self.post_message(author=author, message="\n".join(lines), room=room)


chat_service = ChatBoardService()

__all__ = ["ChatBoardService", "ChatMessage", "ChatRoom", "chat_service"]
