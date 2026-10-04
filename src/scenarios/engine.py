from __future__ import annotations

from math import ceil

from pydantic import BaseModel, Field
import pandas as pd

from src.forecasting.forecast import forecast_metric


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

    # Largest temporary deterioration versus baseline.
    peak_liquidity_gap: float
    peak_liquidity_gap_period: int | None

    trajectory: list[CashPoint]


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


def _receivable_adjustments(
    latest_receivables: float,
    delay_days: int,
    horizon: int,
) -> list[float]:
    """
    Treat delayed receivables as a timing shock, not lost revenue.

    We assume monthly forecast periods. A delay removes the current
    receivable balance from the first projected collection period and
    restores it once the delay has elapsed.
    """
    adjustments = [0.0] * horizon

    if delay_days <= 0 or latest_receivables <= 0:
        return adjustments

    delay_periods = max(1, ceil(delay_days / 30))

    adjustments[0] -= latest_receivables

    recovery_index = delay_periods

    if recovery_index < horizon:
        adjustments[recovery_index] += latest_receivables

    return adjustments


def run_scenario(
    df: pd.DataFrame,
    scenario: ScenarioInput,
) -> ScenarioResult:
    if df.empty:
        raise ValueError("Cannot run a scenario on empty data.")

    revenue_forecast = forecast_metric(
        df,
        "revenue",
        horizon=scenario.horizon,
    )

    cost_forecast = forecast_metric(
        df,
        "operating_cost",
        horizon=scenario.horizon,
    )

    baseline_revenue = [
        point.value
        for point in revenue_forecast.forecasts
    ]

    baseline_cost = [
        point.value
        for point in cost_forecast.forecasts
    ]

    stressed_revenue = [
        value * (1.0 + scenario.revenue_change)
        for value in baseline_revenue
    ]

    stressed_cost = [
        value * (1.0 + scenario.cost_change)
        for value in baseline_cost
    ]

    starting_cash = float(df["cash_balance"].iloc[-1])
    latest_receivables = float(df["receivables"].iloc[-1])

    receivable_adjustments = _receivable_adjustments(
        latest_receivables,
        scenario.receivable_delay_days,
        scenario.horizon,
    )

    baseline_cash = starting_cash
    stressed_cash = starting_cash

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

    if peak_gap > 0:
        peak_period = liquidity_gaps.index(peak_gap) + 1
    else:
        peak_period = None

    return ScenarioResult(
        inputs=scenario,
        starting_cash=starting_cash,

        baseline_end_cash=float(baseline_cash),
        stressed_end_cash=float(stressed_cash),

        baseline_min_cash=float(
            min([starting_cash] + baseline_cash_values)
        ),
        stressed_min_cash=float(
            min([starting_cash] + stressed_cash_values)
        ),

        baseline_runway_months=_estimate_runway(
            starting_cash,
            baseline_flows,
        ),
        stressed_runway_months=_estimate_runway(
            starting_cash,
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
