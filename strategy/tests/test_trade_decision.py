from types import SimpleNamespace

import pandas as pd
import pytest

import strategy.trade_decision as decision_module
from strategy.trade_decision import TradeDecisionEngine


def market_data():
    return pd.DataFrame([
        {"open": 2500.0, "high": 2510.0, "low": 2490.0, "close": 2505.0},
        {"open": 2505.0, "high": 2520.0, "low": 2500.0, "close": 2515.0},
    ])


def valid_context():
    return SimpleNamespace(
        reasons=[],
        trend="bullish",
        distribution=False,
        consolidation=False,
        session="new_york",
        fair_value_gaps=[SimpleNamespace(direction="bullish")],
        bos=[{"direction": "bullish"}],
        choch=[{"direction": "bullish"}],
        liquidity=[SimpleNamespace(direction="sell_side")],
    )


def install_context(monkeypatch, context=None):
    monkeypatch.setattr(
        decision_module,
        "analyze_market_context",
        lambda dataframe: context or valid_context(),
    )


def test_assessment_exposes_confirmed_structure_liquidity_and_macro_checks(monkeypatch):
    install_context(monkeypatch)
    result = TradeDecisionEngine().assess("XAUUSD", market_data(), high_impact_news=False)
    assert result.symbol == "XAUUSD"
    assert result.setup_valid is True
    assert result.confirmation is True
    assert result.structure_valid is True
    assert result.liquidity_valid is True
    assert result.macro_bias_valid is True
    assert result.high_impact_news is False
    assert result.max_open_trades == 3
    assert result.max_trades_per_day == 10
    assert result.max_position_volume == 0.02


def test_assessment_blocks_high_impact_news(monkeypatch):
    install_context(monkeypatch)
    result = TradeDecisionEngine().assess(
        "XAUUSD", market_data(), high_impact_news=True,
    )
    assert result.high_impact_news is True
    assert result.setup_valid is False
    assert any("High-impact news" in reason for reason in result.reasons)


def test_assessment_blocks_at_ten_daily_entries(monkeypatch):
    install_context(monkeypatch)
    result = TradeDecisionEngine().assess(
        "XAUUSD", market_data(), current_daily_entries=10, high_impact_news=False,
    )
    assert result.setup_valid is False
    assert any("Daily entry limit reached" in reason for reason in result.reasons)


def test_assessment_requires_liquidity_confirmation(monkeypatch):
    context = valid_context()
    context.liquidity = []
    install_context(monkeypatch, context)
    result = TradeDecisionEngine().assess("XAUUSD", market_data(), high_impact_news=False)
    assert result.liquidity_valid is False
    assert result.setup_valid is False


def test_assessment_rejects_invalid_fundamental_bias(monkeypatch):
    install_context(monkeypatch)
    with pytest.raises(ValueError, match="fundamental_bias"):
        TradeDecisionEngine().assess(
            "XAUUSD", market_data(), fundamental_bias="strong bullish",
        )


def test_assessment_accepts_broker_alias_but_returns_canonical_symbol(monkeypatch):
    install_context(monkeypatch)
    result = TradeDecisionEngine().assess("XAUUSD.a", market_data(), high_impact_news=False)
    assert result.symbol == "XAUUSD"



def test_assessment_rejects_wrong_side_liquidity_sweep(monkeypatch):
    context = valid_context()
    context.liquidity = [SimpleNamespace(direction="buy_side")]
    install_context(monkeypatch, context)
    result = TradeDecisionEngine().assess(
        "XAUUSD", market_data(), high_impact_news=False,
    )
    assert result.liquidity_valid is False
    assert result.setup_valid is False


def test_assessment_requires_direction_aligned_bos_and_choch(monkeypatch):
    context = valid_context()
    context.choch = [{"direction": "bearish"}]
    install_context(monkeypatch, context)
    result = TradeDecisionEngine().assess(
        "XAUUSD", market_data(), high_impact_news=False,
    )
    assert result.structure_valid is False
    assert result.setup_valid is False
