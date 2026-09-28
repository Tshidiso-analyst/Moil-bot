from datetime import datetime

import pytest

from alerts.models import (
    Alert,
    AlertEvent,
    Evidence,
    NotificationSettings,
    TradeDecision,
    TradingViewReference,
)


def test_evidence_accepts_valid_data():
    evidence = Evidence(
        category="market_structure",
        fact="4H structure is bullish.",
        source="technical",
        impact="supporting",
    )

    assert evidence.category == "market_structure"
    assert evidence.source == "technical"
    assert evidence.impact == "supporting"


def test_evidence_rejects_invalid_source():
    with pytest.raises(ValueError):
        Evidence(
            category="market_structure",
            fact="4H structure is bullish.",
            source="unknown_source",
        )


def test_tradingview_reference_is_external():
    reference = TradingViewReference(
        symbol="EURUSD",
        timeframe="1H",
        summary="External TradingView analysis reference.",
        url="https://www.tradingview.com/",
    )

    assert reference.symbol == "EURUSD"
    assert reference.timeframe == "1H"
    assert reference.url


def test_trade_decision_supports_full_analysis():
    decision = TradeDecision(
        decision_id="DEC-00001",
        symbol="EURUSD",
        market="Forex",
        asset_class="forex",
        direction="BUY",
        strategy="SMC + FVG",
        timeframes=("4H", "1H", "15M"),
        decision="qualified",
        entry=1.0850,
        stop_loss=1.0810,
        take_profit=1.0930,
        expected_move=0.0080,
        risk_percent=1.0,
        risk_reward=2.0,
        technical_evidence=(
            Evidence(
                category="structure",
                fact="4H market structure is bullish.",
                source="technical",
            ),
            Evidence(
                category="fvg",
                fact="Bullish fair value gap identified.",
                source="technical",
            ),
        ),
        fundamental_evidence=(
            Evidence(
                category="fundamentals",
                fact="Fundamental bias is bullish.",
                source="fundamental",
            ),
        ),
        risk_evidence=(
            Evidence(
                category="risk",
                fact="Risk per trade is within configured limit.",
                source="risk",
            ),
        ),
        invalidation_conditions=(
            "1H structure becomes bearish.",
            "Stop loss is reached.",
        ),
        reason=(
            "Technical, fundamental and risk conditions "
            "satisfied the configured entry rules."
        ),
        created_at=datetime.utcnow(),
    )

    assert decision.symbol == "EURUSD"
    assert decision.direction == "BUY"
    assert decision.strategy == "SMC + FVG"
    assert decision.timeframes == ("4H", "1H", "15M")
    assert len(decision.technical_evidence) == 2
    assert len(decision.fundamental_evidence) == 1
    assert len(decision.risk_evidence) == 1
    assert decision.expected_move == 0.0080
    assert decision.risk_reward == 2.0
    assert len(decision.invalidation_conditions) == 2


def test_trade_decision_rejects_invalid_direction():
    with pytest.raises(ValueError):
        TradeDecision(
            decision_id="DEC-00002",
            symbol="EURUSD",
            market="Forex",
            asset_class="forex",
            direction="HOLD",
            strategy="SMC",
            timeframes=("4H", "1H"),
            decision="qualified",
            entry=1.0850,
            stop_loss=1.0810,
            take_profit=1.0930,
            expected_move=0.0080,
            risk_percent=1.0,
            risk_reward=2.0,
            invalidation_conditions=("Structure becomes bearish.",),
            reason="Test decision.",
        )


def test_trade_decision_requires_reason():
    with pytest.raises(ValueError):
        TradeDecision(
            decision_id="DEC-00003",
            symbol="EURUSD",
            market="Forex",
            asset_class="forex",
            direction="BUY",
            strategy="SMC",
            timeframes=("4H", "1H"),
            decision="qualified",
            entry=1.0850,
            stop_loss=1.0810,
            take_profit=1.0930,
            expected_move=0.0080,
            risk_percent=1.0,
            risk_reward=2.0,
            invalidation_conditions=("Structure becomes bearish.",),
            reason="",
        )


def test_notification_settings_can_disable_notifications():
    settings = NotificationSettings(enabled=False)

    assert settings.enabled_channels() == ()


def test_notification_settings_returns_enabled_channels():
    settings = NotificationSettings(
        enabled=True,
        in_app=True,
        email=True,
        message=False,
    )

    assert settings.enabled_channels() == ("in_app", "email")


def test_alert_can_reference_trade_decision():
    alert = Alert(
        alert_id="ALT-00001",
        symbol="EURUSD",
        alert_type="trade_entered",
        severity="info",
        title="Trade Entered",
        message="BUY position entered after qualification.",
        created_at=datetime.utcnow(),
        decision_id="DEC-00001",
    )

    assert alert.alert_type == "trade_entered"
    assert alert.decision_id == "DEC-00001"


def test_alert_event_can_reference_trade_decision():
    event = AlertEvent(
        symbol="EURUSD",
        alert_type="take_profit_hit",
        severity="info",
        title="Take Profit Hit",
        message="The configured take-profit level was reached.",
        decision_id="DEC-00001",
    )

    assert event.alert_type == "take_profit_hit"
    assert event.decision_id == "DEC-00001"
