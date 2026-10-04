from __future__ import annotations

import pandas as pd
from pydantic import BaseModel

from src.scenarios.engine import (
    ScenarioContext,
    ScenarioInput,
    prepare_scenario_context,
    run_scenario_from_context,
)


class DriverImpact(BaseModel):
    driver: str
    end_cash_impact: float
    peak_liquidity_impact: float
    contribution_share: float


class ScenarioDecomposition(BaseModel):
    total_end_cash_impact: float
    peak_liquidity_gap: float
    peak_liquidity_gap_period: int | None
    drivers: list[DriverImpact]


def decompose_scenario_from_context(
    context: ScenarioContext,
    scenario: ScenarioInput,
) -> ScenarioDecomposition:
    if context.horizon != scenario.horizon:
        raise ValueError(
            "Scenario horizon does not match prepared context."
        )

    combined = run_scenario_from_context(
        context,
        scenario,
    )

    isolated_scenarios = {
        "revenue_shock": ScenarioInput(
            revenue_change=scenario.revenue_change,
            horizon=scenario.horizon,
        ),
        "cost_shock": ScenarioInput(
            cost_change=scenario.cost_change,
            horizon=scenario.horizon,
        ),
        "receivable_delay": ScenarioInput(
            receivable_delay_days=scenario.receivable_delay_days,
            horizon=scenario.horizon,
        ),
    }

    peak_period = (
        combined.peak_liquidity_gap_period
    )

    impacts: list[
        tuple[str, float, float]
    ] = []

    for name, isolated_input in isolated_scenarios.items():
        isolated = run_scenario_from_context(
            context,
            isolated_input,
        )

        end_impact = (
            isolated.end_cash_impact
        )

        if peak_period is None:
            liquidity_impact = 0.0
        else:
            point = isolated.trajectory[
                peak_period - 1
            ]

            liquidity_impact = max(
                0.0,
                point.baseline_cash
                - point.stressed_cash,
            )

        impacts.append(
            (
                name,
                float(end_impact),
                float(liquidity_impact),
            )
        )

    total_peak_driver_impact = sum(
        item[2]
        for item in impacts
    )

    drivers: list[
        DriverImpact
    ] = []

    for (
        name,
        end_impact,
        liquidity_impact,
    ) in impacts:

        if total_peak_driver_impact > 0:
            share = (
                liquidity_impact
                / total_peak_driver_impact
            )
        else:
            share = 0.0

        drivers.append(
            DriverImpact(
                driver=name,
                end_cash_impact=end_impact,
                peak_liquidity_impact=(
                    liquidity_impact
                ),
                contribution_share=float(
                    share
                ),
            )
        )

    drivers.sort(
        key=lambda item:
            item.peak_liquidity_impact,
        reverse=True,
    )

    return ScenarioDecomposition(
        total_end_cash_impact=(
            combined.end_cash_impact
        ),
        peak_liquidity_gap=(
            combined.peak_liquidity_gap
        ),
        peak_liquidity_gap_period=(
            combined
            .peak_liquidity_gap_period
        ),
        drivers=drivers,
    )


def decompose_scenario(
    df: pd.DataFrame,
    scenario: ScenarioInput,
) -> ScenarioDecomposition:
    """
    Backwards-compatible API.
    """

    context = prepare_scenario_context(
        df,
        scenario.horizon,
    )

    return (
        decompose_scenario_from_context(
            context,
            scenario,
        )
    )
