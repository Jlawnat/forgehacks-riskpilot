from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from src.core.direct_cash import (
    DIRECT_CASH_HORIZON_WEEKS,
    DirectCashForecastInput,
)
from src.core.recovery_constraints import (
    RecoveryConstraintSet,
    validate_recovery_constraints,
)
from src.core.recovery_engine import (
    RecoveryEvaluation,
    RecoveryPlan,
    evaluate_recovery_plan,
)


class RecoverySearchConfig(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    revenue_step_pct: float = Field(
        default=5.0,
        gt=0.0,
        allow_inf_nan=False,
    )

    cost_step_pct: float = Field(
        default=5.0,
        gt=0.0,
        allow_inf_nan=False,
    )

    receivable_step_days: int = Field(
        default=7,
        ge=1,
    )


class RecoveryCandidate(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    plan: RecoveryPlan
    evaluation: RecoveryEvaluation

    minimum_external_liquidity_for_reserve: (
        float | None
    ) = Field(
        default=None,
        ge=0.0,
        allow_inf_nan=False,
    )

    operating_intervention_score: float = Field(
        ge=0.0,
        le=100.0,
    )

    total_intervention_score: float = Field(
        ge=0.0,
        le=100.0,
    )

    maximum_lever_utilisation: float = Field(
        ge=0.0,
        le=1.0,
    )


class RecoverySearchResult(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    deterministic_status: Literal[
        "FEASIBLE",
        "SHORTFALL",
    ]

    probabilistic_validation_status: Literal[
        "NOT_ASSESSED",
    ] = "NOT_ASSESSED"

    management_reserve: float = Field(
        ge=0.0,
        allow_inf_nan=False,
    )

    candidates_evaluated: int = Field(
        ge=1,
    )

    recommended: RecoveryCandidate | None
    lowest_external_liquidity: RecoveryCandidate | None
    lowest_operational_disruption: RecoveryCandidate | None
    no_external_liquidity: RecoveryCandidate | None

    best_effort: RecoveryCandidate

    best_attainable_min_cash: float = Field(
        allow_inf_nan=False,
    )

    remaining_reserve_gap: float = Field(
        ge=0.0,
        allow_inf_nan=False,
    )


def _float_grid(
    maximum: float,
    step: float,
) -> tuple[float, ...]:
    if maximum <= 0.0:
        return (0.0,)

    values = [0.0]
    value = step

    while value < maximum:
        values.append(
            round(value, 10)
        )
        value += step

    if values[-1] != maximum:
        values.append(
            float(maximum)
        )

    return tuple(values)


def _integer_grid(
    maximum: int,
    step: int,
) -> tuple[int, ...]:
    if maximum <= 0:
        return (0,)

    values = list(
        range(
            0,
            maximum + 1,
            step,
        )
    )

    if values[-1] != maximum:
        values.append(maximum)

    return tuple(values)


def _normalised(
    value: float,
    maximum: float,
) -> float:
    if maximum <= 0.0:
        return 0.0

    return min(
        1.0,
        max(
            0.0,
            value / maximum,
        ),
    )


def _scores(
    plan: RecoveryPlan,
    constraints: RecoveryConstraintSet,
) -> tuple[
    float,
    float,
    float,
]:
    operating_parts: list[float] = []

    revenue = constraints.revenue_improvement

    if (
        revenue.enabled
        and revenue.max_improvement_pct > 0.0
        and revenue.eligible_event_ids
    ):
        operating_parts.append(
            _normalised(
                plan.revenue_improvement_pct,
                revenue.max_improvement_pct,
            )
        )

    cost = constraints.cost_reduction

    if (
        cost.enabled
        and cost.max_reduction_pct > 0.0
        and cost.eligible_event_ids
    ):
        operating_parts.append(
            _normalised(
                plan.cost_reduction_pct,
                cost.max_reduction_pct,
            )
        )

    receivables = (
        constraints.receivable_acceleration
    )

    if (
        receivables.enabled
        and receivables.max_acceleration_days > 0
        and receivables.eligible_event_ids
    ):
        operating_parts.append(
            _normalised(
                float(
                    plan.receivable_acceleration_days
                ),
                float(
                    receivables
                    .max_acceleration_days
                ),
            )
        )

    operating_score = (
        100.0
        * sum(operating_parts)
        / len(operating_parts)
        if operating_parts
        else 0.0
    )

    all_parts = list(
        operating_parts
    )

    liquidity = constraints.external_liquidity

    if (
        liquidity.enabled
        and liquidity.max_amount > 0.0
    ):
        all_parts.append(
            _normalised(
                plan.external_liquidity,
                liquidity.max_amount,
            )
        )

    total_score = (
        100.0
        * sum(all_parts)
        / len(all_parts)
        if all_parts
        else 0.0
    )

    maximum_utilisation = max(
        all_parts,
        default=0.0,
    )

    return (
        float(operating_score),
        float(total_score),
        float(maximum_utilisation),
    )


def _external_week_index(
    forecast_input: DirectCashForecastInput,
    constraints: RecoveryConstraintSet,
) -> int | None:
    available_date = max(
        forecast_input.start_date,
        constraints
        .external_liquidity
        .available_from,
    )

    days_from_start = (
        available_date
        - forecast_input.start_date
    ).days

    if (
        days_from_start
        >= DIRECT_CASH_HORIZON_WEEKS * 7
    ):
        return None

    return days_from_start // 7


def _minimum_required_external(
    operating_evaluation: RecoveryEvaluation,
    *,
    forecast_input: DirectCashForecastInput,
    constraints: RecoveryConstraintSet,
    management_reserve: float,
) -> float | None:
    """
    Minimum funding required at the stated availability
    date to keep every forecast week at or above reserve.

    None means funding at that date cannot repair all
    breaches because a breach already occurs earlier, or
    funding is outside the forecast horizon.
    """
    cash = list(
        operating_evaluation.weekly_closing_cash
    )

    if min(cash) >= management_reserve:
        return 0.0

    week_index = _external_week_index(
        forecast_input,
        constraints,
    )

    if week_index is None:
        return None

    if any(
        value < management_reserve
        for value in cash[:week_index]
    ):
        return None

    post_funding_minimum = min(
        cash[week_index:]
    )

    return max(
        0.0,
        management_reserve
        - post_funding_minimum,
    )


def _candidate(
    *,
    forecast_input: DirectCashForecastInput,
    constraints: RecoveryConstraintSet,
    plan: RecoveryPlan,
    management_reserve: float,
    minimum_required: float | None,
) -> RecoveryCandidate:
    evaluation = evaluate_recovery_plan(
        forecast_input,
        constraints,
        plan,
        management_reserve=(
            management_reserve
        ),
    )

    (
        operating_score,
        total_score,
        maximum_utilisation,
    ) = _scores(
        plan,
        constraints,
    )

    return RecoveryCandidate(
        plan=plan,
        evaluation=evaluation,
        minimum_external_liquidity_for_reserve=(
            minimum_required
        ),
        operating_intervention_score=(
            operating_score
        ),
        total_intervention_score=(
            total_score
        ),
        maximum_lever_utilisation=(
            maximum_utilisation
        ),
    )


def optimize_recovery(
    forecast_input: DirectCashForecastInput,
    constraints: RecoveryConstraintSet,
    *,
    management_reserve: float,
    config: RecoverySearchConfig | None = None,
) -> RecoverySearchResult:
    """
    Search deterministic 13-week recovery candidates.

    Operating levers are searched over explicit grids.
    External liquidity is not brute-forced: for each
    operating combination, the minimum funding required
    at its permitted availability date is calculated.

    Probabilistic adequacy is intentionally NOT assessed.
    """
    validate_recovery_constraints(
        forecast_input,
        constraints,
    )

    search = (
        config
        if config is not None
        else RecoverySearchConfig()
    )

    revenue_constraint = (
        constraints.revenue_improvement
    )

    cost_constraint = (
        constraints.cost_reduction
    )

    receivable_constraint = (
        constraints.receivable_acceleration
    )

    revenue_values = (
        _float_grid(
            revenue_constraint
            .max_improvement_pct,
            search.revenue_step_pct,
        )
        if (
            revenue_constraint.enabled
            and revenue_constraint
            .eligible_event_ids
        )
        else (0.0,)
    )

    cost_values = (
        _float_grid(
            cost_constraint
            .max_reduction_pct,
            search.cost_step_pct,
        )
        if (
            cost_constraint.enabled
            and cost_constraint
            .eligible_event_ids
        )
        else (0.0,)
    )

    acceleration_values = (
        _integer_grid(
            receivable_constraint
            .max_acceleration_days,
            search.receivable_step_days,
        )
        if (
            receivable_constraint.enabled
            and receivable_constraint
            .eligible_event_ids
        )
        else (0,)
    )

    candidates: list[
        RecoveryCandidate
    ] = []

    liquidity_constraint = (
        constraints.external_liquidity
    )

    for revenue_pct in revenue_values:
        for cost_pct in cost_values:
            for acceleration_days in (
                acceleration_values
            ):
                operating_plan = RecoveryPlan(
                    revenue_improvement_pct=(
                        revenue_pct
                    ),
                    cost_reduction_pct=(
                        cost_pct
                    ),
                    receivable_acceleration_days=(
                        acceleration_days
                    ),
                    external_liquidity=0.0,
                )

                operating_evaluation = (
                    evaluate_recovery_plan(
                        forecast_input,
                        constraints,
                        operating_plan,
                        management_reserve=(
                            management_reserve
                        ),
                    )
                )

                required = (
                    _minimum_required_external(
                        operating_evaluation,
                        forecast_input=(
                            forecast_input
                        ),
                        constraints=constraints,
                        management_reserve=(
                            management_reserve
                        ),
                    )
                )

                candidates.append(
                    _candidate(
                        forecast_input=(
                            forecast_input
                        ),
                        constraints=constraints,
                        plan=operating_plan,
                        management_reserve=(
                            management_reserve
                        ),
                        minimum_required=required,
                    )
                )

                if (
                    required is not None
                    and required > 0.0
                    and liquidity_constraint.enabled
                    and required
                    <= liquidity_constraint.max_amount
                ):
                    funded_plan = (
                        operating_plan.model_copy(
                            update={
                                "external_liquidity":
                                    required
                            }
                        )
                    )

                    candidates.append(
                        _candidate(
                            forecast_input=(
                                forecast_input
                            ),
                            constraints=(
                                constraints
                            ),
                            plan=funded_plan,
                            management_reserve=(
                                management_reserve
                            ),
                            minimum_required=(
                                required
                            ),
                        )
                    )

                elif (
                    not operating_evaluation.feasible
                    and liquidity_constraint.enabled
                    and liquidity_constraint.max_amount
                    > 0.0
                    and _external_week_index(
                        forecast_input,
                        constraints,
                    )
                    is not None
                ):
                    max_funded_plan = (
                        operating_plan.model_copy(
                            update={
                                "external_liquidity":
                                    liquidity_constraint
                                    .max_amount
                            }
                        )
                    )

                    candidates.append(
                        _candidate(
                            forecast_input=(
                                forecast_input
                            ),
                            constraints=(
                                constraints
                            ),
                            plan=max_funded_plan,
                            management_reserve=(
                                management_reserve
                            ),
                            minimum_required=(
                                required
                            ),
                        )
                    )

    feasible = [
        candidate
        for candidate in candidates
        if candidate.evaluation.feasible
    ]

    recommended = None
    lowest_external = None
    lowest_operational = None
    no_external = None

    if feasible:
        recommended = min(
            feasible,
            key=lambda candidate: (
                candidate
                .maximum_lever_utilisation,
                candidate
                .total_intervention_score,
                candidate
                .plan
                .external_liquidity,
            ),
        )

        lowest_external = min(
            feasible,
            key=lambda candidate: (
                candidate
                .plan
                .external_liquidity,
                candidate
                .operating_intervention_score,
                candidate
                .total_intervention_score,
            ),
        )

        lowest_operational = min(
            feasible,
            key=lambda candidate: (
                candidate
                .operating_intervention_score,
                candidate
                .plan
                .external_liquidity,
                candidate
                .total_intervention_score,
            ),
        )

        zero_funding = [
            candidate
            for candidate in feasible
            if (
                candidate
                .plan
                .external_liquidity
                == 0.0
            )
        ]

        if zero_funding:
            no_external = min(
                zero_funding,
                key=lambda candidate: (
                    candidate
                    .operating_intervention_score,
                    candidate
                    .maximum_lever_utilisation,
                ),
            )

    best_effort = max(
        candidates,
        key=lambda candidate: (
            candidate
            .evaluation
            .resulting_min_cash,
            -candidate
            .evaluation
            .remaining_reserve_gap,
            -candidate
            .total_intervention_score,
            -candidate
            .plan
            .external_liquidity,
        ),
    )

    best_gap = (
        best_effort
        .evaluation
        .remaining_reserve_gap
    )

    return RecoverySearchResult(
        deterministic_status=(
            "FEASIBLE"
            if feasible
            else "SHORTFALL"
        ),
        management_reserve=float(
            management_reserve
        ),
        candidates_evaluated=len(
            candidates
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
        best_attainable_min_cash=float(
            best_effort
            .evaluation
            .resulting_min_cash
        ),
        remaining_reserve_gap=float(
            best_gap
        ),
    )
