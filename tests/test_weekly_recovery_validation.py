import pytest

from src.core.cash_events import CashEvent
from src.core.direct_cash import (
    DirectCashForecastInput,
)
from src.core.recovery_constraints import (
    CostReductionConstraint,
    ExternalLiquidityConstraint,
    ReceivableAccelerationConstraint,
    RecoveryConstraintSet,
    RevenueImprovementConstraint,
)
from src.core.recovery_engine import (
    RecoveryPlan,
)
from src.core.weekly_recovery_validation import (
    validate_weekly_recovery_plan,
)
from src.core.weekly_uncertainty import (
    ModelledCashErrorSample,
    WeeklyUncertaintyProfile,
)


def _event(
    event_id,
    *,
    amount=10000.0,
    direction="INFLOW",
    source_type="MODELLED",
):
    return CashEvent(
        event_id=event_id,
        date="2026-10-05",
        amount=amount,
        direction=direction,
        category="cash",
        source_type=source_type,
        status="ACTIVE",
        source_reference=f"source-{event_id}",
    )


def _input(
    *,
    opening_cash=50000.0,
    events=(),
):
    return DirectCashForecastInput(
        start_date="2026-10-05",
        opening_cash=opening_cash,
        events=tuple(events),
    )


def _constraints(
    *,
    revenue_ids=(),
    cost_ids=(),
    max_liquidity=50000.0,
    liquidity_available="2026-10-05",
):
    return RecoveryConstraintSet(
        revenue_improvement=(
            RevenueImprovementConstraint(
                max_improvement_pct=20.0,
                available_from="2026-10-05",
                eligible_event_ids=tuple(
                    revenue_ids
                ),
            )
        ),
        cost_reduction=(
            CostReductionConstraint(
                max_reduction_pct=20.0,
                available_from="2026-10-05",
                eligible_event_ids=tuple(
                    cost_ids
                ),
            )
        ),
        receivable_acceleration=(
            ReceivableAccelerationConstraint(
                max_acceleration_days=0,
                available_from="2026-10-05",
            )
        ),
        external_liquidity=(
            ExternalLiquidityConstraint(
                max_amount=max_liquidity,
                available_from=(
                    liquidity_available
                ),
            )
        ),
    )


def _errors(*pairs):
    return tuple(
        ModelledCashErrorSample(
            inflow_error_pct=inflow,
            outflow_error_pct=outflow,
        )
        for inflow, outflow in pairs
    )


def test_deterministic_and_probabilistic_success():
    forecast_input = _input(
        opening_cash=20000.0,
        events=(
            _event(
                "cost-001",
                amount=10000.0,
                direction="OUTFLOW",
            ),
        ),
    )

    profile = WeeklyUncertaintyProfile(
        modelled_flow_error_samples=_errors(
            (0.0, 0.0),
            (0.0, 0.0),
            (0.0, 0.0),
        )
    )

    result = validate_weekly_recovery_plan(
        forecast_input,
        _constraints(
            cost_ids=("cost-001",),
        ),
        RecoveryPlan(),
        profile,
        management_reserve=5000.0,
        max_reserve_breach_probability=0.05,
        simulations=500,
        seed=42,
    )

    assert (
        result.status
        == "OPERATIONALLY_FEASIBLE_AND_PROBABILISTICALLY_ADEQUATE"
    )

    assert result.deterministic_feasible is True
    assert result.reserve_breach_probability == 0.0
    assert result.within_risk_appetite is True


def test_deterministic_success_can_be_probabilistically_inadequate():
    forecast_input = _input(
        opening_cash=11000.0,
        events=(
            _event(
                "cost-001",
                amount=10000.0,
                direction="OUTFLOW",
            ),
        ),
    )

    profile = WeeklyUncertaintyProfile(
        modelled_flow_error_samples=_errors(
            (0.0, 1.0),
            (0.0, 1.0),
            (0.0, 1.0),
        )
    )

    result = validate_weekly_recovery_plan(
        forecast_input,
        _constraints(
            cost_ids=("cost-001",),
        ),
        RecoveryPlan(),
        profile,
        management_reserve=0.0,
        max_reserve_breach_probability=0.05,
        simulations=500,
    )

    assert result.deterministic_feasible is True

    assert (
        result.status
        == "DETERMINISTICALLY_SUFFICIENT_BUT_PROBABILISTICALLY_INADEQUATE"
    )

    assert result.reserve_breach_probability == 1.0
    assert result.within_risk_appetite is False
    assert result.probability_excess == 0.95


