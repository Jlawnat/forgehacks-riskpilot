from __future__ import annotations

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from src.forecasting.models import holt_forecast, naive_forecast
from src.forecasting.validation import evaluate_models


class ForecastPoint(BaseModel):
    period: int = Field(ge=1)
    value: float
    lower: float
    upper: float


class ForecastResult(BaseModel):
    metric: str
    selected_model: str
    validation_mae: float
    horizon: int
    forecasts: list[ForecastPoint]


def forecast_metric(
    df: pd.DataFrame,
    metric: str,
    horizon: int = 3,
) -> ForecastResult:
    if metric not in df.columns:
        raise ValueError(f"Unknown metric: {metric}")

    if horizon < 1:
        raise ValueError("Forecast horizon must be at least 1.")

    series = (
        pd.to_numeric(df[metric], errors="coerce")
        .dropna()
        .astype(float)
        .reset_index(drop=True)
    )

    if len(series) < 7:
        raise ValueError(
            "At least 7 observations are required for validated forecasting."
        )

    scores = evaluate_models(series)
    best = scores[0]

    if best.name == "holt":
        values = holt_forecast(series, horizon)
    else:
        values = naive_forecast(series, horizon)

    residual_scale = best.mae

    points: list[ForecastPoint] = []

    for i, value in enumerate(values, start=1):
        spread = 1.96 * residual_scale * np.sqrt(i)

        points.append(
            ForecastPoint(
                period=i,
                value=float(value),
                lower=float(value - spread),
                upper=float(value + spread),
            )
        )

    return ForecastResult(
        metric=metric,
        selected_model=best.name,
        validation_mae=best.mae,
        horizon=horizon,
        forecasts=points,
    )
