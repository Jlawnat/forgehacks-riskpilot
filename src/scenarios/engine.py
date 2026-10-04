from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field
import pandas as pd

from src.forecasting.forecast import forecast_metric
from src.core.receivables import (
    fractional_receivable_delay_adjustments,
)
from src.core.context import (
    ForecastContext,
    build_forecast_context,
)


class ScenarioInput(BaseModel):
    revenue_change: float = Field(default=0.0, ge=-1.0, le=2.0)
    cost_change: float = Field(default=0.0, ge=-1.0, le=2.0)
    receivable_delay_days: int = Field(default=0, ge=0, le=180)
    horizon: int = Field(default=3, ge=1, le=12)


class CashPoint(BaseModel):
    period: int
    baseline_cash: float
    stressed_cash: float
    baseline_revenue: float
    stressed_revenue: float
    baseline_cost: float
    stressed_cost: float
    receivable_timing_adjustment: float


class ScenarioResult(BaseModel):
    inputs: ScenarioInput
    starting_cash: float

    baseline_end_cash: float
    stressed_end_cash: float

    baseline_min_cash: float
    stressed_min_cash: float

    baseline_runway_months: float | None
    stressed_runway_months: float | None

    baseline_first_negative_period: int | None
    stressed_first_negative_period: int | None

    end_cash_impact: float

    peak_liquidity_gap: float
    peak_liquidity_gap_period: int | None

    trajectory: list[CashPoint]


@dataclass(frozen=True)
class ScenarioContext:
    horizon: int
    starting_cash: float
    latest_receivables: float
    baseline_revenue: tuple[float, ...]
    baseline_cost: tuple[float, ...]


def scenario_context_from_forecast_context(
    context: ForecastContext,
) -> ScenarioContext:
    """
    Convert the shared forecasting context into the
    lightweight structure required by the scenario engine.
    """
    return ScenarioContext(
        horizon=context.horizon,
        starting_cash=context.starting_cash,
        latest_receivables=context.latest_receivables,
        baseline_revenue=tuple(
            float(point.value)
            for point
            in context.revenue_forecast.forecasts
        ),
        baseline_cost=tuple(
            float(point.value)
            for point
            in context.cost_forecast.forecasts
        ),
    )


def prepare_scenario_context(
    df: pd.DataFrame,
    horizon: int,
) -> ScenarioContext:
    """
    Backwards-compatible wrapper.

    Existing callers still work, while higher-level code
    can prepare ForecastContext once and reuse it.
    """
    forecast_context = (
        build_forecast_context(
            df,
            horizon,
        )
    )

    return (
        scenario_context_from_forecast_context(
            forecast_context
        )
    )

def _estimate_runway(
    starting_cash: float,
    monthly_net_flows: list[float],
) -> float | None:
    cash = float(starting_cash)

    if cash <= 0:
        return 0.0

    for index, flow in enumerate(monthly_net_flows, start=1):
        previous_cash = cash
        cash += flow

        if cash <= 0:
            if flow >= 0:
                return float(index)

            burn = abs(flow)

            fraction = (
                previous_cash / burn
                if burn > 0
                else 0.0
            )

            return max(
                0.0,
                (index - 1) + fraction,
            )

    return None


def _first_negative_period(
    cash_values: list[float],
) -> int | None:
    for period, cash in enumerate(cash_values, start=1):
        if cash < 0:
            return period

    return None



def run_scenario_from_context(
    context: ScenarioContext,
    scenario: ScenarioInput,
) -> ScenarioResult:
    if scenario.horizon != context.horizon:
        raise ValueError(
            "Scenario horizon does not match prepared context."
        )

    baseline_revenue = list(context.baseline_revenue)
    baseline_cost = list(context.baseline_cost)

    stressed_revenue = [
        value * (1.0 + scenario.revenue_change)
        for value in baseline_revenue
    ]

    stressed_cost = [
        value * (1.0 + scenario.cost_change)
        for value in baseline_cost
    ]

    receivable_adjustments = fractional_receivable_delay_adjustments(
        context.latest_receivables,
        scenario.receivable_delay_days,
        scenario.horizon,
    )

    baseline_cash = context.starting_cash
    stressed_cash = context.starting_cash

    baseline_flows: list[float] = []
    stressed_flows: list[float] = []
    trajectory: list[CashPoint] = []

    for period in range(scenario.horizon):
        baseline_flow = (
            baseline_revenue[period]
            - baseline_cost[period]
        )

        stressed_flow = (
            stressed_revenue[period]
            - stressed_cost[period]
            + receivable_adjustments[period]
        )

        baseline_flows.append(baseline_flow)
        stressed_flows.append(stressed_flow)

        baseline_cash += baseline_flow
        stressed_cash += stressed_flow

        trajectory.append(
            CashPoint(
                period=period + 1,
                baseline_cash=float(baseline_cash),
                stressed_cash=float(stressed_cash),
                baseline_revenue=float(baseline_revenue[period]),
                stressed_revenue=float(stressed_revenue[period]),
                baseline_cost=float(baseline_cost[period]),
                stressed_cost=float(stressed_cost[period]),
                receivable_timing_adjustment=float(
                    receivable_adjustments[period]
                ),
            )
        )

    baseline_cash_values = [
        point.baseline_cash
        for point in trajectory
    ]

    stressed_cash_values = [
        point.stressed_cash
        for point in trajectory
    ]

    liquidity_gaps = [
        max(0.0, baseline - stressed)
        for baseline, stressed in zip(
            baseline_cash_values,
            stressed_cash_values,
        )
    ]

    peak_gap = max(liquidity_gaps, default=0.0)

    peak_period = (
        liquidity_gaps.index(peak_gap) + 1
        if peak_gap > 0
        else None
    )

    return ScenarioResult(
        inputs=scenario,
        starting_cash=context.starting_cash,

        baseline_end_cash=float(baseline_cash),
        stressed_end_cash=float(stressed_cash),

        baseline_min_cash=float(
            min([context.starting_cash] + baseline_cash_values)
        ),
        stressed_min_cash=float(
            min([context.starting_cash] + stressed_cash_values)
        ),

        baseline_runway_months=_estimate_runway(
            context.starting_cash,
            baseline_flows,
        ),
        stressed_runway_months=_estimate_runway(
            context.starting_cash,
            stressed_flows,
        ),

        baseline_first_negative_period=_first_negative_period(
            baseline_cash_values
        ),
        stressed_first_negative_period=_first_negative_period(
            stressed_cash_values
        ),

        end_cash_impact=float(
            stressed_cash - baseline_cash
        ),

        peak_liquidity_gap=float(peak_gap),
        peak_liquidity_gap_period=peak_period,

        trajectory=trajectory,
    )


def run_scenario(
    df: pd.DataFrame,
    scenario: ScenarioInput,
) -> ScenarioResult:
    context = prepare_scenario_context(
        df,
        scenario.horizon,
    )

    return run_scenario_from_context(
        context,
        scenario,
    )
