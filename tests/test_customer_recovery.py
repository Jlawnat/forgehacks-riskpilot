from datetime import date

from src.core.cash_events import (
    CashEvent,
)
from src.core.command_center import (
    build_command_center,
)
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
from src.core.weekly_uncertainty import (
    ModelledCashErrorSample,
    WeeklyUncertaintyProfile,
)
from src.demo.v2_scenarios import (
    V2DemoScenario,
)


def _profile():
    return WeeklyUncertaintyProfile(
        modelled_flow_error_samples=(
            ModelledCashErrorSample(
                inflow_error_pct=-0.10,
                outflow_error_pct=0.10,
            ),
            ModelledCashErrorSample(
                inflow_error_pct=0.0,
                outflow_error_pct=0.0,
            ),
            ModelledCashErrorSample(
                inflow_error_pct=0.10,
                outflow_error_pct=-0.05,
            ),
        )
    )


def test_customer_recovery_uses_existing_engine():
    start = date(
        2026,
        10,
        5,
    )

    scenario = V2DemoScenario(
        scenario_id="customer-test",
        name="Customer Test",
        description="Customer recovery test.",
        management_reserve=40000.0,
        max_reserve_breach_probability=0.10,
        forecast_input=(
            DirectCashForecastInput(
                start_date=start,
                opening_cash=45000.0,
                events=(
                    CashEvent(
                        event_id="receipt-model",
                        date="2026-10-06",
                        amount=10000.0,
                        direction="INFLOW",
                        category="sales",
                        source_type="MODELLED",
                        status="ACTIVE",
                        source_reference="model",
                    ),
                    CashEvent(
                        event_id="cost-model",
                        date="2026-10-07",
                        amount=20000.0,
                        direction="OUTFLOW",
                        category="cost",
                        source_type="MODELLED",
                        status="ACTIVE",
                        source_reference="model",
                    ),
                ),
            )
        ),
        uncertainty_profile=_profile(),
        recovery_constraints=(
            RecoveryConstraintSet(
                revenue_improvement=(
                    RevenueImprovementConstraint(
                        enabled=True,
                        max_improvement_pct=50.0,
                        available_from=start,
                        eligible_event_ids=(
                            "receipt-model",
                        ),
                    )
                ),
                cost_reduction=(
                    CostReductionConstraint(
                        enabled=True,
                        max_reduction_pct=50.0,
                        available_from=start,
                        eligible_event_ids=(
                            "cost-model",
                        ),
                    )
                ),
                receivable_acceleration=(
                    ReceivableAccelerationConstraint(
                        enabled=False,
                        max_acceleration_days=0,
                        available_from=start,
                    )
                ),
                external_liquidity=(
                    ExternalLiquidityConstraint(
                        enabled=True,
                        max_amount=20000.0,
                        available_from=start,
                    )
                ),
            )
        ),
        recovery_plan=(
            RecoveryPlan(
                revenue_improvement_pct=20.0,
                cost_reduction_pct=20.0,
                external_liquidity=10000.0,
            )
        ),
    )

    result = build_command_center(
        scenario,
        created_at=__import__(
            "datetime"
        ).datetime(
            2026,
            10,
            7,
            tzinfo=__import__(
                "datetime"
            ).timezone.utc,
        ),
        simulations=200,
        seed=42,
    )

    assert (
        result.recovery_evaluation
        is not None
    )

    assert (
        result.recovery_evaluation
        .resulting_min_cash
        >
        result.recovery_evaluation
        .baseline_min_cash
    )
