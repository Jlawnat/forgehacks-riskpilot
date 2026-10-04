import pytest

from src.ai.context import (
    build_risk_analyst_context,
)
from src.ai.tools import (
    business_health_snapshot,
    forecast_outlook_snapshot,
    liquidity_risk_snapshot,
    reverse_stress_snapshot,
    stress_test_snapshot,
)
from src.core.risk_policy import (
    RiskPolicy,
)
from src.ingestion.loader import (
    load_business_csv,
)
from src.ingestion.validator import (
    validate_business_data,
)


@pytest.fixture(scope="module")
def context():
    raw = load_business_csv(
        "data/demo/borderline_business.csv"
    )

    df, _ = validate_business_data(
        raw
    )

    return build_risk_analyst_context(
        df,
        RiskPolicy(
            minimum_cash_reserve=20000.0,
            max_shortfall_probability=0.05,
        ),
        horizon=3,
    )


def test_business_health_is_grounded(
    context,
):
    snapshot = business_health_snapshot(
        context
    )

    assert (
        snapshot["current_position"][
            "cash_balance"
        ]
        == pytest.approx(69000.0)
    )

    assert (
        snapshot["risk_policy"][
            "minimum_cash_reserve"
        ]
        == 20000.0
    )


def test_forecast_snapshot_uses_context(
    context,
):
    snapshot = forecast_outlook_snapshot(
        context
    )

    assert snapshot["horizon"] == 3

    assert (
        len(
            snapshot["revenue"]["forecast"]
        )
        == 3
    )

    assert (
        snapshot[
            "paired_forecast_errors_available"
        ]
        >= 3
    )


def test_liquidity_snapshot_reports_policy_risk(
    context,
):
    snapshot = liquidity_risk_snapshot(
        context
    )

    probability = (
        snapshot[
            "reserve_breach_probability"
        ]
    )

    assert 0.0 <= probability <= 1.0

    assert (
        snapshot[
            "maximum_acceptable_breach_probability"
        ]
        == pytest.approx(0.05)
    )


def test_stress_tool_returns_driver_decomposition(
    context,
):
    snapshot = stress_test_snapshot(
        context,
        revenue_change_pct=-15.0,
        cost_change_pct=10.0,
        receivable_delay_days=30,
    )

    assert (
        snapshot["results"][
            "stressed_end_cash"
        ]
        < snapshot["results"][
            "baseline_end_cash"
        ]
    )

    assert (
        len(
            snapshot[
                "peak_liquidity_drivers"
            ]
        )
        == 3
    )


def test_reverse_stress_uses_management_reserve(
    context,
):
    snapshot = reverse_stress_snapshot(
        context
    )

    assert (
        snapshot["management_reserve"]
        == pytest.approx(20000.0)
    )

    assert (
        snapshot[
            "baseline_margin_to_reserve"
        ]
        > 0
    )


from src.ai.tools import (
    recovery_options_snapshot,
    recovery_validation_snapshot,
)


def test_recovery_options_are_grounded(
    context,
):
    snapshot = recovery_options_snapshot(
        context,
        revenue_change_pct=-15.0,
        cost_change_pct=10.0,
        receivable_delay_days=30,
    )

    assert snapshot["recovery_available"]

    balanced = snapshot["balanced"]

    assert balanced is not None

    assert (
        balanced[
            "resulting_min_cash"
        ]
        >= 20000.0
    )

    assert (
        snapshot[
            "candidates_evaluated"
        ]
        > 1000
    )


def test_recovery_validation_uses_policy(
    context,
):
    snapshot = recovery_validation_snapshot(
        context,
        revenue_change_pct=-15.0,
        cost_change_pct=10.0,
        receivable_delay_days=30,
    )

    assert (
        snapshot[
            "maximum_acceptable_breach_probability"
        ]
        == pytest.approx(0.05)
    )

    assert len(snapshot["plans"]) == 3

    for plan in snapshot["plans"]:
        assert (
            0.0
            <= plan[
                "reserve_breach_probability_after_buffer"
            ]
            <= 1.0
        )

        assert (
            plan[
                "risk_adjusted_total_liquidity"
            ]
            >= 0.0
        )


def test_balanced_recovery_validation_reaches_appetite(
    context,
):
    snapshot = recovery_validation_snapshot(
        context,
        revenue_change_pct=-15.0,
        cost_change_pct=10.0,
        receivable_delay_days=30,
    )

    balanced = next(
        plan
        for plan in snapshot["plans"]
        if plan["plan"] == "Balanced"
    )

    assert (
        balanced[
            "within_appetite_after_buffer"
        ]
        is True
    )

    assert (
        balanced[
            "reserve_breach_probability_after_buffer"
        ]
        <= 0.051
    )


def test_business_health_runway_semantics_are_explicit(
    context,
):
    snapshot = business_health_snapshot(
        context
    )

    indicators = snapshot["indicators"]

    assert (
        "historical_run_rate_cash_runway_months"
        in indicators
    )

    assert (
        "cash_runway_months"
        not in indicators
    )
