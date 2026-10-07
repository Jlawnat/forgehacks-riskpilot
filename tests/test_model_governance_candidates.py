import numpy as np
import pandas as pd

from src.forecasting.models import (
    damped_holt_forecast,
    drift_forecast,
    holt_forecast,
    naive_forecast,
    ses_forecast,
)
from src.forecasting.validation import (
    evaluate_candidate_models,
)


def _series() -> pd.Series:
    return pd.Series(
        [
            100.0,
            103.0,
            105.0,
            108.0,
            111.0,
            113.0,
            116.0,
            118.0,
            121.0,
            123.0,
            125.0,
            128.0,
        ]
    )


def test_candidate_pool_contains_five_models():
    scores = evaluate_candidate_models(
        _series()
    )

    assert {
        score.name
        for score in scores
    } == {
        "naive",
        "drift",
        "ses",
        "holt",
        "damped_holt",
    }


def test_candidate_scores_are_sorted_by_mae():
    scores = evaluate_candidate_models(
        _series()
    )

    maes = [
        score.mae
        for score in scores
    ]

    assert maes == sorted(maes)


def test_all_candidate_models_return_requested_horizon():
    series = _series()

    functions = [
        naive_forecast,
        drift_forecast,
        ses_forecast,
        holt_forecast,
        damped_holt_forecast,
    ]

    for model_fn in functions:
        forecast = model_fn(
            series,
            3,
        )

        assert len(forecast) == 3
        assert np.isfinite(
            forecast
        ).all()
