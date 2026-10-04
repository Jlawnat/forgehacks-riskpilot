from __future__ import annotations

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import Holt


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
