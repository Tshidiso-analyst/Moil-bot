from datetime import datetime

import pytest

from alerts.models import AlertEvent
from alerts.store import AlertStore


def make_event():
    return AlertEvent(
        symbol="EURUSD",
        alert_type="trade_entered",
        severity="info",
        title="Trade Entered",
        message="EURUSD BUY trade entered.",
        decision_id="DEC-00001",
    )


def test_store_creates_alert():
    store = AlertStore()

    alert = store.create(
        event=make_event(),
        alert_id="ALT-00001",
        created_at=datetime.utcnow(),
    )

    assert alert.alert_id == "ALT-00001"
    assert alert.symbol == "EURUSD"
    assert store.get("ALT-00001") == alert


def test_store_rejects_duplicate_alert_id():
    store = AlertStore()

    store.create(
        event=make_event(),
        alert_id="ALT-00001",
        created_at=datetime.utcnow(),
    )

    with pytest.raises(ValueError):
        store.create(
            event=make_event(),
            alert_id="ALT-00001",
            created_at=datetime.utcnow(),
        )


def test_store_returns_all_alerts():
    store = AlertStore()

    store.create(
        event=make_event(),
        alert_id="ALT-00001",
        created_at=datetime.utcnow(),
    )

    event = AlertEvent(
        symbol="XAUUSD",
        alert_type="risk_warning",
        severity="critical",
        title="Risk Warning",
        message="Exposure limit reached.",
    )

    store.create(
        event=event,
        alert_id="ALT-00002",
        created_at=datetime.utcnow(),
    )

    assert len(store.all()) == 2


def test_store_filters_by_symbol():
    store = AlertStore()

    store.create(
        event=make_event(),
        alert_id="ALT-00001",
        created_at=datetime.utcnow(),
    )

    event = AlertEvent(
        symbol="XAUUSD",
        alert_type="risk_warning",
        severity="critical",
        title="Risk Warning",
        message="Exposure limit reached.",
    )

    store.create(
        event=event,
        alert_id="ALT-00002",
        created_at=datetime.utcnow(),
    )

    alerts = store.by_symbol("EURUSD")

    assert len(alerts) == 1
    assert alerts[0].symbol == "EURUSD"


def test_store_filters_by_status():
    store = AlertStore()

    store.create(
        event=make_event(),
        alert_id="ALT-00001",
        created_at=datetime.utcnow(),
    )

    store.create(
        event=make_event(),
        alert_id="ALT-00002",
        created_at=datetime.utcnow(),
    )

    store.acknowledge("ALT-00001")

    new_alerts = store.by_status("new")
    acknowledged = store.by_status("acknowledged")

    assert len(new_alerts) == 1
    assert len(acknowledged) == 1
    assert acknowledged[0].alert_id == "ALT-00001"


def test_store_acknowledges_alert():
    store = AlertStore()

    store.create(
        event=make_event(),
        alert_id="ALT-00001",
        created_at=datetime.utcnow(),
    )

    alert = store.acknowledge("ALT-00001")

    assert alert.status == "acknowledged"


def test_store_resolves_alert():
    store = AlertStore()

    store.create(
        event=make_event(),
        alert_id="ALT-00001",
        created_at=datetime.utcnow(),
    )

    alert = store.resolve("ALT-00001")

    assert alert.status == "resolved"


def test_store_rejects_unknown_alert():
    store = AlertStore()

    with pytest.raises(KeyError):
        store.acknowledge("DOES-NOT-EXIST")
