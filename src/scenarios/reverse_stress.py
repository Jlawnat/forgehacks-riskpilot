from __future__ import annotations

from math import isclose

from pydantic import BaseModel, Field

from src.scenarios.engine import (
    ScenarioContext,
    ScenarioInput,
    run_scenario_from_context,
)


class ReverseStressConfig(BaseModel):
    target_min_cash: float = Field(
        default=0.0,
        ge=0.0,
    )

    horizon: int = Field(
        default=3,
        ge=1,
        le=12,
    )

    max_revenue_decline: float = Field(
        default=0.30,
        ge=0.0,
        le=1.0,
    )

    max_cost_increase: float = Field(
        default=0.30,
        ge=0.0,
        le=2.0,
    )

    max_receivable_delay_days: int = Field(
        default=90,
        ge=0,
        le=180,
    )

    grid_step: float = Field(
        default=0.01,
        gt=0.0,
        le=0.10,
    )

    breakpoint_tolerance: float = Field(
        default=0.0001,
        gt=0.0,
        le=0.01,
    )


class ReverseStressGridPoint(BaseModel):
    revenue_decline: float
    cost_increase: float

    min_cash: float
    margin_to_target: float

    breached: bool


class ReverseStressResult(BaseModel):
    target_min_cash: float
    horizon: int

    baseline_min_cash: float
    baseline_margin_to_target: float
    baseline_breached: bool

    revenue_decline_breakpoint: float | None
    cost_increase_breakpoint: float | None
    receivable_delay_breakpoint_days: int | None

    nearest_combined_failure: (
        ReverseStressGridPoint | None
    )

    grid: list[ReverseStressGridPoint]


def _minimum_cash(
    context: ScenarioContext,
    horizon: int,
    revenue_decline: float = 0.0,
    cost_increase: float = 0.0,
    receivable_delay_days: int = 0,
) -> float:
    result = run_scenario_from_context(
        context,
        ScenarioInput(
            revenue_change=-revenue_decline,
            cost_change=cost_increase,
            receivable_delay_days=(
                receivable_delay_days
            ),
            horizon=horizon,
        ),
    )

    return float(
        result.stressed_min_cash
    )


def _continuous_breakpoint(
    baseline_min_cash: float,
    target_min_cash: float,
    maximum: float,
    tolerance: float,
    evaluator,
) -> float | None:
    if baseline_min_cash < target_min_cash:
        return 0.0

    if maximum <= 0.0:
        return None

    maximum_cash = evaluator(
        maximum
    )

    if maximum_cash >= target_min_cash:
        return None

    low = 0.0
    high = maximum

    while (
        high - low
        > tolerance
    ):
        midpoint = (
            low + high
        ) / 2.0

        minimum_cash = evaluator(
            midpoint
        )

        if minimum_cash < target_min_cash:
            high = midpoint
        else:
            low = midpoint

    return float(high)


def _receivable_delay_breakpoint(
    context: ScenarioContext,
    config: ReverseStressConfig,
    baseline_min_cash: float,
) -> int | None:
    if (
        baseline_min_cash
        < config.target_min_cash
    ):
        return 0

    for delay_days in range(
        1,
        config.max_receivable_delay_days + 1,
    ):
        minimum_cash = _minimum_cash(
            context=context,
            horizon=config.horizon,
            receivable_delay_days=delay_days,
        )

        if (
            minimum_cash
            < config.target_min_cash
        ):
            return delay_days

    return None


def _grid_values(
    maximum: float,
    step: float,
) -> list[float]:
    values = [0.0]

    current = step

    while current < maximum:
        values.append(
            round(
                current,
                10,
            )
        )
        current += step

    if (
        maximum > 0.0
        and not isclose(
            values[-1],
            maximum,
            abs_tol=1e-12,
        )
    ):
        values.append(
            float(maximum)
        )

    return values


def reverse_stress_from_context(
    context: ScenarioContext,
    config: ReverseStressConfig,
) -> ReverseStressResult:
    if (
        config.horizon
        != context.horizon
    ):
        raise ValueError(
            "Reverse-stress horizon does not "
            "match prepared scenario context."
        )

    baseline_min_cash = _minimum_cash(
        context=context,
        horizon=config.horizon,
    )

    baseline_margin = (
        baseline_min_cash
        - config.target_min_cash
    )

    baseline_breached = (
        baseline_min_cash
        < config.target_min_cash
    )

    revenue_breakpoint = (
        _continuous_breakpoint(
            baseline_min_cash=(
                baseline_min_cash
            ),
            target_min_cash=(
                config.target_min_cash
            ),
            maximum=(
                config.max_revenue_decline
            ),
            tolerance=(
                config.breakpoint_tolerance
            ),
            evaluator=lambda decline: (
                _minimum_cash(
                    context=context,
                    horizon=config.horizon,
                    revenue_decline=decline,
                )
            ),
        )
    )

    cost_breakpoint = (
        _continuous_breakpoint(
            baseline_min_cash=(
                baseline_min_cash
            ),
            target_min_cash=(
                config.target_min_cash
            ),
            maximum=(
                config.max_cost_increase
            ),
            tolerance=(
                config.breakpoint_tolerance
            ),
            evaluator=lambda increase: (
                _minimum_cash(
                    context=context,
                    horizon=config.horizon,
                    cost_increase=increase,
                )
            ),
        )
    )

    delay_breakpoint = (
        _receivable_delay_breakpoint(
            context=context,
            config=config,
            baseline_min_cash=(
                baseline_min_cash
            ),
        )
    )

    revenue_values = _grid_values(
        config.max_revenue_decline,
        config.grid_step,
    )

    cost_values = _grid_values(
        config.max_cost_increase,
        config.grid_step,
    )

    grid: list[
        ReverseStressGridPoint
    ] = []

    for revenue_decline in revenue_values:
        for cost_increase in cost_values:
            minimum_cash = _minimum_cash(
                context=context,
                horizon=config.horizon,
                revenue_decline=(
                    revenue_decline
                ),
                cost_increase=(
                    cost_increase
                ),
            )

            margin = (
                minimum_cash
                - config.target_min_cash
            )

            grid.append(
                ReverseStressGridPoint(
                    revenue_decline=(
                        revenue_decline
                    ),
                    cost_increase=(
                        cost_increase
                    ),
                    min_cash=minimum_cash,
                    margin_to_target=margin,
                    breached=(
                        minimum_cash
                        < config.target_min_cash
                    ),
                )
            )

    failed_points = [
        point
        for point in grid
        if point.breached
    ]

    nearest_failure = None

    if failed_points:

        revenue_scale = max(
            config.max_revenue_decline,
            config.grid_step,
        )

        cost_scale = max(
            config.max_cost_increase,
            config.grid_step,
        )

        nearest_failure = min(
            failed_points,
            key=lambda point: (
                (
                    point.revenue_decline
                    / revenue_scale
                )
                ** 2
                + (
                    point.cost_increase
                    / cost_scale
                )
                ** 2
            ),
        )

    return ReverseStressResult(
        target_min_cash=(
            config.target_min_cash
        ),
        horizon=config.horizon,
        baseline_min_cash=(
            baseline_min_cash
        ),
        baseline_margin_to_target=(
            baseline_margin
        ),
        baseline_breached=(
            baseline_breached
        ),
        revenue_decline_breakpoint=(
            revenue_breakpoint
        ),
        cost_increase_breakpoint=(
            cost_breakpoint
        ),
        receivable_delay_breakpoint_days=(
            delay_breakpoint
        ),
        nearest_combined_failure=(
            nearest_failure
        ),
        grid=grid,
    )
