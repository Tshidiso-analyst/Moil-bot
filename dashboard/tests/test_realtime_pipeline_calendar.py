from types import SimpleNamespace

import pandas as pd

from dashboard.realtime_pipeline import RealtimeTradingPipeline


class FakeStrategyEngine:
    def evaluate(self, **kwargs):
        return SimpleNamespace(
            status="research_candidate",
            top_down_alignment="bullish",
            direction="bullish",
            score=5,
            reasons=[],
            fundamental_bias="bullish",
        )


class FakeQualifier:
    def qualify(self, **kwargs):
        return SimpleNamespace(
            qualified=True,
            direction="bullish",
            score=3,
            reasons=[],
        )


class FakeGuard:
    calls = []

    def __init__(self, **kwargs):
        pass

    def evaluate(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs["high_impact_news"]:
            return SimpleNamespace(allowed=False, reason="Calendar/news gate blocked.")
        if not kwargs["macro_bias_valid"]:
            return SimpleNamespace(allowed=False, reason="Macro gate blocked.")
        return SimpleNamespace(allowed=True, reason="Risk checks passed.")


def build_pipeline(monkeypatch):
    import dashboard.realtime_pipeline as module

    frame = pd.DataFrame(
        {
            "open": [1.0] * 30,
            "high": [1.1] * 30,
            "low": [0.9] * 30,
            "close": [1.05] * 30,
        }
    )
    pipeline = RealtimeTradingPipeline()
    monkeypatch.setattr(pipeline, "_build_datasets", lambda symbol: ("EURUSD", {"M15": frame}))
    monkeypatch.setattr(module, "StrategyEngine", FakeStrategyEngine)
    monkeypatch.setattr(module, "analyse_structure", lambda frame: SimpleNamespace(trend="bullish"))
    monkeypatch.setattr(
        module,
        "analyze_market_context",
        lambda frame, timeframe: SimpleNamespace(
            fair_value_gaps=[],
            liquidity=[object()],
            session="new_york",
            trend="bullish",
            bias="bullish",
            distribution=False,
            consolidation=False,
            premium_discount="discount",
            bos=[],
            choch=[],
        ),
    )
    monkeypatch.setattr(module, "SetupQualifier", FakeQualifier)
    monkeypatch.setattr(module, "calculate_account_risk", lambda **kwargs: SimpleNamespace(risk_amount=100.0))
    FakeGuard.calls = []
    monkeypatch.setattr(module, "TradeGuard", FakeGuard)
    return pipeline


def test_pipeline_blocks_when_calendar_and_macro_bias_are_unverified(monkeypatch):
    result = build_pipeline(monkeypatch).evaluate("EURUSD", balance=10000)

    assert result.status == "rejected"
    assert result.qualified is False
    assert FakeGuard.calls[-1]["high_impact_news"] is True
    assert FakeGuard.calls[-1]["macro_bias_valid"] is False
    assert any("calendar is not verified" in reason.lower() for reason in result.reasons)


def test_pipeline_can_pass_verified_calendar_and_macro_inputs(monkeypatch):
    result = build_pipeline(monkeypatch).evaluate(
        "EURUSD",
        balance=10000,
        event_calendar_verified=True,
        high_impact_news=False,
        macro_bias_valid=True,
    )

    assert result.status == "accepted"
    assert result.qualified is True
    assert FakeGuard.calls[-1]["high_impact_news"] is False
    assert FakeGuard.calls[-1]["macro_bias_valid"] is True


def test_pipeline_blocks_when_high_impact_event_is_active(monkeypatch):
    result = build_pipeline(monkeypatch).evaluate(
        "EURUSD",
        balance=10000,
        event_calendar_verified=True,
        high_impact_news=True,
        macro_bias_valid=True,
    )

    assert result.status == "rejected"
    assert FakeGuard.calls[-1]["high_impact_news"] is True


def test_pipeline_rejects_string_calendar_verification_flags():
    pipeline = RealtimeTradingPipeline()
    with pytest.raises(ValueError, match="event_calendar_verified must be a boolean"):
        pipeline.evaluate(
            "EURUSD",
            balance=10_000,
            event_calendar_verified="false",
        )


def test_pipeline_rejects_non_boolean_macro_and_news_flags():
    pipeline = RealtimeTradingPipeline()
    with pytest.raises(ValueError, match="high_impact_news must be a boolean"):
        pipeline.evaluate(
            "EURUSD",
            balance=10_000,
            high_impact_news="false",
        )
