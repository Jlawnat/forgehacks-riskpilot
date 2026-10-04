from __future__ import annotations

from pydantic import BaseModel

from src.core.context import ForecastContext
from src.scenarios.engine import ScenarioInput
from src.scenarios.recovery_optimizer import (
    RecoveryOption,
)
from src.simulation.liquidity import (
    SimulationInput,
    simulate_liquidity_from_context,
)


class RecoveryValidationResult(BaseModel):
    plan_name: str

    reserve_breach_probability: float
    max_acceptable_breach_probability: float
    within_risk_appetite: bool

    probability_excess: float

    median_min_cash: float
    p10_min_cash: float
    median_end_cash: float

    additional_buffer_required: float
    buffer_confidence_level: float

    external_liquidity_already_in_plan: float

    risk_adjusted_total_liquidity: float
    risk_adjusted_breach_probability: float
    risk_adjusted_within_appetite: bool

    risk_adjusted_median_min_cash: float
    risk_adjusted_p10_min_cash: float


def validate_recovery_option_from_context(
    context: ForecastContext,
    base_scenario: ScenarioInput,
    option: RecoveryOption,
    plan_name: str,
    cash_floor: float,
    max_shortfall_probability: float,
    simulations: int = 5000,
    seed: int = 42,
) -> RecoveryValidationResult:
    """
    Probabilistically validate one deterministic
    recovery option.

    External liquidity is assumed to be available
    before forecast period 1, consistent with the
    deterministic recovery optimizer.
    """

    if (
        base_scenario.horizon
        != context.horizon
    ):
        raise ValueError(
            "Recovery-validation horizon does not "
            "match prepared forecast context."
        )

    if not (
        0.0
        < max_shortfall_probability
        < 0.5
    ):
        raise ValueError(
            "max_shortfall_probability must be "
            "between 0 and 0.5 for recovery validation."
        )

    remaining_delay = max(
        0,
        base_scenario.receivable_delay_days
        - option.receivable_acceleration_days,
    )

    confidence_level = (
        1.0
        - max_shortfall_probability
    )

    simulation = (
        simulate_liquidity_from_context(
            context,
            SimulationInput(
                revenue_change=(
                    base_scenario.revenue_change
                    + option.revenue_improvement_pct
                    / 100.0
                ),
                cost_change=(
                    base_scenario.cost_change
                    - option.cost_reduction_pct
                    / 100.0
                ),
                receivable_delay_days=(
                    remaining_delay
                ),
                horizon=(
                    base_scenario.horizon
                ),
                simulations=simulations,
                seed=seed,
                cash_floor=cash_floor,
                initial_liquidity_injection=(
                    option.external_liquidity
                ),
                confidence_level=(
                    confidence_level
                ),
            ),
        )
    )

    breach_probability = (
        simulation.shortfall_probability
    )

    additional_buffer = (
        simulation.liquidity_buffer_at_confidence
    )

    risk_adjusted_total_liquidity = (
        option.external_liquidity
        + additional_buffer
    )

    adjusted_simulation = (
        simulate_liquidity_from_context(
            context,
            SimulationInput(
                revenue_change=(
                    base_scenario.revenue_change
                    + option.revenue_improvement_pct
                    / 100.0
                ),
                cost_change=(
                    base_scenario.cost_change
                    - option.cost_reduction_pct
                    / 100.0
                ),
                receivable_delay_days=(
                    remaining_delay
                ),
                horizon=(
                    base_scenario.horizon
                ),
                simulations=simulations,
                seed=seed,
                cash_floor=cash_floor,
                initial_liquidity_injection=(
                    risk_adjusted_total_liquidity
                ),
                confidence_level=(
                    confidence_level
                ),
            ),
        )
    )

    probability_excess = max(
        0.0,
        breach_probability
        - max_shortfall_probability,
    )

    return RecoveryValidationResult(
        plan_name=plan_name,
        reserve_breach_probability=(
            breach_probability
        ),
        max_acceptable_breach_probability=(
            max_shortfall_probability
        ),
        within_risk_appetite=(
            breach_probability
            <= max_shortfall_probability
        ),
        probability_excess=(
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
        additional_buffer_required=(
            additional_buffer
        ),
        buffer_confidence_level=(
            confidence_level
        ),
        external_liquidity_already_in_plan=(
            option.external_liquidity
        ),
        risk_adjusted_total_liquidity=(
            risk_adjusted_total_liquidity
        ),
        risk_adjusted_breach_probability=(
            adjusted_simulation
            .shortfall_probability
        ),
        risk_adjusted_within_appetite=(
            adjusted_simulation
            .shortfall_probability
            <= max_shortfall_probability
        ),
        risk_adjusted_median_min_cash=(
            adjusted_simulation
            .median_min_cash
        ),
        risk_adjusted_p10_min_cash=(
            adjusted_simulation
            .p10_min_cash
        ),
    )
