from alerts.engine import AlertEngine, AlertDispatch
from alerts.models import AlertEvent, NotificationSettings


def make_event(
    alert_type="trade_entered",
    severity="info",
):
    return AlertEvent(
        symbol="EURUSD",
        alert_type=alert_type,
        severity=severity,
        title="Test Alert",
        message="Test alert message.",
        decision_id="DEC-00001",
    )


def test_engine_processes_trade_alert():
    engine = AlertEngine()

    dispatch = engine.process(make_event())

    assert isinstance(dispatch, AlertDispatch)
    assert dispatch.alert is not None
    assert dispatch.alert.symbol == "EURUSD"
    assert dispatch.alert.alert_type == "trade_entered"
    assert dispatch.alert.alert_id.startswith("ALT-")


def test_engine_stores_processed_alert():
    engine = AlertEngine()

    dispatch = engine.process(make_event())

    assert dispatch.alert is not None

    stored = engine.get_alert(dispatch.alert.alert_id)

    assert stored == dispatch.alert


def test_engine_sends_in_app_notification():
    engine = AlertEngine()

    dispatch = engine.process(make_event())

    assert len(dispatch.notifications) == 1
    assert dispatch.notifications[0].channel == "in_app"
    assert dispatch.notifications[0].sent is True


def test_engine_can_return_all_alerts():
    engine = AlertEngine()

    engine.process(make_event())
    engine.process(make_event())

    alerts = engine.get_all_alerts()

    assert len(alerts) == 2


def test_engine_can_acknowledge_alert():
    engine = AlertEngine()

    dispatch = engine.process(make_event())

    acknowledged = engine.acknowledge(
        dispatch.alert.alert_id
    )

    assert acknowledged.status == "acknowledged"


def test_engine_can_resolve_alert():
    engine = AlertEngine()

    dispatch = engine.process(make_event())

    resolved = engine.resolve(
        dispatch.alert.alert_id
    )

    assert resolved.status == "resolved"


def test_master_notification_switch_can_disable_alerts():
    engine = AlertEngine(
        settings=NotificationSettings(enabled=False)
    )

    dispatch = engine.process(make_event())

    assert dispatch.alert is not None
    assert dispatch.notifications == []
    assert len(engine.get_all_alerts()) == 1


def test_trade_entered_notification_can_be_disabled():
    settings = NotificationSettings(
        enabled=True,
        trade_entered=False,
    )

    engine = AlertEngine(settings=settings)

    dispatch = engine.process(
        make_event(alert_type="trade_entered")
    )

    assert dispatch.alert is not None
    assert dispatch.notifications == []
    assert len(engine.get_all_alerts()) == 1


def test_stop_loss_notification_can_be_disabled():
    settings = NotificationSettings(
        enabled=True,
        stop_loss_hit=False,
    )

    engine = AlertEngine(settings=settings)

    dispatch = engine.process(
        make_event(
            alert_type="stop_loss_hit",
            severity="warning",
        )
    )

    assert dispatch.alert is not None
    assert dispatch.notifications == []
    assert len(engine.get_all_alerts()) == 1


def test_take_profit_notification_can_be_disabled():
    settings = NotificationSettings(
        enabled=True,
        take_profit_hit=False,
    )

    engine = AlertEngine(settings=settings)

    dispatch = engine.process(
        make_event(alert_type="take_profit_hit")
    )

    assert dispatch.alert is not None
    assert dispatch.notifications == []
    assert len(engine.get_all_alerts()) == 1


def test_fundamental_notifications_can_be_disabled():
    settings = NotificationSettings(
        enabled=True,
        fundamental_events=False,
    )

    engine = AlertEngine(settings=settings)

    dispatch = engine.process(
        make_event(
            alert_type="fundamental_event",
            severity="warning",
        )
    )

    assert dispatch.alert is not None
    assert dispatch.notifications == []
    assert len(engine.get_all_alerts()) == 1


def test_risk_notifications_can_be_disabled():
    settings = NotificationSettings(
        enabled=True,
        risk_warnings=False,
    )

    engine = AlertEngine(settings=settings)

    dispatch = engine.process(
        make_event(
            alert_type="risk_warning",
            severity="critical",
        )
    )

    assert dispatch.alert is not None
    assert dispatch.notifications == []
    assert len(engine.get_all_alerts()) == 1


def test_engine_returns_new_alerts():
    engine = AlertEngine()

    dispatch = engine.process(make_event())

    new_alerts = engine.get_new_alerts()

    assert len(new_alerts) == 1
    assert new_alerts[0] == dispatch.alert


def test_engine_filters_alerts_by_symbol():
    engine = AlertEngine()

    engine.process(make_event())

    xau_event = AlertEvent(
        symbol="XAUUSD",
        alert_type="trade_entered",
        severity="info",
        title="Gold Trade",
        message="XAUUSD BUY trade entered.",
    )

    engine.process(xau_event)

    eur_alerts = engine.get_symbol_alerts("EURUSD")
    xau_alerts = engine.get_symbol_alerts("XAUUSD")

    assert len(eur_alerts) == 1
    assert len(xau_alerts) == 1


def test_engine_can_use_custom_notification_service():
    class FakeNotificationService:
        def __init__(self):
            self.sent_alert_ids = []

        def update_settings(self, settings):
            self.settings = settings

        def send(self, alert):
            self.sent_alert_ids.append(alert.alert_id)
            return []

    service = FakeNotificationService()
    engine = AlertEngine(notification_service=service)

    dispatch = engine.process(make_event())

    assert dispatch.alert is not None
    assert service.sent_alert_ids == [
        dispatch.alert.alert_id
    ]