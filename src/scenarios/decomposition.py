from __future__ import annotations

from pydantic import BaseModel
import pandas as pd

from src.scenarios.engine import (
    ScenarioInput,
    run_scenario,
)


class DriverImpact(BaseModel):
    driver: str

    # Persistent impact at the end of the modeled horizon.
    end_cash_impact: float

    # Impact at the period where the combined scenario creates
    # its largest liquidity gap.
    peak_liquidity_impact: float

    contribution_share: float


class ScenarioDecomposition(BaseModel):
    total_end_cash_impact: float
    peak_liquidity_gap: float
    peak_liquidity_gap_period: int | None
    drivers: list[DriverImpact]


def decompose_scenario(
    df: pd.DataFrame,
    scenario: ScenarioInput,
) -> ScenarioDecomposition:
    combined = run_scenario(df, scenario)

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

    peak_period = combined.peak_liquidity_gap_period

    impacts: list[tuple[str, float, float]] = []

    for name, isolated_input in isolated_scenarios.items():
        isolated = run_scenario(
            df,
            isolated_input,
        )

        end_impact = isolated.end_cash_impact

        if peak_period is None:
            liquidity_impact = 0.0
        else:
            point = isolated.trajectory[peak_period - 1]

            liquidity_impact = max(
                0.0,
                point.baseline_cash - point.stressed_cash,
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

    drivers: list[DriverImpact] = []

    for name, end_impact, liquidity_impact in impacts:
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
                peak_liquidity_impact=liquidity_impact,
                contribution_share=float(share),
            )
        )

    drivers.sort(
        key=lambda item: item.peak_liquidity_impact,
        reverse=True,
    )

    return ScenarioDecomposition(
        total_end_cash_impact=combined.end_cash_impact,
        peak_liquidity_gap=combined.peak_liquidity_gap,
        peak_liquidity_gap_period=combined.peak_liquidity_gap_period,
        drivers=drivers,
    )
