from datetime import datetime, timezone

import pytest

from alerts.models import Alert, AlertEvent
from alerts.notifications import NotificationResult
from alerts.postgres_store import PostgresAlertStore


class FakeDatabase:
    def __init__(self):
        self.alerts = []
        self.deliveries = []


class FakeCursor:
    def __init__(self, database):
        self.database = database
        self.result = None
        self.results = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=()):
        sql = " ".join(query.lower().split())
        self.result = None
        self.results = []

        if sql.startswith("insert into moil_alerts"):
            values = tuple(params)
            alert_id, dedupe_key = values[0], values[9]
            duplicate = any(
                row[0] == alert_id
                or (dedupe_key is not None and row[9] == dedupe_key)
                for row in self.database.alerts
            )
            if not duplicate:
                self.database.alerts.append(values)
                self.result = values
        elif sql.startswith("select") and "where alert_id = %s" in sql:
            self.result = next(
                (row for row in self.database.alerts if row[0] == params[0]),
                None,
            )
        elif sql.startswith("select") and "where dedupe_key = %s" in sql:
            self.result = next(
                (row for row in self.database.alerts if row[9] == params[0]),
                None,
            )
        elif sql.startswith("select") and "where symbol = %s" in sql:
            self.results = [row for row in self.database.alerts if row[1] == params[0]]
        elif sql.startswith("select") and "where status = %s" in sql:
            self.results = [row for row in self.database.alerts if row[7] == params[0]]
        elif sql.startswith("select") and "from moil_alerts" in sql:
            self.results = list(self.database.alerts)
        elif sql.startswith("update moil_alerts"):
            status, alert_id = params
            for index, row in enumerate(self.database.alerts):
                if row[0] == alert_id:
                    values = list(row)
                    values[7] = status
                    self.database.alerts[index] = tuple(values)
                    self.result = tuple(values)
                    break
        elif sql.startswith("insert into moil_alert_deliveries"):
            self.database.deliveries.append(tuple(params))
        else:
            raise AssertionError(f"Unexpected SQL: {sql}")

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.results


class FakeConnection:
    def __init__(self, database):
        self.database = database

    def cursor(self):
        return FakeCursor(self.database)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def make_event(dedupe_key="event:EURUSD:1"):
    return AlertEvent(
        symbol="EURUSD",
        alert_type="fundamental_event",
        severity="warning",
        title="High impact event",
        message="Economic release is approaching.",
        decision_id="DEC-001",
        dedupe_key=dedupe_key,
    )


@pytest.fixture
def store(monkeypatch):
    import alerts.postgres_store as module

    database = FakeDatabase()
    monkeypatch.setattr(module, "get_connection", lambda: FakeConnection(database))
    return PostgresAlertStore(), database


def test_postgres_store_creates_and_retrieves_alert(store):
    repository, _database = store
    created = repository.create(make_event(), "ALT-000001", datetime.now(timezone.utc))

    assert created.alert_id == "ALT-000001"
    assert repository.get("ALT-000001") == created
    assert repository.by_dedupe_key("event:EURUSD:1") == created


def test_postgres_store_atomically_returns_existing_deduplicated_alert(store):
    repository, database = store
    created_at = datetime.now(timezone.utc)
    first = repository.create(make_event(), "ALT-000001", created_at)
    second = repository.create(make_event(), "ALT-000002", created_at)

    assert second == first
    assert len(database.alerts) == 1


def test_postgres_store_add_rejects_duplicate_alert_id(store):
    repository, _database = store
    alert = Alert(
        alert_id="ALT-000001",
        symbol="EURUSD",
        alert_type="risk_warning",
        severity="critical",
        title="Risk",
        message="Risk limit reached.",
        created_at=datetime.now(timezone.utc),
    )
    repository.add(alert)

    with pytest.raises(ValueError, match="already exists"):
        repository.add(alert)


def test_postgres_store_filters_and_updates_status(store):
    repository, _database = store
    first = repository.create(make_event(), "ALT-000001", datetime.now(timezone.utc))
    second_event = AlertEvent(
        symbol="XAUUSD",
        alert_type="risk_warning",
        severity="critical",
        title="Exposure",
        message="Exposure limit reached.",
    )
    second = repository.create(second_event, "ALT-000002", datetime.now(timezone.utc))

    assert repository.by_symbol("EURUSD") == [first]
    assert repository.by_status("new") == [first, second]
    assert repository.acknowledge(first.alert_id).status == "acknowledged"
    assert repository.resolve(second.alert_id).status == "resolved"


def test_postgres_store_records_delivery_attempts(store):
    repository, database = store
    alert = repository.create(make_event(), "ALT-000001", datetime.now(timezone.utc))
    repository.record_deliveries(
        alert,
        [NotificationResult(channel="email", sent=False, message="SMTP unavailable")],
    )

    assert database.deliveries == [
        ("ALT-000001", "email", False, "SMTP unavailable")
    ]


def test_postgres_store_rejects_unknown_status_update(store):
    repository, _database = store

    with pytest.raises(KeyError, match="not found"):
        repository.acknowledge("ALT-MISSING")
