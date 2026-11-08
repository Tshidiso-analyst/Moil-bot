from datetime import datetime, timezone

from fundamentals.event_risk import EconomicEvent
from fundamentals.release_analysis import EconomicReleaseAnalyzer


def event(name, actual=None, forecast=None, previous=None, currency="USD", at=None):
    return EconomicEvent(
        name=name,
        currency=currency,
        scheduled_at=at or datetime(2026, 11, 7, 13, 30, tzinfo=timezone.utc),
        impact="high",
        actual=actual,
        forecast=forecast,
        previous=previous,
        source="fixture-calendar",
    )


def test_nfp_release_groups_payrolls_unemployment_and_wages():
    result = EconomicReleaseAnalyzer().analyze([
        event("Nonfarm Payrolls", 220, 180, 150),
        event("Unemployment Rate", 4.1, 4.2, 4.3),
        event("Average Hourly Earnings MoM", 0.3, 0.3, 0.2),
    ])

    assert len(result) == 1
    release = result[0]
    assert release.release_type == "NFP"
    assert {item.category for item in release.components} == {
        "headline_payrolls", "unemployment_rate", "wage_growth"
    }
    assert release.assessment == "mixed"
    assert release.macro_bias == "unverified"
    assert release.trade_direction == "none"
    assert release.trade_approval is False


def test_cpi_distinguishes_core_headline_and_monthly_components():
    result = EconomicReleaseAnalyzer().analyze([
        event("CPI YoY", 3.2, 3.0),
        event("Core CPI YoY", 3.5, 3.4),
        event("CPI MoM", 0.2, 0.3),
    ])

    assert len(result) == 1
    categories = {item.category for item in result[0].components}
    assert categories == {"annual_inflation", "core_inflation", "monthly_inflation"}
    assert result[0].assessment == "mixed"


def test_fomc_rate_and_statement_are_reported_without_policy_guess():
    result = EconomicReleaseAnalyzer().analyze([
        event("Federal Funds Rate", 4.0, 4.0),
        event("FOMC Statement"),
        event("FOMC Press Conference"),
    ])

    release = result[0]
    assert release.release_type == "FOMC"
    assert {item.category for item in release.components} == {
        "policy_rate", "policy_statement", "press_conference"
    }
    assert release.assessment == "partial"
    assert release.macro_bias == "unverified"
    assert release.trade_approval is False


def test_missing_actual_or_forecast_is_not_treated_as_a_miss():
    release = EconomicReleaseAnalyzer().analyze([
        event("Nonfarm Payrolls", actual=200, forecast=None)
    ])[0]

    assert release.components[0].comparison == "unavailable"
    assert release.assessment == "unavailable"


def test_only_some_components_available_is_partial():
    release = EconomicReleaseAnalyzer().analyze([
        event("Nonfarm Payrolls", 200, 180),
        event("Unemployment Rate"),
    ])[0]

    assert release.assessment == "partial"


def test_all_components_above_forecast_are_described_without_directional_bias():
    release = EconomicReleaseAnalyzer().analyze([
        event("CPI YoY", 3.2, 3.0),
        event("Core CPI YoY", 3.5, 3.4),
    ])[0]

    assert release.assessment == "above_forecast"
    assert release.macro_bias == "unverified"
    assert release.trade_direction == "none"


def test_events_are_grouped_by_currency_date_and_release_type():
    events = [
        event("Nonfarm Payrolls", 200, 180),
        event("Nonfarm Payrolls", 100, 90, currency="CAD"),
        event("CPI YoY", 3.2, 3.0),
        event(
            "Unemployment Rate", 4.0, 4.1,
            at=datetime(2026, 11, 8, 13, 30, tzinfo=timezone.utc),
        ),
    ]

    results = EconomicReleaseAnalyzer().analyze(events)

    assert len(results) == 4
    assert {(item.currency, item.release_type, item.release_date.isoformat()) for item in results} == {
        ("USD", "NFP", "2026-11-07"),
        ("CAD", "NFP", "2026-11-07"),
        ("USD", "CPI", "2026-11-07"),
        ("USD", "NFP", "2026-11-08"),
    }


def test_unrelated_events_are_ignored():
    assert EconomicReleaseAnalyzer().analyze([
        event("Retail Sales", 1.2, 1.0)
    ]) == ()


def test_results_are_stably_sorted():
    results = EconomicReleaseAnalyzer().analyze([
        event("CPI YoY", 3.2, 3.0, currency="EUR"),
        event("Nonfarm Payrolls", 200, 180),
    ])

    assert [(item.currency, item.release_type) for item in results] == [
        ("EUR", "CPI"), ("USD", "NFP")
    ]


def test_above_forecast_and_in_line_components_are_mixed_not_partial():
    release = EconomicReleaseAnalyzer().analyze([
        event("CPI YoY", 3.2, 3.0),
        event("Core CPI YoY", 3.4, 3.4),
    ])[0]

    assert release.assessment == "mixed"
    assert "in_line" in release.observations[0]
    assert "above_forecast" in release.observations[0]


def test_below_forecast_and_in_line_components_are_mixed_not_partial():
    release = EconomicReleaseAnalyzer().analyze([
        event("CPI YoY", 2.8, 3.0),
        event("Core CPI YoY", 3.4, 3.4),
    ])[0]

    assert release.assessment == "mixed"
    assert "in_line" in release.observations[0]
    assert "below_forecast" in release.observations[0]
