from __future__ import annotations

from pydantic import BaseModel, Field

from src.scenarios.engine import (
    ScenarioContext,
    ScenarioInput,
    run_scenario_from_context,
)


class RecoveryOptimizerConfig(BaseModel):
    target_min_cash: float = Field(
        default=0.0,
        ge=0.0,
    )

    max_revenue_improvement_pct: int = Field(
        default=20,
        ge=0,
        le=50,
    )

    max_cost_reduction_pct: int = Field(
        default=15,
        ge=0,
        le=50,
    )

    max_receivable_acceleration_days: int = Field(
        default=90,
        ge=0,
        le=180,
    )

    max_external_liquidity: float = Field(
        default=50000.0,
        ge=0.0,
    )

    revenue_step_pct: int = Field(
        default=1,
        ge=1,
        le=10,
    )

    cost_step_pct: int = Field(
        default=1,
        ge=1,
        le=10,
    )

    receivable_step_days: int = Field(
        default=1,
        ge=1,
        le=30,
    )


class RecoveryOption(BaseModel):
    feasible: bool

    revenue_improvement_pct: float
    cost_reduction_pct: float
    receivable_acceleration_days: int

    required_external_liquidity: float
    external_liquidity: float

    operating_min_cash: float
    resulting_min_cash: float
    resulting_end_cash: float
    reserve_margin: float

    operational_disruption_score: float
    total_intervention_score: float
    maximum_lever_utilisation: float


class RecoveryOptimizationResult(BaseModel):
    target_min_cash: float

    stressed_min_cash: float
    stressed_end_cash: float
    initial_reserve_gap: float

    feasible: bool
    candidates_evaluated: int

    recommended: RecoveryOption | None

    lowest_external_liquidity: RecoveryOption | None
    lowest_operational_disruption: RecoveryOption | None
    no_external_liquidity: RecoveryOption | None

    best_effort: RecoveryOption


def _integer_grid(
    maximum: int,
    step: int,
) -> list[int]:
    if maximum <= 0:
        return [0]

    values = list(
        range(
            0,
            maximum + 1,
            step,
        )
    )

    if values[-1] != maximum:
        values.append(maximum)

    return values


def _normalised_score(
    value: float,
    maximum: float,
) -> float:
    if maximum <= 0:
        return 0.0

    return min(
        1.0,
        max(
            0.0,
            value / maximum,
        ),
    )


def _scores(
    revenue_pct: float,
    cost_pct: float,
    acceleration_days: int,
    external_liquidity: float,
    config: RecoveryOptimizerConfig,
    maximum_acceleration: int,
) -> tuple[float, float]:
    operational_parts: list[float] = []

    if config.max_revenue_improvement_pct > 0:
        operational_parts.append(
            _normalised_score(
                revenue_pct,
                config.max_revenue_improvement_pct,
            )
        )

    if config.max_cost_reduction_pct > 0:
        operational_parts.append(
            _normalised_score(
                cost_pct,
                config.max_cost_reduction_pct,
            )
        )

    if maximum_acceleration > 0:
        operational_parts.append(
            _normalised_score(
                acceleration_days,
                maximum_acceleration,
            )
        )

    operational_score = (
        100.0
        * sum(operational_parts)
        / len(operational_parts)
        if operational_parts
        else 0.0
    )

    total_parts = list(
        operational_parts
    )

    if config.max_external_liquidity > 0:
        total_parts.append(
            _normalised_score(
                external_liquidity,
                config.max_external_liquidity,
            )
        )

    total_score = (
        100.0
        * sum(total_parts)
        / len(total_parts)
        if total_parts
        else 0.0
    )

    return (
        float(operational_score),
        float(total_score),
    )


def _signature(
    option: RecoveryOption,
) -> tuple[float, float, int, float]:
    return (
        option.revenue_improvement_pct,
        option.cost_reduction_pct,
        option.receivable_acceleration_days,
        round(
            option.external_liquidity,
            6,
        ),
    )


