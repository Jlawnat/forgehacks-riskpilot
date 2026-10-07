from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from src.forecasting.models import holt_forecast, naive_forecast


ForecastFn = Callable[[pd.Series, int], np.ndarray]


@dataclass(frozen=True)
class ModelScore:
    name: str
    mae: float


def _mae(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.mean(np.abs(actual - predicted)))


def _rolling_one_step_mae(
    series: pd.Series,
    model_fn: ForecastFn,
    min_train: int = 6,
) -> float:
    if len(series) <= min_train:
        raise ValueError("Not enough observations for rolling validation.")

    errors: list[float] = []

    for split in range(min_train, len(series)):
        train = series.iloc[:split]
        actual = float(series.iloc[split])

        try:
            predicted = float(model_fn(train, 1)[0])
        except Exception:
            continue

        errors.append(abs(actual - predicted))

    if not errors:
        raise ValueError("Model could not be evaluated.")

    return float(np.mean(errors))


def evaluate_models(series: pd.Series) -> list[ModelScore]:
    models: dict[str, ForecastFn] = {
        "naive": naive_forecast,
        "holt": holt_forecast,
    }

    scores: list[ModelScore] = []

    for name, fn in models.items():
        try:
            score = _rolling_one_step_mae(series, fn)
        except Exception:
            continue

        scores.append(ModelScore(name=name, mae=score))

    if not scores:
        raise ValueError("No forecasting model could be evaluated.")

    return sorted(scores, key=lambda item: item.mae)



# ---------------------------------------------------------------------
# MODEL GOVERNANCE / SHADOW CANDIDATE EVALUATION
# ---------------------------------------------------------------------

from src.forecasting.models import (
    damped_holt_forecast,
    drift_forecast,
    ses_forecast,
)


_CANDIDATE_MODEL_FUNCTIONS = {
    "naive": naive_forecast,
    "drift": drift_forecast,
    "ses": ses_forecast,
    "holt": holt_forecast,
    "damped_holt": damped_holt_forecast,
}


def _candidate_rolling_mae(
    series: pd.Series,
    model_fn,
    *,
    min_train: int = 6,
) -> float:
    """
    One-step rolling-origin out-of-sample MAE used only
    for model-governance comparison.
    """
    values = (
        pd.to_numeric(
            series,
            errors="coerce",
        )
        .dropna()
        .astype(float)
        .reset_index(drop=True)
    )

    if len(values) <= min_train:
        raise ValueError(
            "Not enough observations for rolling validation."
        )

    errors: list[float] = []

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

        if np.isfinite(prediction):
            errors.append(
                abs(actual - prediction)
            )

    if not errors:
        raise ValueError(
            "Model produced no valid rolling predictions."
        )

    return float(
        np.mean(errors)
    )


def evaluate_candidate_models(
    series: pd.Series,
    *,
    min_train: int = 6,
) -> list[ModelScore]:
    """
    Evaluate the broader transparent forecasting candidate pool.

    These scores are for model governance / shadow validation.
    They do NOT automatically promote a model into the production
    forecasting engine.
    """
    scores: list[ModelScore] = []

    for name, model_fn in (
        _CANDIDATE_MODEL_FUNCTIONS.items()
    ):
        try:
            mae = _candidate_rolling_mae(
                series,
                model_fn,
                min_train=min_train,
            )
        except Exception:
            continue

        scores.append(
            ModelScore(
                name=name,
                mae=mae,
            )
        )

    if not scores:
        raise ValueError(
            "No candidate forecasting model could be evaluated."
        )

    return sorted(
        scores,
        key=lambda score: (
            score.mae,
            score.name,
        ),
    )
