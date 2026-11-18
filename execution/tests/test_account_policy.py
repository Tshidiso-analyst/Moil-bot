from types import SimpleNamespace

import pytest

from execution.account_policy import AccountPolicy


class FakeMT5:
    ACCOUNT_TRADE_MODE_DEMO = 0
    ACCOUNT_TRADE_MODE_REAL = 2


def account(mode=0):
    return SimpleNamespace(trade_mode=mode, trade_allowed=True, trade_expert=True)


def test_disabled_by_default():
    with pytest.raises(RuntimeError, match="disabled"):
        AccountPolicy().verify(FakeMT5(), account())


def test_explicit_demo_mode_passes():
    AccountPolicy(mode="demo", execution_enabled=True).verify(FakeMT5(), account())


def test_demo_policy_blocks_real_account():
    with pytest.raises(RuntimeError, match="non-DEMO"):
        AccountPolicy(mode="demo", execution_enabled=True).verify(FakeMT5(), account(2))


def test_real_mode_requires_separate_approval():
    with pytest.raises(RuntimeError, match="separate explicit authorization"):
        AccountPolicy(mode="real", execution_enabled=True).verify(FakeMT5(), account(2))


def test_real_mode_requires_matching_real_account():
    policy = AccountPolicy(mode="real", execution_enabled=True, real_trading_approved=True)
    policy.verify(FakeMT5(), account(2))
    with pytest.raises(RuntimeError, match="unverified REAL"):
        policy.verify(FakeMT5(), account(0))


def test_kill_switch_blocks_all_modes():
    with pytest.raises(RuntimeError, match="kill switch"):
        AccountPolicy(mode="demo", execution_enabled=True, kill_switch=True).verify(FakeMT5(), account())


def test_missing_account_fails_closed():
    with pytest.raises(RuntimeError, match="unavailable"):
        AccountPolicy(mode="demo", execution_enabled=True).verify(FakeMT5(), None)
