from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.core.cash_actions import (
    CashAction,
    CashActionRegister,
    create_cash_action_register,
)
from src.core.forecast_monitoring import (
    DirectCashForecastSnapshot,
    create_forecast_snapshot,
)
from src.core.liquidity_brief import (
    LiquidityDecisionBrief,
    build_liquidity_decision_brief,
)
from src.core.monitoring_triggers import (
    MonitoringTriggerEvaluation,
    MonitoringTriggerPolicy,
    evaluate_monitoring_triggers,
)
from src.core.recovery_engine import (
    RecoveryEvaluation,
    evaluate_recovery_plan,
)
from src.core.weekly_recovery_validation import (
    WeeklyRecoveryValidationResult,
    validate_weekly_recovery_plan,
)
from src.core.weekly_simulation import (
    WeeklyLiquiditySimulationResult,
    WeeklySimulationConfig,
    simulate_weekly_liquidity,
)
from src.demo.v2_scenarios import V2DemoScenario


class CommandCenterResult(BaseModel):
    """
    Complete deterministic V2 Command Center evidence package.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    scenario_id: str
    scenario_name: str

    snapshot: DirectCashForecastSnapshot
    simulation: WeeklyLiquiditySimulationResult

    recovery_evaluation: RecoveryEvaluation | None = None
    recovery_validation: WeeklyRecoveryValidationResult | None = None

    action_register: CashActionRegister
    monitoring: MonitoringTriggerEvaluation

    brief: LiquidityDecisionBrief


def _build_demo_actions(
    scenario: V2DemoScenario,
    *,
    created_at: datetime,
) -> CashActionRegister:
    """
    Translate only directly measurable recovery-plan cash
    commitments into demo actions.

    Percentage operating levers are not converted into invented
    dollar impacts here.
    """
    plan = scenario.recovery_plan
    constraints = scenario.recovery_constraints

    if plan is None or constraints is None:
        return create_cash_action_register(())

    actions: list[CashAction] = []

    if plan.external_liquidity > 0.0:
        actions.append(
            CashAction(
                action_id=(
                    f"{scenario.scenario_id}-"
                    "external-liquidity"
                ),
                action_type="EXTERNAL_LIQUIDITY",
                action=(
                    "Secure the external liquidity "
                    "included in the recovery plan."
                ),
                owner="CFO",
                target_date=(
                    constraints
                    .external_liquidity
                    .available_from
                ),
                expected_cash_impact=float(
                    plan.external_liquidity
                ),
                status="PLANNED",
                originating_recovery_plan_id=(
                    f"{scenario.scenario_id}-"
                    "recovery-plan"
                ),
                created_at=created_at,
            )
        )

    return create_cash_action_register(
        tuple(actions)
    )


def build_command_center(
    scenario: V2DemoScenario,
    *,
    created_at: datetime,
    simulations: int = 2000,
    seed: int = 42,
) -> CommandCenterResult:
    """
    Run the current RiskPilot V2 workflow for one scenario.

    Flow:
        forecast snapshot
        -> weekly uncertainty
        -> recovery evaluation/validation
        -> action register
        -> monitoring triggers
        -> Liquidity Decision Brief
    """
    snapshot = create_forecast_snapshot(
        scenario.forecast_input,
        snapshot_id=(
            f"{scenario.scenario_id}-snapshot"
        ),
        created_at=created_at,
        management_reserve=(
            scenario.management_reserve
        ),
    )

    simulation = simulate_weekly_liquidity(
        scenario.forecast_input,
        scenario.uncertainty_profile,
        WeeklySimulationConfig(
            simulations=simulations,
            seed=seed,
            cash_floor=(
                scenario.management_reserve
            ),
            confidence_level=(
                1.0
                - scenario
                .max_reserve_breach_probability
            ),
        ),
    )

    recovery_evaluation = None
    recovery_validation = None

    if scenario.recovery_plan is not None:
        assert (
            scenario.recovery_constraints
            is not None
        )

        recovery_evaluation = (
            evaluate_recovery_plan(
                scenario.forecast_input,
                scenario.recovery_constraints,
                scenario.recovery_plan,
                management_reserve=(
                    scenario.management_reserve
                ),
            )
        )

        recovery_validation = (
            validate_weekly_recovery_plan(
                scenario.forecast_input,
                scenario.recovery_constraints,
                scenario.recovery_plan,
                scenario.uncertainty_profile,
                management_reserve=(
                    scenario.management_reserve
                ),
                max_reserve_breach_probability=(
                    scenario
                    .max_reserve_breach_probability
                ),
                simulations=simulations,
                seed=seed,
            )
        )

    actions = _build_demo_actions(
        scenario,
        created_at=created_at,
    )

    monitoring = evaluate_monitoring_triggers(
        snapshot,
        actions,
        as_of_date=(
            scenario.forecast_input.start_date
        ),
        policy=MonitoringTriggerPolicy(
            major_forecast_variance_threshold=10000.0,
        ),
        breach_probability=float(
            simulation.shortfall_probability
        ),
        maximum_acceptable_breach_probability=(
            scenario
            .max_reserve_breach_probability
        ),
    )

    brief = build_liquidity_decision_brief(
        snapshot,
        actions,
        brief_id=(
            f"{scenario.scenario_id}-brief"
        ),
        created_at=created_at,
        recovery_evaluation=(
            recovery_evaluation
        ),
        recovery_validation=(
            recovery_validation
        ),
        monitoring_evaluation=monitoring,
    )

    return CommandCenterResult(
        scenario_id=scenario.scenario_id,
        scenario_name=scenario.name,
        snapshot=snapshot,
        simulation=simulation,
        recovery_evaluation=(
            recovery_evaluation
        ),
        recovery_validation=(
            recovery_validation
        ),
        action_register=actions,
        monitoring=monitoring,
        brief=brief,
    )
