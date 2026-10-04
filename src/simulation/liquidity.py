from __future__ import annotations

from math import ceil

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from src.forecasting.forecast import forecast_metric
from src.forecasting.models import holt_forecast, naive_forecast


class SimulationInput(BaseModel):
    revenue_change: float = Field(default=0.0, ge=-1.0, le=2.0)
    cost_change: float = Field(default=0.0, ge=-1.0, le=2.0)
    receivable_delay_days: int = Field(default=0, ge=0, le=180)

    horizon: int = Field(default=3, ge=1, le=12)

    simulations: int = Field(default=5000, ge=100, le=50000)
    seed: int = 42

    cash_floor: float = 0.0
    confidence_level: float = Field(default=0.95, gt=0.5, lt=1.0)


class LiquidityQuantilePoint(BaseModel):
    period: int

    p10_cash: float
    p50_cash: float
    p90_cash: float

    shortfall_probability: float


class LiquiditySimulationResult(BaseModel):
    inputs: SimulationInput

    simulations: int
    residual_pairs_available: int

    selected_revenue_model: str
    selected_cost_model: str

    shortfall_probability: float
    first_period_shortfall_probability: float

    median_end_cash: float
    p10_end_cash: float
    p90_end_cash: float

    median_min_cash: float
    p10_min_cash: float

    liquidity_buffer_at_confidence: float
    expected_tail_buffer: float

    cash_path_quantiles: list[LiquidityQuantilePoint]


def _model_function(name: str):
    if name == "holt":
        return holt_forecast

    if name == "naive":
        return naive_forecast

    raise ValueError(f"Unsupported forecasting model: {name}")


def _rolling_residuals(
    series: pd.Series,
    model_name: str,
    min_train: int = 6,
) -> dict[int, float]:
    values = (
        pd.to_numeric(series, errors="coerce")
        .astype(float)
        .reset_index(drop=True)
    )

    model_fn = _model_function(model_name)

    residuals: dict[int, float] = {}

    for split in range(min_train, len(values)):
        train = values.iloc[:split]
        actual = float(values.iloc[split])

        try:
            prediction = float(
                model_fn(train, 1)[0]
            )
        except Exception:
            continue

        residuals[split] = actual - prediction

    return residuals


def _paired_residuals(
    df: pd.DataFrame,
    revenue_model: str,
    cost_model: str,
) -> np.ndarray:
    revenue_residuals = _rolling_residuals(
        df["revenue"],
        revenue_model,
    )

    cost_residuals = _rolling_residuals(
        df["operating_cost"],
        cost_model,
    )

    common_indices = sorted(
        set(revenue_residuals)
        & set(cost_residuals)
    )

    if len(common_indices) < 3:
        raise ValueError(
            "Not enough paired forecast errors for Monte Carlo simulation."
        )

    return np.asarray(
        [
            [
                revenue_residuals[index],
                cost_residuals[index],
            ]
            for index in common_indices
        ],
        dtype=float,
    )


def _receivable_adjustments(
    latest_receivables: float,
    delay_days: int,
    horizon: int,
) -> np.ndarray:
    adjustments = np.zeros(
        horizon,
        dtype=float,
    )

    if delay_days <= 0 or latest_receivables <= 0:
        return adjustments

    delay_periods = max(
        1,
        ceil(delay_days / 30),
    )

    # Cash is delayed from the first expected collection period.
    adjustments[0] -= latest_receivables

    # It returns when the delay has elapsed if that point is
    # inside the simulation horizon.
    recovery_index = delay_periods

    if recovery_index < horizon:
        adjustments[recovery_index] += latest_receivables

    return adjustments


