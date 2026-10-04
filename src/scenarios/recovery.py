from __future__ import annotations

from pydantic import BaseModel, Field
import pandas as pd

from src.scenarios.engine import (
    ScenarioContext,
    ScenarioInput,
    prepare_scenario_context,
    run_scenario_from_context,
)


MAX_REVENUE_IMPROVEMENT_PCT = 20
MAX_COST_REDUCTION_PCT = 15


class RecoveryAction(BaseModel):
    action: str
    feasible: bool

    magnitude: float | None = None
    unit: str | None = None

    resulting_min_cash: float | None = None
    resulting_end_cash: float | None = None

    components: dict[str, float] = Field(default_factory=dict)

    explanation: str


class RecoveryPlan(BaseModel):
    target_min_cash: float
    stressed_min_cash: float
    stressed_end_cash: float

    operational_recovery_possible: bool
    actions: list[RecoveryAction]


def _evaluate(
    context: ScenarioContext,
    scenario: ScenarioInput,
    target: float,
) -> tuple[bool, float, float]:
    result = run_scenario_from_context(
        context,
        scenario,
    )

    return (
        result.stressed_min_cash >= target,
        result.stressed_min_cash,
        result.stressed_end_cash,
    )


def _revenue_only(
    context: ScenarioContext,
    base: ScenarioInput,
    target: float,
) -> RecoveryAction:
    for pct in range(MAX_REVENUE_IMPROVEMENT_PCT + 1):
        candidate = ScenarioInput(
            revenue_change=base.revenue_change + pct / 100,
            cost_change=base.cost_change,
            receivable_delay_days=base.receivable_delay_days,
            horizon=base.horizon,
        )

        feasible, min_cash, end_cash = _evaluate(
            context,
            candidate,
            target,
        )

        if feasible:
            return RecoveryAction(
                action="revenue_recovery",
                feasible=True,
                magnitude=float(pct),
                unit="percentage points",
                resulting_min_cash=min_cash,
                resulting_end_cash=end_cash,
                components={
                    "revenue_improvement_pct": float(pct),
                },
                explanation=(
                    f"Improve revenue by approximately {pct}% "
                    "relative to the stressed assumption."
                ),
            )

    return RecoveryAction(
        action="revenue_recovery",
        feasible=False,
        components={
            "max_revenue_improvement_pct":
                float(MAX_REVENUE_IMPROVEMENT_PCT),
        },
        explanation=(
            "Revenue improvement alone does not restore the target "
            f"within the practical +{MAX_REVENUE_IMPROVEMENT_PCT}% "
            "search range."
        ),
    )


def _cost_only(
    context: ScenarioContext,
    base: ScenarioInput,
    target: float,
) -> RecoveryAction:
    for pct in range(MAX_COST_REDUCTION_PCT + 1):
        candidate = ScenarioInput(
            revenue_change=base.revenue_change,
            cost_change=base.cost_change - pct / 100,
            receivable_delay_days=base.receivable_delay_days,
            horizon=base.horizon,
        )

        feasible, min_cash, end_cash = _evaluate(
            context,
            candidate,
            target,
        )

        if feasible:
            return RecoveryAction(
                action="cost_reduction",
                feasible=True,
                magnitude=float(pct),
                unit="percentage points",
                resulting_min_cash=min_cash,
                resulting_end_cash=end_cash,
                components={
                    "cost_reduction_pct": float(pct),
                },
                explanation=(
                    f"Reduce operating costs by approximately {pct}% "
                    "relative to the stressed assumption."
                ),
            )

    return RecoveryAction(
        action="cost_reduction",
        feasible=False,
        components={
            "max_cost_reduction_pct":
                float(MAX_COST_REDUCTION_PCT),
        },
        explanation=(
            "Cost reduction alone does not restore the target "
            f"within the practical {MAX_COST_REDUCTION_PCT}% "
            "search range."
        ),
    )


