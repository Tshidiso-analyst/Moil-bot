from dataclasses import dataclass

import pandas as pd

from execution.demo_start import DemoStartController


@dataclass
class _FakeAssessment:
    symbol: str
    direction: str
    session: str
    trend: str
    setup_valid: bool
    confirmation: bool
    reasons: list
    entry: float | None
    stop_loss: float | None
    take_profit: float | None
    risk_percent: float


class _FakeDecisionEngine:
    def __init__(self, assessment: _FakeAssessment):
        self.assessment = assessment

    def assess(self, **kwargs):
        return self.assessment


class _FakeRegistry:
    def __init__(self, rules):
        self._rules = rules

    def all_rules(self):
        return list(self._rules)


def _sample_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=5, freq="15min", tz="UTC"),
            "open": [1.1, 1.11, 1.12, 1.13, 1.14],
            "high": [1.12, 1.13, 1.14, 1.15, 1.16],
            "low": [1.09, 1.10, 1.11, 1.12, 1.13],
            "close": [1.11, 1.12, 1.13, 1.14, 1.15],
        }
    )


def test_demo_start_blocks_non_demo_account():
    controller = DemoStartController(
        registry=_FakeRegistry([]),
        decision_engine=_FakeDecisionEngine(
            _FakeAssessment(
                symbol="EURUSD",
                direction="bullish",
                session="new_york",
                trend="bullish",
                setup_valid=True,
                confirmation=True,
                reasons=[],
                entry=1.15,
                stop_loss=1.14,
                take_profit=1.17,
                risk_percent=0.5,
            )
        ),
    )
    result = controller.start(
        symbol="EURUSD",
        dataframe=_sample_frame(),
        account_mode="REAL",
    )
    assert result.allowed is False
    assert result.status == "blocked"
    assert "DEMO" in result.reason


def test_demo_start_requires_reviewed_rules():
    controller = DemoStartController(
        registry=_FakeRegistry([]),
        decision_engine=_FakeDecisionEngine(
            _FakeAssessment(
                symbol="EURUSD",
                direction="bullish",
                session="new_york",
                trend="bullish",
                setup_valid=True,
                confirmation=True,
                reasons=["ok"],
                entry=1.15,
                stop_loss=1.14,
                take_profit=1.17,
                risk_percent=0.5,
            )
        ),
    )
    result = controller.start(
        symbol="EURUSD",
        dataframe=_sample_frame(),
        account_mode="DEMO",
    )
    assert result.allowed is False
    assert "reviewed" in result.reason.lower()


def test_demo_start_dry_run_with_reviewed_rule():
    rules = [
        {
            "rule_id": "fvg_ny_1",
            "name": "NY FVG continuation",
            "direction": "bullish",
            "execution_enabled": False,
            "sources": [{"human_review_confirmed": True}],
        }
    ]
    controller = DemoStartController(
        registry=_FakeRegistry(rules),
        decision_engine=_FakeDecisionEngine(
            _FakeAssessment(
                symbol="EURUSD",
                direction="bullish",
                session="new_york",
                trend="bullish",
                setup_valid=True,
                confirmation=True,
                reasons=["FVG aligned"],
                entry=1.15,
                stop_loss=1.14,
                take_profit=1.17,
                risk_percent=0.5,
            )
        ),
    )
    result = controller.start(
        symbol="EURUSD",
        dataframe=_sample_frame(),
        account_mode="DEMO",
        allow_execution=False,
    )
    assert result.allowed is True
    assert result.status == "planned"
    assert result.dry_run is True
    assert result.rule_id == "fvg_ny_1"
    assert result.order_ticket is None


class _FakeDemoExecutor:
    def __init__(self):
        self.order = None

    def calculate_volume_for_risk(self, **kwargs):
        assert kwargs["risk_percent"] <= 1.0
        return 0.01

    def place_market_order(self, **kwargs):
        self.order = kwargs
        return {"ticket": 445566, "price": 1.15, "volume": kwargs["volume"]}


def test_demo_start_executes_only_after_separate_demo_rule_approval():
    rules = [{
        "rule_id": "fvg_ny_1",
        "name": "NY FVG continuation",
        "direction": "bullish",
        "execution_enabled": False,
        "demo_execution_enabled": True,
        "sources": [{"human_review_confirmed": True, "page": 12}],
    }]
    executor = _FakeDemoExecutor()
    controller = DemoStartController(
        registry=_FakeRegistry(rules),
        decision_engine=_FakeDecisionEngine(
            _FakeAssessment(
                symbol="EURUSD",
                direction="bullish",
                session="new_york",
                trend="bullish",
                setup_valid=True,
                confirmation=True,
                reasons=["confirmed"],
                entry=1.15,
                stop_loss=1.14,
                take_profit=1.17,
                risk_percent=0.5,
            )
        ),
    )

    result = controller.start(
        symbol="EURUSD",
        dataframe=_sample_frame(),
        account_mode="DEMO",
        allow_execution=True,
        proposed_risk_percent=0.5,
        executor=executor,
        account_balance=10000.0,
    )

    assert result.status == "executed"
    assert result.dry_run is False
    assert result.order_ticket == 445566
    assert executor.order["max_risk_amount"] == 50.0


def test_demo_start_refuses_unapproved_rule_even_when_execution_requested():
    rules = [{
        "rule_id": "fvg_ny_1",
        "name": "NY FVG continuation",
        "direction": "bullish",
        "execution_enabled": True,
        "demo_execution_enabled": False,
        "sources": [{"human_review_confirmed": True, "page": 12}],
    }]
    executor = _FakeDemoExecutor()
    controller = DemoStartController(
        registry=_FakeRegistry(rules),
        decision_engine=_FakeDecisionEngine(
            _FakeAssessment(
                symbol="EURUSD",
                direction="bullish",
                session="new_york",
                trend="bullish",
                setup_valid=True,
                confirmation=True,
                reasons=["confirmed"],
                entry=1.15,
                stop_loss=1.14,
                take_profit=1.17,
                risk_percent=0.5,
            )
        ),
    )

    result = controller.start(
        symbol="EURUSD",
        dataframe=_sample_frame(),
        account_mode="DEMO",
        allow_execution=True,
        executor=executor,
        account_balance=10000.0,
    )

    assert result.status == "blocked"
    assert executor.order is None
