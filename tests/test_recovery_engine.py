import pytest

from src.core.cash_events import CashEvent
from src.core.direct_cash import (
    CashCoverageAllocation,
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
    evaluate_recovery_plan,
)


def _event(
    event_id,
    *,
    date_value="2026-10-05",
    amount=10000.0,
    direction="INFLOW",
    source_type="MODELLED",
):
    return CashEvent(
        event_id=event_id,
        date=date_value,
        amount=amount,
        direction=direction,
        category="cash",
        source_type=source_type,
        status="ACTIVE",
        source_reference=f"source-{event_id}",
    )


def _constraints(
    *,
    revenue_ids=(),
    cost_ids=(),
    receivable_ids=(),
    revenue_available="2026-10-05",
    cost_available="2026-10-05",
    receivable_available="2026-10-05",
    liquidity_available="2026-10-05",
    liquidity_max=50000.0,
):
    return RecoveryConstraintSet(
        revenue_improvement=(
            RevenueImprovementConstraint(
                max_improvement_pct=20.0,
                available_from=revenue_available,
                eligible_event_ids=tuple(
                    revenue_ids
                ),
            )
        ),
        cost_reduction=(
            CostReductionConstraint(
                max_reduction_pct=20.0,
                available_from=cost_available,
                eligible_event_ids=tuple(
                    cost_ids
                ),
            )
        ),
        receivable_acceleration=(
            ReceivableAccelerationConstraint(
                max_acceleration_days=30,
                available_from=(
                    receivable_available
                ),
                eligible_event_ids=tuple(
                    receivable_ids
                ),
            )
        ),
        external_liquidity=(
            ExternalLiquidityConstraint(
                max_amount=liquidity_max,
                available_from=(
                    liquidity_available
                ),
            )
        ),
    )


def _input(
    *,
    opening_cash=50000.0,
    events=(),
    allocations=(),
):
    return DirectCashForecastInput(
        start_date="2026-10-05",
        opening_cash=opening_cash,
        events=tuple(events),
        coverage_allocations=tuple(
            allocations
        ),
    )


def test_revenue_and_cost_actions_change_only_eligible_cash():
    forecast_input = _input(
        events=(
            _event(
                "revenue-001",
                amount=10000.0,
            ),
            _event(
                "cost-001",
                amount=10000.0,
                direction="OUTFLOW",
            ),
        )
    )

    result = evaluate_recovery_plan(
        forecast_input,
        _constraints(
            revenue_ids=("revenue-001",),
            cost_ids=("cost-001",),
        ),
        RecoveryPlan(
            revenue_improvement_pct=10.0,
            cost_reduction_pct=20.0,
        ),
        management_reserve=0.0,
    )

    assert result.baseline_min_cash == 50000.0
    assert result.operating_min_cash == 53000.0
    assert result.resulting_min_cash == 53000.0

    assert set(result.changed_event_ids) == {
        "revenue-001",
        "cost-001",
    }


def test_revenue_action_respects_availability_date():
    forecast_input = _input(
        events=(
            _event(
                "revenue-001",
                date_value="2026-10-05",
                amount=10000.0,
            ),
        )
    )

    result = evaluate_recovery_plan(
        forecast_input,
        _constraints(
            revenue_ids=("revenue-001",),
            revenue_available="2026-10-12",
        ),
        RecoveryPlan(
            revenue_improvement_pct=20.0,
        ),
        management_reserve=0.0,
    )

    assert result.operating_min_cash == 60000.0
    assert result.changed_event_ids == ()


def test_receivable_acceleration_moves_committed_cash_earlier():
    forecast_input = _input(
        events=(
            _event(
                "invoice-001",
                date_value="2026-10-19",
                amount=10000.0,
                source_type="COMMITTED",
            ),
        )
    )

    result = evaluate_recovery_plan(
        forecast_input,
        _constraints(
            receivable_ids=("invoice-001",),
        ),
        RecoveryPlan(
            receivable_acceleration_days=7,
        ),
        management_reserve=0.0,
    )

    assert result.weekly_closing_cash[0] == 50000.0
    assert result.weekly_closing_cash[1] == 60000.0

    assert result.changed_event_ids == (
        "invoice-001",
    )


def test_receivable_cannot_accelerate_before_lever_available():
    forecast_input = _input(
        events=(
            _event(
                "invoice-001",
                date_value="2026-10-19",
                amount=10000.0,
                source_type="COMMITTED",
            ),
        )
    )

    result = evaluate_recovery_plan(
        forecast_input,
        _constraints(
            receivable_ids=("invoice-001",),
            receivable_available="2026-10-15",
        ),
        RecoveryPlan(
            receivable_acceleration_days=30,
        ),
        management_reserve=0.0,
    )

    assert result.weekly_closing_cash[0] == 50000.0
    assert result.weekly_closing_cash[1] == 60000.0


