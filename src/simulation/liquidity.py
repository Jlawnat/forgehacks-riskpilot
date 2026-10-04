from __future__ import annotations


import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from src.core.receivables import (
    fractional_receivable_delay_adjustments,
)
from src.core.context import (
    ForecastContext,
    build_forecast_context,
)


class SimulationInput(BaseModel):
    revenue_change: float = Field(
        default=0.0,
        ge=-1.0,
        le=2.0,
    )

    cost_change: float = Field(
        default=0.0,
        ge=-1.0,
        le=2.0,
    )

    receivable_delay_days: int = Field(
        default=0,
        ge=0,
        le=180,
    )

    horizon: int = Field(
        default=3,
        ge=1,
        le=12,
    )

    simulations: int = Field(
        default=5000,
        ge=100,
        le=50000,
    )

    seed: int = 42

    cash_floor: float = 0.0

    initial_liquidity_injection: float = Field(
        default=0.0,
        ge=0.0,
    )

    confidence_level: float = Field(
        default=0.95,
        gt=0.5,
        lt=1.0,
    )


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

    cash_path_quantiles: list[
        LiquidityQuantilePoint
    ]



def simulate_liquidity_from_context(
    context: ForecastContext,
    config: SimulationInput,
) -> LiquiditySimulationResult:
    """
    Run Monte Carlo liquidity analysis using an already-prepared
    ForecastContext.

    No forecasting models are refitted here.
    """

    if (
        config.horizon
        != context.horizon
    ):
        raise ValueError(
            "Simulation horizon does not match "
            "the prepared forecast context."
        )

    baseline_revenue = np.asarray(
        [
            point.value
            for point
            in context
            .revenue_forecast
            .forecasts
        ],
        dtype=float,
    )

    baseline_cost = np.asarray(
        [
            point.value
            for point
            in context
            .cost_forecast
            .forecasts
        ],
        dtype=float,
    )

    residual_pairs = np.asarray(
        context.paired_residuals,
        dtype=float,
    )

    if len(residual_pairs) < 3:
        raise ValueError(
            "Not enough paired forecast errors "
            "for Monte Carlo simulation."
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

    sampled_errors = (
        residual_pairs[
            sampled_indices
        ]
    )

    revenue_errors = (
        sampled_errors[
            :,
            :,
            0,
        ]
    )

    cost_errors = (
        sampled_errors[
            :,
            :,
            1,
        ]
    )

    simulated_revenue = (
        baseline_revenue[None, :]
        + revenue_errors
    )

    simulated_cost = (
        baseline_cost[None, :]
        + cost_errors
    )

    # Avoid impossible negative values created purely
    # by residual resampling.
    simulated_revenue = np.maximum(
        simulated_revenue,
        0.0,
    )

    simulated_cost = np.maximum(
        simulated_cost,
        0.0,
    )

    simulated_revenue *= (
        1.0
        + config.revenue_change
    )

    simulated_cost *= (
        1.0
        + config.cost_change
    )

    receivable_adjustments = np.asarray(
        fractional_receivable_delay_adjustments(
            context.latest_receivables,
            config.receivable_delay_days,
            config.horizon,
        ),
        dtype=float,
    )

    net_cash_flows = (
        simulated_revenue
        - simulated_cost
        + receivable_adjustments[
            None,
            :
        ]
    )

    cash_paths = (
        context.starting_cash
        + config.initial_liquidity_injection
        + np.cumsum(
            net_cash_flows,
            axis=1,
        )
    )

    min_cash_by_path = np.min(
        cash_paths,
        axis=1,
    )

    end_cash = (
        cash_paths[:, -1]
    )

    shortfall_matrix = (
        cash_paths
        < config.cash_floor
    )

    any_shortfall = np.any(
        shortfall_matrix,
        axis=1,
    )

    shortfall_probability = float(
        np.mean(
            any_shortfall
        )
    )

    first_period_shortfall_probability = (
        float(
            np.mean(
                shortfall_matrix[
                    :,
                    0,
                ]
            )
        )
    )

    required_buffer_by_path = (
        np.maximum(
            0.0,
            config.cash_floor
            - min_cash_by_path,
        )
    )

    liquidity_buffer_at_confidence = (
        float(
            np.quantile(
                required_buffer_by_path,
                config.confidence_level,
            )
        )
    )

    tail_cutoff = np.quantile(
        required_buffer_by_path,
        config.confidence_level,
    )

    tail_buffers = (
        required_buffer_by_path[
            required_buffer_by_path
            >= tail_cutoff
        ]
    )

    expected_tail_buffer = float(
        tail_buffers.mean()
        if len(tail_buffers)
        else 0.0
    )

    quantiles: list[
        LiquidityQuantilePoint
    ] = []

    for period in range(
        config.horizon
    ):
        period_cash = (
            cash_paths[
                :,
                period,
            ]
        )

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

        simulations=(
            config.simulations
        ),

        residual_pairs_available=(
            len(
                residual_pairs
            )
        ),

        selected_revenue_model=(
            context
            .revenue_forecast
            .selected_model
        ),

        selected_cost_model=(
            context
            .cost_forecast
            .selected_model
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

        cash_path_quantiles=(
            quantiles
        ),
    )


def simulate_liquidity(
    df: pd.DataFrame,
    config: SimulationInput,
) -> LiquiditySimulationResult:
    """
    Backwards-compatible convenience API.

    Higher-level application code should prefer:
        build_forecast_context(...)
        simulate_liquidity_from_context(...)

    so multiple analyses can reuse one model fit.
    """

    if df.empty:
        raise ValueError(
            "Cannot simulate liquidity "
            "from empty data."
        )

    context = (
        build_forecast_context(
            df,
            horizon=config.horizon,
        )
    )

    return (
        simulate_liquidity_from_context(
            context,
            config,
        )
    )
