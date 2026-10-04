from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from src.core.direct_cash import (
    DirectCashForecastInput,
)
from src.core.recovery_constraints import (
    RecoveryConstraintSet,
)
from src.core.recovery_engine import (
    RecoveryPlan,
    apply_recovery_operating_actions,
    evaluate_recovery_plan,
)
from src.core.weekly_simulation import (
    WeeklyCashInjection,
    WeeklySimulationConfig,
    simulate_weekly_liquidity,
)
from src.core.weekly_uncertainty import (
    WeeklyUncertaintyProfile,
)


WeeklyRecoveryProbabilityStatus = Literal[
    "OPERATIONALLY_FEASIBLE_AND_PROBABILISTICALLY_ADEQUATE",
    "DETERMINISTICALLY_SUFFICIENT_BUT_PROBABILISTICALLY_INADEQUATE",
    "EXECUTABLE_ACTIONS_WITH_FINANCIAL_SHORTFALL",
]


class WeeklyRecoveryValidationResult(BaseModel):
    """
    Probabilistic validation of one V2-D deterministic
    recovery plan against the 13-week uncertainty model.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    status: WeeklyRecoveryProbabilityStatus

    deterministic_feasible: bool

    management_reserve: float = Field(
        ge=0.0,
        allow_inf_nan=False,
    )

    max_acceptable_breach_probability: float = Field(
        gt=0.0,
        lt=0.5,
    )

    reserve_breach_probability: float = Field(
        ge=0.0,
        le=1.0,
    )

    within_risk_appetite: bool

    probability_excess: float = Field(
        ge=0.0,
        le=1.0,
    )

    median_min_cash: float
    p10_min_cash: float
    median_end_cash: float

    external_liquidity_week: int | None = Field(
        default=None,
        ge=1,
        le=13,
    )

    external_liquidity_already_in_plan: float = Field(
        ge=0.0,
        allow_inf_nan=False,
    )

    additional_upfront_buffer_at_confidence: float = Field(
        ge=0.0,
        allow_inf_nan=False,
    )

    risk_adjusted_breach_probability: float = Field(
        ge=0.0,
        le=1.0,
    )

    risk_adjusted_within_risk_appetite: bool

    simulations: int = Field(
        ge=100,
    )

    limitations: tuple[str, ...] = ()


def validate_weekly_recovery_plan(
    forecast_input: DirectCashForecastInput,
    constraints: RecoveryConstraintSet,
    plan: RecoveryPlan,
    uncertainty_profile: WeeklyUncertaintyProfile,
    *,
    management_reserve: float,
    max_reserve_breach_probability: float,
    simulations: int = 5000,
    seed: int = 42,
) -> WeeklyRecoveryValidationResult:
    """
    Validate one deterministic recovery plan under compatible
    weekly uncertainty evidence.

    The confidence-level buffer is an additional UPFRONT buffer.
    It is not treated as proof that a later funding source can
    repair an earlier breach.
    """
    if isinstance(
        max_reserve_breach_probability,
        bool,
    ):
        raise ValueError(
            "max_reserve_breach_probability must be "
            "numeric, not boolean."
        )

    maximum_probability = float(
        max_reserve_breach_probability
    )

    if not (
        0.0
        < maximum_probability
        < 0.5
    ):
        raise ValueError(
            "max_reserve_breach_probability must be "
            "between 0 and 0.5."
        )

    deterministic = evaluate_recovery_plan(
        forecast_input,
        constraints,
        plan,
        management_reserve=management_reserve,
    )

    adjusted_input, _ = (
        apply_recovery_operating_actions(
            forecast_input,
            constraints,
            plan,
        )
    )

    planned_injections: tuple[
        WeeklyCashInjection,
        ...,
    ] = ()

    if (
        plan.external_liquidity > 0.0
        and deterministic.external_liquidity_week
        is not None
    ):
        planned_injections = (
            WeeklyCashInjection(
                week_number=(
                    deterministic
                    .external_liquidity_week
                ),
                amount=plan.external_liquidity,
                source_reference=(
                    "recovery-plan-external-liquidity"
                ),
            ),
        )

    confidence_level = (
        1.0 - maximum_probability
    )

    simulation_config = WeeklySimulationConfig(
        simulations=simulations,
        seed=seed,
        cash_floor=management_reserve,
        confidence_level=confidence_level,
    )

    simulation = simulate_weekly_liquidity(
        adjusted_input,
        uncertainty_profile,
        simulation_config,
        cash_injections=planned_injections,
    )

    breach_probability = (
        simulation.shortfall_probability
    )

    within_appetite = (
        breach_probability
        <= maximum_probability
    )

    probability_excess = max(
        0.0,
        breach_probability
        - maximum_probability,
    )

    additional_buffer = (
        simulation
        .liquidity_buffer_at_confidence
    )

    risk_adjusted_injections = (
        planned_injections
    )

    if additional_buffer > 0.0:
        risk_adjusted_injections = (
            *planned_injections,
            WeeklyCashInjection(
                week_number=1,
                amount=additional_buffer,
                source_reference=(
                    "uncertainty-confidence-buffer"
                ),
            ),
        )

    if additional_buffer > 0.0:
        adjusted_simulation = (
            simulate_weekly_liquidity(
                adjusted_input,
                uncertainty_profile,
                simulation_config,
                cash_injections=(
                    risk_adjusted_injections
                ),
            )
        )
    else:
        adjusted_simulation = simulation

    adjusted_probability = (
        adjusted_simulation
        .shortfall_probability
    )

    adjusted_within_appetite = (
        adjusted_probability
        <= maximum_probability
    )

    if not deterministic.feasible:
        status: WeeklyRecoveryProbabilityStatus = (
            "EXECUTABLE_ACTIONS_WITH_FINANCIAL_SHORTFALL"
        )
    elif within_appetite:
        status = (
            "OPERATIONALLY_FEASIBLE_AND_PROBABILISTICALLY_ADEQUATE"
        )
    else:
        status = (
            "DETERMINISTICALLY_SUFFICIENT_BUT_PROBABILISTICALLY_INADEQUATE"
        )

    return WeeklyRecoveryValidationResult(
        status=status,
        deterministic_feasible=(
            deterministic.feasible
        ),
        management_reserve=float(
            management_reserve
        ),
        max_acceptable_breach_probability=(
            maximum_probability
        ),
        reserve_breach_probability=(
            breach_probability
        ),
        within_risk_appetite=(
            within_appetite
        ),
        probability_excess=float(
            probability_excess
        ),
        median_min_cash=(
            simulation.median_min_cash
        ),
        p10_min_cash=(
            simulation.p10_min_cash
        ),
        median_end_cash=(
            simulation.median_end_cash
        ),
        external_liquidity_week=(
            deterministic
            .external_liquidity_week
        ),
        external_liquidity_already_in_plan=float(
            plan.external_liquidity
        ),
        additional_upfront_buffer_at_confidence=float(
            additional_buffer
        ),
        risk_adjusted_breach_probability=(
            adjusted_probability
        ),
        risk_adjusted_within_risk_appetite=(
            adjusted_within_appetite
        ),
        simulations=simulation.simulations,
        limitations=simulation.limitations,
    )