def test_late_external_liquidity_cannot_repair_earlier_breach():
    forecast_input = _input(
        opening_cash=20000.0,
        events=(
            _event(
                "payment-001",
                amount=15000.0,
                direction="OUTFLOW",
            ),
        ),
    )

    result = evaluate_recovery_plan(
        forecast_input,
        _constraints(
            cost_ids=("payment-001",),
            liquidity_available="2026-10-12",
        ),
        RecoveryPlan(
            external_liquidity=20000.0,
        ),
        management_reserve=10000.0,
    )

    assert result.external_liquidity_week == 2
    assert result.weekly_closing_cash[0] == 5000.0
    assert result.weekly_closing_cash[1] == 25000.0

    assert result.resulting_min_cash == 5000.0
    assert result.first_reserve_breach_week == 1
    assert result.remaining_reserve_gap == 5000.0
    assert result.feasible is False


def test_timely_external_liquidity_can_restore_reserve():
    forecast_input = _input(
        opening_cash=20000.0,
        events=(
            _event(
                "payment-001",
                amount=15000.0,
                direction="OUTFLOW",
            ),
        ),
    )

    result = evaluate_recovery_plan(
        forecast_input,
        _constraints(
            liquidity_available="2026-10-05",
        ),
        RecoveryPlan(
            external_liquidity=10000.0,
        ),
        management_reserve=10000.0,
    )

    assert result.external_liquidity_week == 1
    assert result.resulting_min_cash == 15000.0
    assert result.first_reserve_breach_week is None
    assert result.remaining_reserve_gap == 0.0
    assert result.feasible is True


def test_external_liquidity_after_horizon_has_no_effect():
    forecast_input = _input(
        opening_cash=5000.0,
    )

    result = evaluate_recovery_plan(
        forecast_input,
        _constraints(
            liquidity_available="2027-01-04",
        ),
        RecoveryPlan(
            external_liquidity=10000.0,
        ),
        management_reserve=10000.0,
    )

    assert result.external_liquidity_week is None
    assert result.resulting_min_cash == 5000.0
    assert result.feasible is False


def test_disabled_lever_is_rejected():
    constraints = _constraints(
        revenue_ids=("revenue-001",),
    )

    constraints = constraints.model_copy(
        update={
            "revenue_improvement":
                constraints.revenue_improvement.model_copy(
                    update={"enabled": False}
                )
        }
    )

    with pytest.raises(
        ValueError,
        match="disabled",
    ):
        evaluate_recovery_plan(
            _input(
                events=(
                    _event("revenue-001"),
                )
            ),
            constraints,
            RecoveryPlan(
                revenue_improvement_pct=5.0,
            ),
            management_reserve=0.0,
        )


def test_plan_cannot_exceed_management_maximum():
    with pytest.raises(
        ValueError,
        match="exceeds",
    ):
        evaluate_recovery_plan(
            _input(
                events=(
                    _event("revenue-001"),
                )
            ),
            _constraints(
                revenue_ids=("revenue-001",),
            ),
            RecoveryPlan(
                revenue_improvement_pct=25.0,
            ),
            management_reserve=0.0,
        )


def test_positive_event_lever_requires_eligible_events():
    with pytest.raises(
        ValueError,
        match="no eligible cash events",
    ):
        evaluate_recovery_plan(
            _input(),
            _constraints(),
            RecoveryPlan(
                revenue_improvement_pct=5.0,
            ),
            management_reserve=0.0,
        )


def test_recovery_does_not_mutate_base_input():
    event = _event(
        "revenue-001",
        amount=10000.0,
    )

    forecast_input = _input(
        events=(event,)
    )

    before = forecast_input.model_dump(
        mode="json"
    )

    evaluate_recovery_plan(
        forecast_input,
        _constraints(
            revenue_ids=("revenue-001",),
        ),
        RecoveryPlan(
            revenue_improvement_pct=10.0,
        ),
        management_reserve=0.0,
    )

    assert (
        forecast_input.model_dump(mode="json")
        == before
    )


def test_revenue_improvement_preserves_explicit_coverage():
    committed = _event(
        "invoice-001",
        amount=26000.0,
        source_type="COMMITTED",
    )

    modelled = _event(
        "model-001",
        amount=40000.0,
    )

    allocation = CashCoverageAllocation(
        coverage_id="coverage-001",
        committed_event_id="invoice-001",
        modelled_event_id="model-001",
        amount=26000.0,
        source_reference="manual-match",
    )

    result = evaluate_recovery_plan(
        _input(
            events=(
                committed,
                modelled,
            ),
            allocations=(
                allocation,
            ),
        ),
        _constraints(
            revenue_ids=("model-001",),
        ),
        RecoveryPlan(
            revenue_improvement_pct=10.0,
        ),
        management_reserve=0.0,
    )

    # Baseline total cash contribution:
    # 26k committed + 14k residual = 40k.
    assert result.baseline_min_cash == 90000.0

    # Improved model total:
    # 44k model estimate - 26k explicit coverage
    # = 18k residual, plus 26k committed = 44k.
    assert result.operating_min_cash == 94000.0


def test_evaluation_round_trips_deterministically():
    result = evaluate_recovery_plan(
        _input(
            events=(
                _event(
                    "revenue-001",
                    amount=1000.0,
                ),
            )
        ),
        _constraints(
            revenue_ids=("revenue-001",),
        ),
        RecoveryPlan(
            revenue_improvement_pct=5.0,
        ),
        management_reserve=25000.0,
    )

    payload = result.model_dump(
        mode="json"
    )

    restored = (
        type(result)
        .model_validate(payload)
    )

    assert restored == result
