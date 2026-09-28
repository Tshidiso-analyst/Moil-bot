import pytest

from qualification.engine import (
    SetupQualifier,
    calculate_risk_reward,
    create_setup_signal,
)


def test_setup_qualifies():
    result = SetupQualifier().qualify(
        structure_trend="bullish",
        top_down_alignment="bullish",
        fvg_direction="bullish",
        fundamental_bias="bullish",
    )

    assert result.qualified is True
    assert result.direction == "bullish"
    assert result.score == 4


def test_setup_does_not_qualify_with_conflicting_evidence():
    result = SetupQualifier().qualify(
        structure_trend="bullish",
        top_down_alignment="bearish",
        fvg_direction="bearish",
        fundamental_bias="bearish",
    )

    assert result.qualified is False


def test_risk_reward():
    result = calculate_risk_reward(
        entry=100,
        stop_loss=95,
        take_profit=110,
    )

    assert result == 2


def test_bullish_setup_signal():
    signal = create_setup_signal(
        symbol="EURUSDm",
        direction="bullish",
        entry=1.1000,
        stop_loss=1.0950,
        take_profit=1.1100,
    )

    assert signal.direction == "bullish"
    assert signal.risk_reward == pytest.approx(2.0)


def test_invalid_bullish_setup():
    with pytest.raises(ValueError):
        create_setup_signal(
            symbol="EURUSDm",
            direction="bullish",
            entry=1.1000,
            stop_loss=1.1050,
            take_profit=1.1100,
        )