def simulate_liquidity(
    df: pd.DataFrame,
    config: SimulationInput,
) -> LiquiditySimulationResult:
    if df.empty:
        raise ValueError(
            "Cannot simulate liquidity from empty data."
        )

    revenue_forecast = forecast_metric(
        df,
        "revenue",
        horizon=config.horizon,
    )

    cost_forecast = forecast_metric(
        df,
        "operating_cost",
        horizon=config.horizon,
    )

    baseline_revenue = np.asarray(
        [
            point.value
            for point in revenue_forecast.forecasts
        ],
        dtype=float,
    )

    baseline_cost = np.asarray(
        [
            point.value
            for point in cost_forecast.forecasts
        ],
        dtype=float,
    )

    residual_pairs = _paired_residuals(
        df,
        revenue_forecast.selected_model,
        cost_forecast.selected_model,
    )

    rng = np.random.default_rng(
        config.seed
    )

    sampled_indices = rng.integers(
        0,
        len(residual_pairs),
        size=(
            config.simulations,
            config.horizon,
        ),
    )

    sampled_errors = residual_pairs[
        sampled_indices
    ]

    revenue_errors = sampled_errors[:, :, 0]
    cost_errors = sampled_errors[:, :, 1]

    simulated_revenue = (
        baseline_revenue[None, :]
        + revenue_errors
    )

    simulated_cost = (
        baseline_cost[None, :]
        + cost_errors
    )

    # Financial values cannot become negative purely because
    # of forecast-error sampling.
    simulated_revenue = np.maximum(
        simulated_revenue,
        0.0,
    )

    simulated_cost = np.maximum(
        simulated_cost,
        0.0,
    )

    simulated_revenue *= (
        1.0 + config.revenue_change
    )

    simulated_cost *= (
        1.0 + config.cost_change
    )

    latest_receivables = float(
        df["receivables"].iloc[-1]
    )

    receivable_adjustments = (
        _receivable_adjustments(
            latest_receivables,
            config.receivable_delay_days,
            config.horizon,
        )
    )

    net_cash_flows = (
        simulated_revenue
        - simulated_cost
        + receivable_adjustments[None, :]
    )

    starting_cash = float(
        df["cash_balance"].iloc[-1]
    )

    cash_paths = (
        starting_cash
        + np.cumsum(
            net_cash_flows,
            axis=1,
        )
    )

    min_cash_by_path = np.min(
        cash_paths,
        axis=1,
    )

    end_cash = cash_paths[:, -1]

    shortfall_matrix = (
        cash_paths
        < config.cash_floor
    )

    any_shortfall = np.any(
        shortfall_matrix,
        axis=1,
    )

    shortfall_probability = float(
        np.mean(any_shortfall)
    )

    first_period_shortfall_probability = float(
        np.mean(shortfall_matrix[:, 0])
    )

    # Required extra liquidity for each path to keep the
    # entire path above the selected cash floor.
    required_buffer_by_path = np.maximum(
        0.0,
        config.cash_floor
        - min_cash_by_path,
    )

    liquidity_buffer_at_confidence = float(
        np.quantile(
            required_buffer_by_path,
            config.confidence_level,
        )
    )

    tail_cutoff = np.quantile(
        required_buffer_by_path,
        config.confidence_level,
    )

    tail_buffers = required_buffer_by_path[
        required_buffer_by_path
        >= tail_cutoff
    ]

    expected_tail_buffer = float(
        tail_buffers.mean()
        if len(tail_buffers)
        else 0.0
    )

    quantiles: list[LiquidityQuantilePoint] = []

    for period in range(config.horizon):
        period_cash = cash_paths[:, period]

        quantiles.append(
            LiquidityQuantilePoint(
                period=period + 1,
                p10_cash=float(
                    np.quantile(
                        period_cash,
                        0.10,
                    )
                ),
                p50_cash=float(
                    np.quantile(
                        period_cash,
                        0.50,
                    )
                ),
                p90_cash=float(
                    np.quantile(
                        period_cash,
                        0.90,
                    )
                ),
                shortfall_probability=float(
                    np.mean(
                        period_cash
                        < config.cash_floor
                    )
                ),
            )
        )

    return LiquiditySimulationResult(
        inputs=config,

        simulations=config.simulations,
        residual_pairs_available=len(
            residual_pairs
        ),

        selected_revenue_model=(
            revenue_forecast.selected_model
        ),
        selected_cost_model=(
            cost_forecast.selected_model
        ),

        shortfall_probability=(
            shortfall_probability
        ),

        first_period_shortfall_probability=(
            first_period_shortfall_probability
        ),

        median_end_cash=float(
            np.quantile(
                end_cash,
                0.50,
            )
        ),

        p10_end_cash=float(
            np.quantile(
                end_cash,
                0.10,
            )
        ),

        p90_end_cash=float(
            np.quantile(
                end_cash,
                0.90,
            )
        ),

        median_min_cash=float(
            np.quantile(
                min_cash_by_path,
                0.50,
            )
        ),

        p10_min_cash=float(
            np.quantile(
                min_cash_by_path,
                0.10,
            )
        ),

        liquidity_buffer_at_confidence=(
            liquidity_buffer_at_confidence
        ),

        expected_tail_buffer=(
            expected_tail_buffer
        ),

        cash_path_quantiles=quantiles,
    )
