"""Safety regression tests for independent strategy order authorization."""
from types import SimpleNamespace

import pytest

from execution.authorization import require_strategy_authorization


def approved(**changes):
    values = dict(symbol="XAUUSD", direction="bullish", setup_valid=True,
                  confirmation=True, structure_valid=True, liquidity_valid=True,
                  macro_bias_valid=True, high_impact_news=False)
    values.update(changes)
    return SimpleNamespace(**values)


def test_authorized_gold_setup():
    require_strategy_authorization(approved(), symbol="XAUUSD.a", direction="buy")


@pytest.mark.parametrize("direction", ["sideways", "", "hold", "neutral"])
def test_unknown_direction_rejected(direction):
    with pytest.raises(RuntimeError, match="Unsupported"):
        require_strategy_authorization(approved(), symbol="XAUUSD", direction=direction)


def test_direction_mismatch_rejected():
    with pytest.raises(RuntimeError, match="direction"):
        require_strategy_authorization(approved(), symbol="XAUUSD", direction="sell")


@pytest.mark.parametrize("field", ["setup_valid", "confirmation", "structure_valid",
                                   "liquidity_valid", "macro_bias_valid"])
def test_unconfirmed_strategy_rejected(field):
    with pytest.raises(RuntimeError, match="incomplete"):
        require_strategy_authorization(approved(**{field: False}), symbol="XAUUSD", direction="buy")


def test_news_uncertainty_rejected():
    with pytest.raises(RuntimeError, match="news"):
        require_strategy_authorization(approved(high_impact_news=None), symbol="XAUUSD", direction="buy")


def test_missing_assessment_rejected():
    with pytest.raises(RuntimeError, match="assessment"):
        require_strategy_authorization(None, symbol="XAUUSD", direction="buy")
