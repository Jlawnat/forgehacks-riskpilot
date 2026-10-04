from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

import numpy as np
import pandas as pd

from src.forecasting.forecast import (
    ForecastPoint,
    ForecastResult,
)
from src.forecasting.models import (
    holt_forecast,
    naive_forecast,
)
from src.forecasting.validation import (
    ModelScore,
    evaluate_models,
)


@dataclass(frozen=True)
class ForecastContext:
    """
    Expensive forecasting work prepared once and reused by
    stress testing, Monte Carlo simulation and optimisation.
    """

    dataset_fingerprint: str
    horizon: int

    starting_cash: float
    latest_receivables: float

    revenue_forecast: ForecastResult
    cost_forecast: ForecastResult

    revenue_scores: tuple[ModelScore, ...]
    cost_scores: tuple[ModelScore, ...]

    paired_residuals: tuple[
        tuple[float, float],
        ...
    ]


def dataframe_fingerprint(
    df: pd.DataFrame,
) -> str:
    """
    Stable fingerprint for caching analytical results.
    """
    if df.empty:
        raise ValueError(
            "Cannot fingerprint an empty dataframe."
        )

    hashed_rows = pd.util.hash_pandas_object(
        df,
        index=True,
    ).values

    digest = sha256()

    digest.update(
        hashed_rows.tobytes()
    )

    digest.update(
        "|".join(
            map(str, df.columns)
        ).encode()
    )

    return digest.hexdigest()


def _clean_series(
    series: pd.Series,
) -> pd.Series:
    return (
        pd.to_numeric(
            series,
            errors="coerce",
        )
        .dropna()
        .astype(float)
        .reset_index(drop=True)
    )


def _model_function(
    name: str,
):
    if name == "holt":
        return holt_forecast

    if name == "naive":
        return naive_forecast

    raise ValueError(
        f"Unsupported forecasting model: {name}"
    )


def _forecast_from_scores(
    series: pd.Series,
    metric: str,
    horizon: int,
    scores: list[ModelScore],
) -> ForecastResult:
    if not scores:
        raise ValueError(
            "No forecasting scores are available."
        )

    cleaned = _clean_series(series)

    best = scores[0]

    model_fn = _model_function(
        best.name
    )

    values = model_fn(
        cleaned,
        horizon,
    )

    points: list[ForecastPoint] = []

    for period, value in enumerate(
        values,
        start=1,
    ):
        # Same uncertainty convention used by the existing
        # forecasting engine.
        spread = (
            1.96
            * best.mae
            * np.sqrt(period)
        )

        points.append(
            ForecastPoint(
                period=period,
                value=float(value),
                lower=float(
                    value - spread
                ),
                upper=float(
                    value + spread
                ),
            )
        )

    return ForecastResult(
        metric=metric,
        selected_model=best.name,
        validation_mae=float(
            best.mae
        ),
        horizon=horizon,
        forecasts=points,
    )


def _rolling_residuals(
    series: pd.Series,
    model_name: str,
    min_train: int = 6,
) -> dict[int, float]:
    values = _clean_series(series)

    model_fn = _model_function(
        model_name
    )

    residuals: dict[int, float] = {}

    for split in range(
        min_train,
        len(values),
    ):
        train = values.iloc[:split]

        actual = float(
            values.iloc[split]
        )

        try:
            prediction = float(
                model_fn(
                    train,
                    1,
                )[0]
            )
        except Exception:
            continue

        residuals[split] = (
            actual - prediction
        )

    return residuals


def _paired_residuals(
    df: pd.DataFrame,
    revenue_model: str,
    cost_model: str,
) -> tuple[
    tuple[float, float],
    ...
]:
    revenue_residuals = (
        _rolling_residuals(
            df["revenue"],
            revenue_model,
        )
    )

    cost_residuals = (
        _rolling_residuals(
            df["operating_cost"],
            cost_model,
        )
    )

    common = sorted(
        set(revenue_residuals)
        & set(cost_residuals)
    )

    if len(common) < 3:
        raise ValueError(
            "Not enough paired forecast errors "
            "for uncertainty analysis."
        )

    return tuple(
        (
            float(
                revenue_residuals[index]
            ),
            float(
                cost_residuals[index]
            ),
        )
        for index in common
    )


def build_forecast_context(
    df: pd.DataFrame,
    horizon: int = 3,
) -> ForecastContext:
    """
    Prepare expensive forecast information once.

    Future engines should consume this context instead
    of independently re-fitting forecast models.
    """
    if df.empty:
        raise ValueError(
            "Cannot build context from empty data."
        )

    if horizon < 1:
        raise ValueError(
            "Forecast horizon must be positive."
        )

    required = {
        "revenue",
        "operating_cost",
        "cash_balance",
        "receivables",
    }

    missing = (
        required
        - set(df.columns)
    )

    if missing:
        raise ValueError(
            "Missing required columns: "
            + ", ".join(
                sorted(missing)
            )
        )

    revenue_series = _clean_series(
        df["revenue"]
    )

    cost_series = _clean_series(
        df["operating_cost"]
    )

    # Evaluate each model family once.
    revenue_scores = evaluate_models(
        revenue_series
    )

    cost_scores = evaluate_models(
        cost_series
    )

    revenue_forecast = (
        _forecast_from_scores(
            revenue_series,
            "revenue",
            horizon,
            revenue_scores,
        )
    )

    cost_forecast = (
        _forecast_from_scores(
            cost_series,
            "operating_cost",
            horizon,
            cost_scores,
        )
    )

    paired_residuals = (
        _paired_residuals(
            df,
            revenue_forecast
            .selected_model,
            cost_forecast
            .selected_model,
        )
    )

    return ForecastContext(
        dataset_fingerprint=(
            dataframe_fingerprint(df)
        ),
        horizon=horizon,

        starting_cash=float(
            df["cash_balance"]
            .iloc[-1]
        ),

        latest_receivables=float(
            df["receivables"]
            .iloc[-1]
        ),

        revenue_forecast=(
            revenue_forecast
        ),

        cost_forecast=(
            cost_forecast
        ),

        revenue_scores=tuple(
            revenue_scores
        ),

        cost_scores=tuple(
            cost_scores
        ),

        paired_residuals=(
            paired_residuals
        ),
    )