def optimize_recovery_from_context(
    context: ScenarioContext,
    scenario: ScenarioInput,
    config: RecoveryOptimizerConfig,
) -> RecoveryOptimizationResult:
    if scenario.horizon != context.horizon:
        raise ValueError(
            "Recovery scenario horizon does not match "
            "prepared scenario context."
        )

    stressed = run_scenario_from_context(
        context,
        scenario,
    )

    initial_gap = max(
        0.0,
        config.target_min_cash
        - stressed.stressed_min_cash,
    )

    maximum_acceleration = min(
        scenario.receivable_delay_days,
        config.max_receivable_acceleration_days,
    )

    revenue_values = _integer_grid(
        config.max_revenue_improvement_pct,
        config.revenue_step_pct,
    )

    cost_values = _integer_grid(
        config.max_cost_reduction_pct,
        config.cost_step_pct,
    )

    acceleration_values = _integer_grid(
        maximum_acceleration,
        config.receivable_step_days,
    )

    options: list[RecoveryOption] = []

    for revenue_pct in revenue_values:
        for cost_pct in cost_values:
            for acceleration_days in acceleration_values:
                remaining_delay = max(
                    0,
                    scenario.receivable_delay_days
                    - acceleration_days,
                )

                candidate = ScenarioInput(
                    revenue_change=(
                        scenario.revenue_change
                        + revenue_pct / 100.0
                    ),
                    cost_change=(
                        scenario.cost_change
                        - cost_pct / 100.0
                    ),
                    receivable_delay_days=(
                        remaining_delay
                    ),
                    horizon=scenario.horizon,
                )

                result = run_scenario_from_context(
                    context,
                    candidate,
                )

                required_liquidity = max(
                    0.0,
                    config.target_min_cash
                    - result.stressed_min_cash,
                )

                applied_liquidity = min(
                    required_liquidity,
                    config.max_external_liquidity,
                )

                resulting_min_cash = (
                    result.stressed_min_cash
                    + applied_liquidity
                )

                resulting_end_cash = (
                    result.stressed_end_cash
                    + applied_liquidity
                )

                feasible = (
                    resulting_min_cash
                    >= config.target_min_cash - 1e-9
                )

                operational_score, total_score = (
                    _scores(
                        revenue_pct=(
                            revenue_pct
                        ),
                        cost_pct=cost_pct,
                        acceleration_days=(
                            acceleration_days
                        ),
                        external_liquidity=(
                            applied_liquidity
                        ),
                        config=config,
                        maximum_acceleration=(
                            maximum_acceleration
                        ),
                    )
                )

                lever_utilisations = [
                    _normalised_score(
                        revenue_pct,
                        config.max_revenue_improvement_pct,
                    ),
                    _normalised_score(
                        cost_pct,
                        config.max_cost_reduction_pct,
                    ),
                    _normalised_score(
                        acceleration_days,
                        maximum_acceleration,
                    ),
                    _normalised_score(
                        applied_liquidity,
                        config.max_external_liquidity,
                    ),
                ]

                maximum_lever_utilisation = max(
                    lever_utilisations,
                    default=0.0,
                )

                options.append(
                    RecoveryOption(
                        feasible=feasible,
                        revenue_improvement_pct=(
                            float(revenue_pct)
                        ),
                        cost_reduction_pct=(
                            float(cost_pct)
                        ),
                        receivable_acceleration_days=(
                            acceleration_days
                        ),
                        required_external_liquidity=(
                            float(required_liquidity)
                        ),
                        external_liquidity=(
                            float(applied_liquidity)
                        ),
                        operating_min_cash=float(
                            result.stressed_min_cash
                        ),
                        resulting_min_cash=float(
                            resulting_min_cash
                        ),
                        resulting_end_cash=float(
                            resulting_end_cash
                        ),
                        reserve_margin=float(
                            resulting_min_cash
                            - config.target_min_cash
                        ),
                        operational_disruption_score=(
                            operational_score
                        ),
                        total_intervention_score=(
                            total_score
                        ),
                        maximum_lever_utilisation=float(
                            maximum_lever_utilisation
                        ),
                    )
                )

    feasible_options = [
        option
        for option in options
        if option.feasible
    ]

    recommended = None
    lowest_external = None
    lowest_operational = None
    no_external = None

    if feasible_options:
        # Balanced recommendation:
        # minimise dependence on any single recovery lever.
        # Among equally balanced plans, prefer the smaller
        # overall intervention and then less external funding.
        recommended = min(
            feasible_options,
            key=lambda option: (
                option.maximum_lever_utilisation,
                option.total_intervention_score,
                option.external_liquidity,
            ),
        )

        lowest_external = min(
            feasible_options,
            key=lambda option: (
                option.external_liquidity,
                option.operational_disruption_score,
                option.total_intervention_score,
            ),
        )

        lowest_operational = min(
            feasible_options,
            key=lambda option: (
                option.operational_disruption_score,
                option.external_liquidity,
                option.total_intervention_score,
            ),
        )

        zero_funding_options = [
            option
            for option in feasible_options
            if option.external_liquidity <= 1e-9
        ]

        if zero_funding_options:
            no_external = min(
                zero_funding_options,
                key=lambda option: (
                    option.operational_disruption_score,
                    option.total_intervention_score,
                ),
            )

    best_effort = max(
        options,
        key=lambda option: (
            option.resulting_min_cash,
            -option.total_intervention_score,
        ),
    )

    return RecoveryOptimizationResult(
        target_min_cash=(
            config.target_min_cash
        ),
        stressed_min_cash=float(
            stressed.stressed_min_cash
        ),
        stressed_end_cash=float(
            stressed.stressed_end_cash
        ),
        initial_reserve_gap=float(
            initial_gap
        ),
        feasible=bool(
            feasible_options
        ),
        candidates_evaluated=len(
            options
        ),
        recommended=recommended,
        lowest_external_liquidity=(
            lowest_external
        ),
        lowest_operational_disruption=(
            lowest_operational
        ),
        no_external_liquidity=(
            no_external
        ),
        best_effort=best_effort,
    )
