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
from src.core.recovery_optimizer import (
    RecoverySearchConfig,
    optimize_recovery,
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
    max_revenue=20.0,
    max_cost=20.0,
    max_acceleration=14,
    max_liquidity=50000.0,
    liquidity_available="2026-10-05",
    liquidity_enabled=True,
):
    return RecoveryConstraintSet(
        revenue_improvement=(
            RevenueImprovementConstraint(
                max_improvement_pct=max_revenue,
                available_from="2026-10-05",
                eligible_event_ids=tuple(
                    revenue_ids
                ),
            )
        ),
        cost_reduction=(
            CostReductionConstraint(
                max_reduction_pct=max_cost,
                available_from="2026-10-05",
                eligible_event_ids=tuple(
                    cost_ids
                ),
            )
        ),
        receivable_acceleration=(
            ReceivableAccelerationConstraint(
                max_acceleration_days=(
                    max_acceleration
                ),
                available_from="2026-10-05",
                eligible_event_ids=tuple(
                    receivable_ids
                ),
            )
        ),
        external_liquidity=(
            ExternalLiquidityConstraint(
                enabled=liquidity_enabled,
                max_amount=max_liquidity,
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
):
    return DirectCashForecastInput(
        start_date="2026-10-05",
        opening_cash=opening_cash,
        events=tuple(events),
    )


def _search_config():
    return RecoverySearchConfig(
        revenue_step_pct=10.0,
        cost_step_pct=10.0,
        receivable_step_days=7,
    )


def test_optimizer_finds_operating_recovery():
    forecast_input = _input(
        opening_cash=10000.0,
        events=(
            _event(
                "cost-001",
                amount=10000.0,
                direction="OUTFLOW",
            ),
        ),
    )

    result = optimize_recovery(
        forecast_input,
        _constraints(
            cost_ids=("cost-001",),
            max_cost=50.0,
            max_liquidity=0.0,
        ),
        management_reserve=5000.0,
        config=RecoverySearchConfig(
            cost_step_pct=25.0,
        ),
    )

    assert result.deterministic_status == "FEASIBLE"
    assert result.recommended is not None

    assert (
        result.recommended
        .evaluation
        .remaining_reserve_gap
        == 0.0
    )


def test_optimizer_uses_minimum_required_external_liquidity():
    forecast_input = _input(
        opening_cash=20000.0,
        events=(
            _event(
                "payment-001",
                amount=15000.0,
                direction="OUTFLOW",
                source_type="COMMITTED",
            ),
        ),
    )

    result = optimize_recovery(
        forecast_input,
        _constraints(
            max_revenue=0.0,
            max_cost=0.0,
            max_acceleration=0,
            max_liquidity=20000.0,
        ),
        management_reserve=10000.0,
        config=_search_config(),
    )

    assert result.recommended is not None

    assert (
        result.recommended
        .plan
        .external_liquidity
        == 5000.0
    )

    assert (
        result.recommended
        .minimum_external_liquidity_for_reserve
        == 5000.0
    )


def test_late_funding_cannot_create_false_feasibility():
    forecast_input = _input(
        opening_cash=20000.0,
        events=(
            _event(
                "payment-001",
                amount=15000.0,
                direction="OUTFLOW",
                source_type="COMMITTED",
            ),
        ),
    )

    result = optimize_recovery(
        forecast_input,
        _constraints(
            max_revenue=0.0,
            max_cost=0.0,
            max_acceleration=0,
            max_liquidity=50000.0,
            liquidity_available="2026-10-12",
        ),
        management_reserve=10000.0,
        config=_search_config(),
    )

    assert result.deterministic_status == "SHORTFALL"
    assert result.recommended is None

    assert (
        result.best_effort
        .evaluation
        .first_reserve_breach_week
        == 1
    )

    assert result.remaining_reserve_gap == 5000.0


def test_optimizer_reports_best_effort_shortfall():
    forecast_input = _input(
        opening_cash=10000.0,
        events=(
            _event(
                "payment-001",
                amount=20000.0,
                direction="OUTFLOW",
                source_type="COMMITTED",
            ),
        ),
    )

    result = optimize_recovery(
        forecast_input,
        _constraints(
            max_revenue=0.0,
            max_cost=0.0,
            max_acceleration=0,
            max_liquidity=5000.0,
        ),
        management_reserve=5000.0,
        config=_search_config(),
    )

    assert result.deterministic_status == "SHORTFALL"
    assert result.recommended is None
    assert result.best_attainable_min_cash == -5000.0
    assert result.remaining_reserve_gap == 10000.0


def test_optimizer_returns_named_tradeoffs():
    forecast_input = _input(
        opening_cash=10000.0,
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
        ),
    )

    result = optimize_recovery(
        forecast_input,
        _constraints(
            revenue_ids=("revenue-001",),
            cost_ids=("cost-001",),
            max_liquidity=10000.0,
        ),
        management_reserve=5000.0,
        config=_search_config(),
    )

    assert result.recommended is not None
    assert result.lowest_external_liquidity is not None
    assert result.lowest_operational_disruption is not None
    assert result.no_external_liquidity is not None


def test_no_external_option_is_none_when_funding_is_required():
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

    result = optimize_recovery(
        forecast_input,
        _constraints(
            max_revenue=0.0,
            max_cost=0.0,
            max_acceleration=0,
            max_liquidity=10000.0,
        ),
        management_reserve=5000.0,
        config=_search_config(),
    )

    assert result.recommended is not None
    assert result.no_external_liquidity is None


def test_disabled_liquidity_is_not_used():
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

    result = optimize_recovery(
        forecast_input,
        _constraints(
            max_revenue=0.0,
            max_cost=0.0,
            max_acceleration=0,
            max_liquidity=50000.0,
            liquidity_enabled=False,
        ),
        management_reserve=5000.0,
        config=_search_config(),
    )

    assert result.deterministic_status == "SHORTFALL"

    assert (
        result.best_effort
        .plan
        .external_liquidity
        == 0.0
    )


def test_optimizer_respects_all_management_maxima():
    forecast_input = _input(
        opening_cash=20000.0,
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
        ),
    )

    constraints = _constraints(
        revenue_ids=("revenue-001",),
        cost_ids=("cost-001",),
        max_revenue=10.0,
        max_cost=10.0,
        max_liquidity=5000.0,
    )

    result = optimize_recovery(
        forecast_input,
        constraints,
        management_reserve=15000.0,
        config=RecoverySearchConfig(
            revenue_step_pct=5.0,
            cost_step_pct=5.0,
        ),
    )

    for candidate in (
        [
            result.recommended,
            result.best_effort,
        ]
    ):
        if candidate is None:
            continue

        assert (
            candidate.plan.revenue_improvement_pct
            <= 10.0
        )

        assert (
            candidate.plan.cost_reduction_pct
            <= 10.0
        )

        assert (
            candidate.plan.external_liquidity
            <= 5000.0
        )


