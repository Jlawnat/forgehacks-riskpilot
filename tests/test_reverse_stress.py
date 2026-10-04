import pytest

from src.scenarios.engine import (
    ScenarioContext,
)

from src.scenarios.reverse_stress import (
    ReverseStressConfig,
    reverse_stress_from_context,
)


@pytest.fixture
def context():
    return ScenarioContext(
        horizon=3,
        starting_cash=50000.0,
        latest_receivables=30000.0,
        baseline_revenue=(
            40000.0,
            40000.0,
            40000.0,
        ),
        baseline_cost=(
            35000.0,
            35000.0,
            35000.0,
        ),
    )


@pytest.fixture
def config():
    return ReverseStressConfig(
        target_min_cash=40000.0,
        horizon=3,
        max_revenue_decline=0.30,
        max_cost_increase=0.30,
        max_receivable_delay_days=60,
        grid_step=0.05,
        breakpoint_tolerance=0.00001,
    )


def test_reverse_stress_baseline_state(
    context,
    config,
):
    result = reverse_stress_from_context(
        context,
        config,
    )

    # Minimum liquidity includes the current starting
    # cash position as well as the forecast trajectory.
    assert (
        result.baseline_min_cash
        == pytest.approx(50000.0)
    )

    assert (
        result.baseline_margin_to_target
        == pytest.approx(10000.0)
    )

    assert result.baseline_breached is False


def test_revenue_only_breakpoint(
    context,
    config,
):
    result = reverse_stress_from_context(
        context,
        config,
    )

    assert (
        result.revenue_decline_breakpoint
        == pytest.approx(
            0.20833,
            abs=0.0001,
        )
    )


def test_cost_only_breakpoint(
    context,
    config,
):
    result = reverse_stress_from_context(
        context,
        config,
    )

    assert (
        result.cost_increase_breakpoint
        == pytest.approx(
            0.23810,
            abs=0.0001,
        )
    )


def test_receivable_delay_breakpoint(
    context,
    config,
):
    result = reverse_stress_from_context(
        context,
        config,
    )

    # A 15-day delay leaves P1 exactly at
    # the $40k reserve. Day 16 pushes it below.
    assert (
        result.receivable_delay_breakpoint_days
        == 16
    )


def test_reverse_stress_grid_contains_survival_boundary(
    context,
    config,
):
    result = reverse_stress_from_context(
        context,
        config,
    )

    assert len(result.grid) == 49

    assert any(
        not point.breached
        for point in result.grid
    )

    assert any(
        point.breached
        for point in result.grid
    )

    assert (
        result.nearest_combined_failure
        is not None
    )

    assert (
        result.nearest_combined_failure
        .breached
        is True
    )