def _receivables_only(
    context: ScenarioContext,
    base: ScenarioInput,
    target: float,
) -> RecoveryAction:
    if base.receivable_delay_days == 0:
        return RecoveryAction(
            action="receivable_acceleration",
            feasible=False,
            explanation="No receivable delay exists in this scenario.",
        )

    candidate = ScenarioInput(
        revenue_change=base.revenue_change,
        cost_change=base.cost_change,
        receivable_delay_days=0,
        horizon=base.horizon,
    )

    feasible, min_cash, end_cash = _evaluate(
        context,
        candidate,
        target,
    )

    return RecoveryAction(
        action="receivable_acceleration",
        feasible=feasible,
        magnitude=float(base.receivable_delay_days),
        unit="days",
        resulting_min_cash=min_cash,
        resulting_end_cash=end_cash,
        components={
            "receivable_days_faster":
                float(base.receivable_delay_days),
        },
        explanation=(
            f"Remove the modeled {base.receivable_delay_days}-day "
            "collection delay."
            if feasible
            else
            "Removing the modeled receivable delay improves liquidity "
            "but does not solve the structural cash shortfall alone."
        ),
    )


def _best_operating_mix(
    context: ScenarioContext,
    base: ScenarioInput,
    target: float,
) -> tuple[RecoveryAction, float]:
    """
    Search realistic combinations of:
    - revenue improvement <= 20 percentage points
    - cost reduction <= 15 percentage points
    - optional removal of the receivable delay

    If no combination fully restores the target, return the combination
    that gets closest by maximising minimum cash.
    """
    best_feasible = None
    best_infeasible = None

    for remove_delay in (False, True):
        delay = (
            0
            if remove_delay
            else base.receivable_delay_days
        )

        for revenue_pct in range(
            MAX_REVENUE_IMPROVEMENT_PCT + 1
        ):
            for cost_pct in range(
                MAX_COST_REDUCTION_PCT + 1
            ):
                candidate = ScenarioInput(
                    revenue_change=(
                        base.revenue_change
                        + revenue_pct / 100
                    ),
                    cost_change=(
                        base.cost_change
                        - cost_pct / 100
                    ),
                    receivable_delay_days=delay,
                    horizon=base.horizon,
                )

                feasible, min_cash, end_cash = _evaluate(
                    context,
                    candidate,
                    target,
                )

                intervention = revenue_pct + cost_pct

                record = (
                    intervention,
                    revenue_pct,
                    cost_pct,
                    remove_delay,
                    min_cash,
                    end_cash,
                )

                if feasible:
                    if (
                        best_feasible is None
                        or record[0] < best_feasible[0]
                    ):
                        best_feasible = record
                else:
                    if (
                        best_infeasible is None
                        or min_cash > best_infeasible[4]
                        or (
                            min_cash == best_infeasible[4]
                            and intervention < best_infeasible[0]
                        )
                    ):
                        best_infeasible = record

    chosen = (
        best_feasible
        if best_feasible is not None
        else best_infeasible
    )

    assert chosen is not None

    (
        intervention,
        revenue_pct,
        cost_pct,
        remove_delay,
        min_cash,
        end_cash,
    ) = chosen

    receivable_days = (
        base.receivable_delay_days
        if remove_delay
        else 0
    )

    if best_feasible is not None:
        action = RecoveryAction(
            action="best_operating_mix",
            feasible=True,
            magnitude=float(intervention),
            unit="combined percentage points",
            resulting_min_cash=min_cash,
            resulting_end_cash=end_cash,
            components={
                "revenue_improvement_pct":
                    float(revenue_pct),
                "cost_reduction_pct":
                    float(cost_pct),
                "receivable_days_faster":
                    float(receivable_days),
            },
            explanation=(
                f"Improve revenue by {revenue_pct}%, reduce costs "
                f"by {cost_pct}%"
                + (
                    f", and collect receivables "
                    f"{receivable_days} days faster."
                    if receivable_days
                    else "."
                )
            ),
        )
    else:
        action = RecoveryAction(
            action="best_operating_mix",
            feasible=False,
            magnitude=float(intervention),
            unit="combined percentage points",
            resulting_min_cash=min_cash,
            resulting_end_cash=end_cash,
            components={
                "revenue_improvement_pct":
                    float(revenue_pct),
                "cost_reduction_pct":
                    float(cost_pct),
                "receivable_days_faster":
                    float(receivable_days),
            },
            explanation=(
                "Even the strongest modeled operating response within "
                "practical limits does not fully restore the cash target."
            ),
        )

    return action, min_cash


