from datetime import datetime

from backtesting.models import BacktestResult, BacktestTrade
from dashboard.adapter import DashboardAdapter
from dashboard.data import DashboardData
from dashboard.service import DashboardService
from fundamentals.models import FundamentalContext
from qualification.models import QualificationResult
from risk.account import calculate_account_risk
from risk.limits import can_open_trade
from risk.models import RiskLimits


def test_market_overview_supports_forex():
    service = DashboardService()

    result = service.create_market_overview(
        symbol="GBPUSD",
        asset_class="forex",
        price=1.35,
        structure="bullish",
        top_down_alignment="bullish",
        fundamental_bias="bullish",
    )

    assert result.symbol == "GBPUSD"
    assert result.asset_class == "forex"
    assert result.structure == "bullish"


def test_market_adapter_supports_index():
    adapter = DashboardAdapter()

    fundamentals = FundamentalContext(
        symbol="US30",
        bias="bullish",
        high_impact_events=1,
        news_count=3,
        summary="Positive signals.",
    )

    result = adapter.market_from_analysis(
        symbol="US30",
        price=45000,
        structure="bullish",
        top_down_alignment="bullish",
        fundamentals=fundamentals,
    )

    assert result.asset_class == "index"
    assert result.fundamental_bias == "bullish"


def test_market_adapter_supports_stock():
    adapter = DashboardAdapter()

    fundamentals = FundamentalContext(
        symbol="AAPL",
        bias="neutral",
        high_impact_events=0,
        news_count=2,
        summary="Neutral signals.",
    )

    result = adapter.market_from_analysis(
        symbol="AAPL",
        price=250,
        structure="neutral",
        top_down_alignment="mixed",
        fundamentals=fundamentals,
        description="Apple Inc.",
    )

    assert result.asset_class == "stock_or_other"
    assert result.symbol == "AAPL"


def test_setup_adapter():
    adapter = DashboardAdapter()

    qualification = QualificationResult(
        qualified=True,
        direction="bullish",
        score=4,
        reasons=[
            "Market structure is bullish.",
            "Top-down analysis agrees.",
        ],
    )

    result = adapter.setup_from_qualification(
        symbol="XAUUSD",
        qualification=qualification,
        entry=2500,
        stop_loss=2480,
        take_profit=2540,
        risk_reward=2.0,
    )

    assert result.symbol == "XAUUSD"
    assert result.qualified is True
    assert result.score == 4
    assert result.risk_reward == 2.0


def test_risk_adapter():
    adapter = DashboardAdapter()

    account = calculate_account_risk(
        balance=10000,
        risk_percent=1,
    )

    result = adapter.risk_from_account(
        account=account,
        open_trades=2,
        exposure_percent=2,
        daily_loss_percent=1,
    )

    assert result.balance == 10000
    assert result.risk_amount == 100
    assert result.open_trades == 2


def test_backtest_adapter():
    adapter = DashboardAdapter()

    trade = BacktestTrade(
        symbol="BTCUSD",
        direction="bullish",
        entry_time=datetime(2026, 1, 1),
        exit_time=datetime(2026, 1, 2),
        entry_price=100000,
        exit_price=100100,
        stop_loss=99900,
        take_profit=100200,
        profit=100,
        result="win",
    )

    result = BacktestResult(
        trades=[trade],
        total_profit=100,
        winning_trades=1,
        losing_trades=0,
        win_rate=100,
    )

    overview = adapter.backtest_from_result(
        symbol="BTCUSD",
        result=result,
    )

    assert overview.symbol == "BTCUSD"
    assert overview.total_trades == 1
    assert overview.winning_trades == 1
    assert overview.win_rate == 100
    assert overview.profit_factor == float("inf")


def test_dashboard_snapshot_serialization():
    service = DashboardService()

    market = service.create_market_overview(
        symbol="NAS100",
        asset_class="index",
        price=22000,
        structure="bullish",
        top_down_alignment="bullish",
        fundamental_bias="neutral",
    )

    risk = service.create_risk_overview(
        balance=10000,
        risk_percent=1,
        risk_amount=100,
        open_trades=1,
        exposure_percent=1,
        daily_loss_percent=0,
    )

    setup = service.create_setup_overview(
        symbol="NAS100",
        direction="bullish",
        qualified=True,
        score=4,
        entry=22000,
        stop_loss=21900,
        take_profit=22200,
        risk_reward=2,
    )

    snapshot = service.create_snapshot(
        market=market,
        setup=setup,
        risk=risk,
    )

    data = DashboardData.snapshot(snapshot)

    assert data["market"]["symbol"] == "NAS100"
    assert data["market"]["asset_class"] == "index"
    assert data["setup"]["qualified"] is True
    assert data["risk"]["risk_amount"] == 100
    assert data["backtest"] is None


def test_dashboard_supports_multiple_asset_classes():
    service = DashboardService()

    instruments = [
        ("GBPUSD", "forex"),
        ("US30", "index"),
        ("AAPL", "stock_or_other"),
        ("XAUUSD", "commodity"),
        ("BTCUSD", "crypto"),
    ]

    for symbol, asset_class in instruments:
        result = service.create_market_overview(
            symbol=symbol,
            asset_class=asset_class,
            price=100,
            structure="neutral",
            top_down_alignment="mixed",
            fundamental_bias="neutral",
        )

        assert result.symbol == symbol
        assert result.asset_class == asset_class


def test_dashboard_risk_data_respects_limits():
    limits = RiskLimits(
        max_risk_per_trade_percent=1.0,
        max_open_trades=3,
        max_total_exposure_percent=3.0,
        max_daily_loss_percent=5.0,
    )

    assert can_open_trade(
        limits=limits,
        current_open_trades=1,
        current_exposure_percent=1.0,
        proposed_risk_percent=1.0,
        daily_loss_percent=1.0,
    )