def test_deterministic_shortfall_has_distinct_status():
    forecast_input = _input(
        opening_cash=5000.0,
        events=(
            _event(
                "payment-001",
                amount=10000.0,
                direction="OUTFLOW",
                source_type="COMMITTED",
            ),
        ),
    )

    result = validate_weekly_recovery_plan(
        forecast_input,
        _constraints(),
        RecoveryPlan(),
        WeeklyUncertaintyProfile(),
        management_reserve=0.0,
        max_reserve_breach_probability=0.05,
        simulations=500,
    )

    assert result.deterministic_feasible is False

    assert (
        result.status
        == "EXECUTABLE_ACTIONS_WITH_FINANCIAL_SHORTFALL"
    )


def test_planned_external_liquidity_is_applied_at_its_week():
    forecast_input = _input(
        opening_cash=10000.0,
        events=(
            _event(
                "payment-001",
                amount=10000.0,
                direction="OUTFLOW",
                source_type="COMMITTED",
            ),
        ),
    )

    result = validate_weekly_recovery_plan(
        forecast_input,
        _constraints(
            max_liquidity=10000.0,
            liquidity_available="2026-10-05",
        ),
        RecoveryPlan(
            external_liquidity=5000.0,
        ),
        WeeklyUncertaintyProfile(),
        management_reserve=5000.0,
        max_reserve_breach_probability=0.05,
        simulations=500,
    )

    assert result.external_liquidity_week == 1

    assert (
        result.external_liquidity_already_in_plan
        == 5000.0
    )

    assert result.reserve_breach_probability == 0.0


def test_late_liquidity_does_not_hide_early_shortfall():
    forecast_input = _input(
        opening_cash=10000.0,
        events=(
            _event(
                "payment-001",
                amount=10000.0,
                direction="OUTFLOW",
                source_type="COMMITTED",
            ),
        ),
    )

    result = validate_weekly_recovery_plan(
        forecast_input,
        _constraints(
            max_liquidity=10000.0,
            liquidity_available="2026-10-12",
        ),
        RecoveryPlan(
            external_liquidity=10000.0,
        ),
        WeeklyUncertaintyProfile(),
        management_reserve=5000.0,
        max_reserve_breach_probability=0.05,
        simulations=500,
    )

    assert result.external_liquidity_week == 2
    assert result.deterministic_feasible is False
    assert result.reserve_breach_probability == 1.0


def test_confidence_buffer_restores_risk_appetite():
    forecast_input = _input(
        opening_cash=11000.0,
        events=(
            _event(
                "cost-001",
                amount=10000.0,
                direction="OUTFLOW",
            ),
        ),
    )

    profile = WeeklyUncertaintyProfile(
        modelled_flow_error_samples=_errors(
            (0.0, 1.0),
            (0.0, 1.0),
            (0.0, 1.0),
        )
    )

    result = validate_weekly_recovery_plan(
        forecast_input,
        _constraints(
            cost_ids=("cost-001",),
        ),
        RecoveryPlan(),
        profile,
        management_reserve=0.0,
        max_reserve_breach_probability=0.05,
        simulations=500,
    )

    assert (
        result.additional_upfront_buffer_at_confidence
        == 9000.0
    )

    assert (
        result.risk_adjusted_breach_probability
        == 0.0
    )

    assert (
        result.risk_adjusted_within_risk_appetite
        is True
    )


def test_small_sample_limitations_are_preserved():
    forecast_input = _input(
        events=(
            _event("revenue-001"),
        )
    )

    profile = WeeklyUncertaintyProfile(
        modelled_flow_error_samples=_errors(
            (-0.1, 0.0),
            (0.0, 0.0),
            (0.1, 0.0),
        )
    )

    result = validate_weekly_recovery_plan(
        forecast_input,
        _constraints(
            revenue_ids=("revenue-001",),
        ),
        RecoveryPlan(),
        profile,
        management_reserve=0.0,
        max_reserve_breach_probability=0.05,
        simulations=500,
    )

    assert result.limitations
    assert "small-sample" in result.limitations[0]


@pytest.mark.parametrize(
    "value",
    [
        0.0,
        0.5,
        1.0,
        -0.01,
        True,
        False,
    ],
)
def test_invalid_risk_appetite_is_rejected(
    value,
):
    with pytest.raises(ValueError):
        validate_weekly_recovery_plan(
            _input(),
            _constraints(),
            RecoveryPlan(),
            WeeklyUncertaintyProfile(),
            management_reserve=0.0,
            max_reserve_breach_probability=value,
            simulations=500,
        )


def test_result_round_trips_deterministically():
    result = validate_weekly_recovery_plan(
        _input(),
        _constraints(),
        RecoveryPlan(),
        WeeklyUncertaintyProfile(),
        management_reserve=0.0,
        max_reserve_breach_probability=0.05,
        simulations=100,
    )

    payload = result.model_dump(
        mode="json"
    )

    restored = (
        type(result)
        .model_validate(payload)
    )

    assert restored == result
