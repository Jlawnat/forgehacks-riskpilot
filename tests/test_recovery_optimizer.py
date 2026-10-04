import pytest

from src.scenarios.engine import (
    ScenarioContext,
    ScenarioInput,
)

from src.scenarios.recovery_optimizer import (
    RecoveryOptimizerConfig,
    optimize_recovery_from_context,
)


@pytest.fixture(scope="module")
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


@pytest.fixture(scope="module")
def stress():
    return ScenarioInput(
        revenue_change=-0.15,
        cost_change=0.10,
        receivable_delay_days=30,
        horizon=3,
    )


@pytest.fixture(scope="module")
def result(
    context,
    stress,
):
    return optimize_recovery_from_context(
        context,
        stress,
        RecoveryOptimizerConfig(
            target_min_cash=40000.0,
            max_external_liquidity=30000.0,
        ),
    )


def test_optimizer_finds_feasible_recovery(
    result,
):
    assert result.feasible
    assert result.recommended is not None

    assert (
        result.recommended.resulting_min_cash
        >= result.target_min_cash
    )


def test_recommended_plan_respects_constraints(
    result,
):
    option = result.recommended

    assert option is not None

    assert (
        option.revenue_improvement_pct
        <= 20
    )

    assert (
        option.cost_reduction_pct
        <= 15
    )

    assert (
        option.receivable_acceleration_days
        <= 30
    )

    assert (
        option.external_liquidity
        <= 30000
    )


def test_optimizer_can_find_zero_funding_plan(
    result,
):
    assert (
        result.no_external_liquidity
        is not None
    )

    assert (
        result.no_external_liquidity
        .external_liquidity
        == pytest.approx(0.0)
    )

    assert (
        result.no_external_liquidity
        .resulting_min_cash
        >= result.target_min_cash
    )


def test_optimizer_returns_named_tradeoffs(
    result,
):
    assert (
        result.lowest_external_liquidity
        is not None
    )

    assert (
        result.lowest_operational_disruption
        is not None
    )

    assert result.candidates_evaluated > 1000


def test_optimizer_reports_infeasible_when_capacity_is_too_low(
    context,
    stress,
):
    result = optimize_recovery_from_context(
        context,
        stress,
        RecoveryOptimizerConfig(
            target_min_cash=40000.0,
            max_revenue_improvement_pct=0,
            max_cost_reduction_pct=0,
            max_receivable_acceleration_days=0,
            max_external_liquidity=10000.0,
        ),
    )

    assert not result.feasible
    assert result.recommended is None

    assert (
        result.best_effort.resulting_min_cash
        < result.target_min_cash
    )

    assert (
        result.best_effort
        .required_external_liquidity
        > 10000.0
    )


def test_recommended_plan_is_balanced(
    result,
):
    option = result.recommended

    assert option is not None

    # The balanced recommendation should not simply
    # choose the zero-action / maximum-financing solution
    # when operating recovery alternatives are available.
    assert not (
        option.revenue_improvement_pct == 0
        and option.cost_reduction_pct == 0
        and option.receivable_acceleration_days == 0
        and option.external_liquidity > 0
    )

    assert (
        0.0
        <= option.maximum_lever_utilisation
        <= 1.0
    )
