from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path


@dataclass
class SourceRecord:
    source_id: str
    title: str
    source_type: str
    location: str
    description: str = ""
    added_at: str = ""


class SourceRegistry:
    def __init__(self, registry_path: str = "knowledge/registry/sources.json"):
        self.registry_path = Path(registry_path)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[dict]:
        if not self.registry_path.exists():
            return []

        with self.registry_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _save(self, records: list[dict]) -> None:
        with self.registry_path.open("w", encoding="utf-8") as file:
            json.dump(records, file, indent=2, ensure_ascii=False)

    def register(
        self,
        source_id: str,
        title: str,
        source_type: str,
        location: str,
        description: str = "",
    ) -> SourceRecord:
        records = self._load()

        if any(record["source_id"] == source_id for record in records):
            raise ValueError(f"Source already registered: {source_id}")

        record = SourceRecord(
            source_id=source_id,
            title=title,
            source_type=source_type,
            location=location,
            description=description,
            added_at=datetime.now(timezone.utc).isoformat(),
        )

        records.append(asdict(record))
        self._save(records)

        return record

    def get(self, source_id: str) -> dict | None:
        return next(
            (
                record
                for record in self._load()
                if record["source_id"] == source_id
            ),
            None,
        )

    def list_sources(self) -> list[dict]:
        return self._load()