def test_probabilistic_validation_is_explicitly_not_assessed():
    result = optimize_recovery(
        _input(),
        _constraints(
            max_revenue=0.0,
            max_cost=0.0,
            max_acceleration=0,
            max_liquidity=0.0,
        ),
        management_reserve=0.0,
    )

    assert (
        result.probabilistic_validation_status
        == "NOT_ASSESSED"
    )


def test_baseline_is_recommended_when_already_feasible():
    result = optimize_recovery(
        _input(
            opening_cash=50000.0,
        ),
        _constraints(
            max_revenue=0.0,
            max_cost=0.0,
            max_acceleration=0,
            max_liquidity=50000.0,
        ),
        management_reserve=10000.0,
    )

    assert result.recommended is not None

    assert (
        result.recommended.plan
        .revenue_improvement_pct
        == 0.0
    )

    assert (
        result.recommended.plan
        .cost_reduction_pct
        == 0.0
    )

    assert (
        result.recommended.plan
        .receivable_acceleration_days
        == 0
    )

    assert (
        result.recommended.plan
        .external_liquidity
        == 0.0
    )


def test_optimizer_does_not_mutate_input():
    forecast_input = _input(
        events=(
            _event(
                "revenue-001",
            ),
        )
    )

    before = forecast_input.model_dump(
        mode="json"
    )

    optimize_recovery(
        forecast_input,
        _constraints(
            revenue_ids=("revenue-001",),
        ),
        management_reserve=0.0,
        config=_search_config(),
    )

    assert (
        forecast_input.model_dump(mode="json")
        == before
    )


def test_result_round_trips_deterministically():
    result = optimize_recovery(
        _input(
            opening_cash=50000.0,
        ),
        _constraints(
            max_revenue=0.0,
            max_cost=0.0,
            max_acceleration=0,
            max_liquidity=0.0,
        ),
        management_reserve=10000.0,
    )

    payload = result.model_dump(
        mode="json"
    )

    restored = (
        type(result)
        .model_validate(payload)
    )

    assert restored == result
