from alerts.models import Evidence, TradeDecision
from alerts.rules import (
    fundamental_event_alert,
    risk_warning_alert,
    setup_qualified_alert,
    stop_loss_hit_alert,
    take_profit_hit_alert,
    thesis_invalidated_alert,
    thesis_weakening_alert,
    trade_entered_alert,
)


def make_decision():
    return TradeDecision(
        decision_id="DEC-00001",
        symbol="EURUSD",
        market="Forex",
        asset_class="forex",
        direction="BUY",
        strategy="SMC + FVG",
        timeframes=("4H", "1H", "15M"),
        decision="entered",
        entry=1.0850,
        stop_loss=1.0810,
        take_profit=1.0930,
        expected_move=0.0080,
        risk_percent=1.0,
        risk_reward=2.0,
        technical_evidence=(
            Evidence(
                category="structure",
                fact="4H structure is bullish.",
                source="technical",
            ),
        ),
        fundamental_evidence=(
            Evidence(
                category="fundamentals",
                fact="Fundamental bias supports the direction.",
                source="fundamental",
            ),
        ),
        risk_evidence=(
            Evidence(
                category="risk",
                fact="Risk is within limits.",
                source="risk",
            ),
        ),
        invalidation_conditions=(
            "1H structure becomes bearish.",
            "Stop loss is reached.",
        ),
        reason="Technical, fundamental and risk conditions were satisfied.",
    )


def test_trade_entered_alert():
    alert = trade_entered_alert(make_decision())

    assert alert.alert_type == "trade_entered"
    assert alert.severity == "info"
    assert alert.decision_id == "DEC-00001"
    assert "SMC + FVG" in alert.message


def test_setup_qualified_alert():
    alert = setup_qualified_alert(make_decision())

    assert alert.alert_type == "setup_qualified"
    assert "qualified" in alert.title.lower()
    assert "2.00" in alert.message


def test_stop_loss_alert():
    alert = stop_loss_hit_alert(
        make_decision(),
        exit_price=1.0810,
    )

    assert alert.alert_type == "stop_loss_hit"
    assert alert.severity == "warning"
    assert "1.081" in alert.message


def test_take_profit_alert():
    alert = take_profit_hit_alert(
        make_decision(),
        exit_price=1.0930,
    )

    assert alert.alert_type == "take_profit_hit"
    assert alert.severity == "info"
    assert "1.093" in alert.message


def test_fundamental_alert():
    alert = fundamental_event_alert(
        symbol="EURUSD",
        title="High Impact Event",
        message="A high-impact event may affect market volatility.",
    )

    assert alert.alert_type == "fundamental_event"
    assert alert.severity == "warning"


def test_risk_warning_alert():
    alert = risk_warning_alert(
        symbol="EURUSD",
        message="Maximum exposure limit reached.",
        decision_id="DEC-00001",
    )

    assert alert.alert_type == "risk_warning"
    assert alert.severity == "critical"
    assert alert.decision_id == "DEC-00001"


def test_thesis_weakening_alert():
    alert = thesis_weakening_alert(
        make_decision(),
        reason="1H bullish structure is weakening.",
    )

    assert alert.alert_type == "thesis_weakening"
    assert alert.severity == "warning"


def test_thesis_invalidated_alert():
    alert = thesis_invalidated_alert(
        make_decision(),
        reason="1H structure has become bearish.",
    )

    assert alert.alert_type == "thesis_invalidated"
    assert alert.severity == "critical"
