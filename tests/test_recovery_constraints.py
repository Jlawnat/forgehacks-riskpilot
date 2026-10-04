import pytest
from pydantic import ValidationError

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
    validate_recovery_constraints,
)


def _event(
    event_id,
    *,
    source_type,
    direction,
    status="ACTIVE",
):
    return CashEvent(
        event_id=event_id,
        date="2026-10-12",
        amount=10000.0,
        direction=direction,
        category="cash",
        source_type=source_type,
        status=status,
        source_reference=f"source-{event_id}",
    )


def _forecast_input():
    return DirectCashForecastInput(
        start_date="2026-10-05",
        opening_cash=50000.0,
        events=(
            _event(
                "revenue-001",
                source_type="MODELLED",
                direction="INFLOW",
            ),
            _event(
                "cost-001",
                source_type="MODELLED",
                direction="OUTFLOW",
            ),
            _event(
                "invoice-001",
                source_type="COMMITTED",
                direction="INFLOW",
            ),
        ),
    )


def _constraints():
    return RecoveryConstraintSet(
        revenue_improvement=(
            RevenueImprovementConstraint(
                max_improvement_pct=15.0,
                available_from="2026-10-05",
                eligible_event_ids=(
                    "revenue-001",
                ),
            )
        ),
        cost_reduction=(
            CostReductionConstraint(
                max_reduction_pct=10.0,
                available_from="2026-10-05",
                eligible_event_ids=(
                    "cost-001",
                ),
            )
        ),
        receivable_acceleration=(
            ReceivableAccelerationConstraint(
                max_acceleration_days=14,
                available_from="2026-10-05",
                eligible_event_ids=(
                    "invoice-001",
                ),
            )
        ),
        external_liquidity=(
            ExternalLiquidityConstraint(
                max_amount=30000.0,
                available_from="2026-10-19",
            )
        ),
    )


def test_valid_recovery_constraints():
    validate_recovery_constraints(
        _forecast_input(),
        _constraints(),
    )


def test_constraints_are_immutable():
    constraints = _constraints()

    with pytest.raises(ValidationError):
        constraints.external_liquidity.max_amount = 1.0


def test_revenue_must_target_modelled_inflow():
    forecast = _forecast_input()

    constraints = _constraints().model_copy(
        update={
            "revenue_improvement":
                RevenueImprovementConstraint(
                    max_improvement_pct=10.0,
                    available_from="2026-10-05",
                    eligible_event_ids=(
                        "cost-001",
                    ),
                )
        }
    )

    with pytest.raises(
        ValueError,
        match="Revenue improvement",
    ):
        validate_recovery_constraints(
            forecast,
            constraints,
        )


def test_cost_reduction_must_target_modelled_outflow():
    constraints = _constraints().model_copy(
        update={
            "cost_reduction":
                CostReductionConstraint(
                    max_reduction_pct=10.0,
                    available_from="2026-10-05",
                    eligible_event_ids=(
                        "revenue-001",
                    ),
                )
        }
    )

    with pytest.raises(
        ValueError,
        match="Cost reduction",
    ):
        validate_recovery_constraints(
            _forecast_input(),
            constraints,
        )


def test_receivable_acceleration_must_target_committed_inflow():
    constraints = _constraints().model_copy(
        update={
            "receivable_acceleration":
                ReceivableAccelerationConstraint(
                    max_acceleration_days=10,
                    available_from="2026-10-05",
                    eligible_event_ids=(
                        "revenue-001",
                    ),
                )
        }
    )

    with pytest.raises(
        ValueError,
        match="Receivable acceleration",
    ):
        validate_recovery_constraints(
            _forecast_input(),
            constraints,
        )


def test_unknown_event_is_rejected():
    constraints = _constraints().model_copy(
        update={
            "revenue_improvement":
                RevenueImprovementConstraint(
                    max_improvement_pct=10.0,
                    available_from="2026-10-05",
                    eligible_event_ids=(
                        "missing-event",
                    ),
                )
        }
    )

    with pytest.raises(
        ValueError,
        match="unknown event ID",
    ):
        validate_recovery_constraints(
            _forecast_input(),
            constraints,
        )


def test_non_active_target_is_rejected():
    forecast = DirectCashForecastInput(
        start_date="2026-10-05",
        opening_cash=50000.0,
        events=(
            _event(
                "revenue-001",
                source_type="MODELLED",
                direction="INFLOW",
                status="CANCELLED",
            ),
        ),
    )

    constraints = RecoveryConstraintSet(
        revenue_improvement=(
            RevenueImprovementConstraint(
                max_improvement_pct=10.0,
                available_from="2026-10-05",
                eligible_event_ids=(
                    "revenue-001",
                ),
            )
        ),
        cost_reduction=(
            CostReductionConstraint(
                available_from="2026-10-05",
            )
        ),
        receivable_acceleration=(
            ReceivableAccelerationConstraint(
                available_from="2026-10-05",
            )
        ),
        external_liquidity=(
            ExternalLiquidityConstraint(
                available_from="2026-10-05",
            )
        ),
    )

    with pytest.raises(
        ValueError,
        match="ACTIVE",
    ):
        validate_recovery_constraints(
            forecast,
            constraints,
        )


@pytest.mark.parametrize(
    "value",
    [
        -1.0,
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_invalid_external_liquidity_is_rejected(
    value,
):
    with pytest.raises(ValidationError):
        ExternalLiquidityConstraint(
            max_amount=value,
            available_from="2026-10-05",
        )


@pytest.mark.parametrize(
    "value",
    [
        -1.0,
        100.01,
        float("nan"),
        float("inf"),
    ],
)
def test_invalid_cost_reduction_is_rejected(
    value,
):
    with pytest.raises(ValidationError):
        CostReductionConstraint(
            max_reduction_pct=value,
            available_from="2026-10-05",
        )


def test_duplicate_eligible_ids_are_rejected():
    with pytest.raises(
        ValidationError,
        match="Duplicate eligible event ID",
    ):
        RevenueImprovementConstraint(
            max_improvement_pct=10.0,
            available_from="2026-10-05",
            eligible_event_ids=(
                "revenue-001",
                "revenue-001",
            ),
        )


def test_blank_eligible_id_is_rejected():
    with pytest.raises(ValidationError):
        RevenueImprovementConstraint(
            max_improvement_pct=10.0,
            available_from="2026-10-05",
            eligible_event_ids=("   ",),
        )


def test_disabled_lever_preserves_capacity_metadata():
    constraint = ExternalLiquidityConstraint(
        enabled=False,
        max_amount=50000.0,
        available_from="2026-10-19",
    )

    assert constraint.enabled is False
    assert constraint.max_amount == 50000.0


def test_constraints_round_trip():
    constraints = _constraints()

    payload = constraints.model_dump(
        mode="json"
    )

    restored = (
        RecoveryConstraintSet
        .model_validate(payload)
    )

    assert restored == constraints
