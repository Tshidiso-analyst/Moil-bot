from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
from pathlib import Path


@dataclass
class StrategyRule:
    rule_id: str
    name: str
    description: str
    conditions: list[str]
    actions: list[str]
    version: int = 1
    active: bool = True
    created_at: str = ""


class RuleStore:
    def __init__(self, path: str = "knowledge/rules/rules.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []

        with self.path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _save(self, rules: list[dict]) -> None:
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(rules, file, indent=2, ensure_ascii=False)

    def create_rule(
        self,
        rule_id: str,
        name: str,
        description: str,
        conditions: list[str],
        actions: list[str],
    ) -> StrategyRule:
        rules = self._load()

        versions = [
            rule["version"]
            for rule in rules
            if rule["rule_id"] == rule_id
        ]

        next_version = max(versions, default=0) + 1

        rule = StrategyRule(
            rule_id=rule_id,
            name=name,
            description=description,
            conditions=conditions,
            actions=actions,
            version=next_version,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        rules.append(asdict(rule))
        self._save(rules)

        return rule

    def get_versions(self, rule_id: str) -> list[dict]:
        return [
            rule
            for rule in self._load()
            if rule["rule_id"] == rule_id
        ]
