from __future__ import annotations

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import Holt, SimpleExpSmoothing


def naive_forecast(series: pd.Series, horizon: int) -> np.ndarray:
    if series.empty:
        raise ValueError("Cannot forecast an empty series.")

    return np.repeat(float(series.iloc[-1]), horizon)


def holt_forecast(series: pd.Series, horizon: int) -> np.ndarray:
    if len(series) < 4:
        raise ValueError("Holt forecasting requires at least 4 observations.")

    model = Holt(
        series.astype(float),
        initialization_method="estimated",
    ).fit(optimized=True)

    return np.asarray(model.forecast(horizon), dtype=float)



def drift_forecast(
    series: pd.Series,
    horizon: int,
) -> np.ndarray:
    """
    Random-walk-with-drift benchmark.

    Extends the average historical change from the first
    observation to the latest observation.
    """
    if len(series) < 2:
        raise ValueError(
            "Drift forecasting requires at least 2 observations."
        )

    values = series.astype(float)

    slope = (
        float(values.iloc[-1])
        - float(values.iloc[0])
    ) / (len(values) - 1)

    steps = np.arange(
        1,
        horizon + 1,
        dtype=float,
    )

    return (
        float(values.iloc[-1])
        + slope * steps
    )


def ses_forecast(
    series: pd.Series,
    horizon: int,
) -> np.ndarray:
    """
    Simple exponential smoothing level model.
    """
    if len(series) < 3:
        raise ValueError(
            "SES forecasting requires at least 3 observations."
        )

    model = SimpleExpSmoothing(
        series.astype(float),
        initialization_method="estimated",
    ).fit(
        optimized=True,
    )

    return np.asarray(
        model.forecast(horizon),
        dtype=float,
    )


def damped_holt_forecast(
    series: pd.Series,
    horizon: int,
) -> np.ndarray:
    """
    Holt trend model with a damped long-run trend.
    """
    if len(series) < 4:
        raise ValueError(
            "Damped Holt forecasting requires at least 4 observations."
        )

    model = Holt(
        series.astype(float),
        damped_trend=True,
        initialization_method="estimated",
    ).fit(
        optimized=True,
    )

    return np.asarray(
        model.forecast(horizon),
        dtype=float,
    )