def build_recovery_plan_from_context(
    context: ScenarioContext,
    stressed_scenario: ScenarioInput,
    target_min_cash: float = 0.0,
) -> RecoveryPlan:
    """
    Build recovery recommendations without re-fitting
    any forecasting models.
    """

    if (
        context.horizon
        != stressed_scenario.horizon
    ):
        raise ValueError(
            "Scenario horizon does not match "
            "prepared context."
        )

    stressed = run_scenario_from_context(
        context,
        stressed_scenario,
    )

    if (
        stressed.stressed_min_cash
        >= target_min_cash
    ):
        return RecoveryPlan(
            target_min_cash=(
                target_min_cash
            ),
            stressed_min_cash=(
                stressed
                .stressed_min_cash
            ),
            stressed_end_cash=(
                stressed
                .stressed_end_cash
            ),
            operational_recovery_possible=True,
            actions=[
                RecoveryAction(
                    action=(
                        "no_action_required"
                    ),
                    feasible=True,
                    magnitude=0.0,
                    unit="none",
                    resulting_min_cash=(
                        stressed
                        .stressed_min_cash
                    ),
                    resulting_end_cash=(
                        stressed
                        .stressed_end_cash
                    ),
                    explanation=(
                        "The scenario already "
                        "satisfies the selected "
                        "cash target."
                    ),
                )
            ],
        )

    revenue = _revenue_only(
        context,
        stressed_scenario,
        target_min_cash,
    )

    cost = _cost_only(
        context,
        stressed_scenario,
        target_min_cash,
    )

    receivables = _receivables_only(
        context,
        stressed_scenario,
        target_min_cash,
    )

    (
        operating_mix,
        best_min_cash,
    ) = _best_operating_mix(
        context,
        stressed_scenario,
        target_min_cash,
    )

    actions = [
        revenue,
        cost,
        receivables,
        operating_mix,
    ]

    operational_recovery_possible = (
        operating_mix.feasible
    )

    if not operational_recovery_possible:
        required_buffer = max(
            0.0,
            target_min_cash
            - best_min_cash,
        )

        actions.append(
            RecoveryAction(
                action="liquidity_buffer",
                feasible=True,
                magnitude=float(
                    required_buffer
                ),
                unit="currency",
                resulting_min_cash=float(
                    best_min_cash
                    + required_buffer
                ),
                resulting_end_cash=(
                    None
                    if operating_mix
                    .resulting_end_cash
                    is None
                    else float(
                        operating_mix
                        .resulting_end_cash
                        + required_buffer
                    )
                ),
                components={
                    "required_liquidity_buffer":
                        float(
                            required_buffer
                        ),
                },
                explanation=(
                    "After applying the strongest "
                    "modeled operating response "
                    "within practical limits, "
                    "approximately "
                    f"${required_buffer:,.0f} "
                    "of additional liquidity "
                    "would still be required to "
                    "keep cash above the selected "
                    "minimum."
                ),
            )
        )

    return RecoveryPlan(
        target_min_cash=(
            target_min_cash
        ),
        stressed_min_cash=(
            stressed.stressed_min_cash
        ),
        stressed_end_cash=(
            stressed.stressed_end_cash
        ),
        operational_recovery_possible=(
            operational_recovery_possible
        ),
        actions=actions,
    )


def build_recovery_plan(
    df: pd.DataFrame,
    stressed_scenario: ScenarioInput,
    target_min_cash: float = 0.0,
) -> RecoveryPlan:
    """
    Backwards-compatible API.
    """

    context = (
        prepare_scenario_context(
            df,
            stressed_scenario.horizon,
        )
    )

    return (
        build_recovery_plan_from_context(
            context,
            stressed_scenario,
            target_min_cash,
        )
    )
