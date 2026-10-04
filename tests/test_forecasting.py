from src.forecasting.forecast import forecast_metric
from src.ingestion.loader import load_business_csv
from src.ingestion.validator import validate_business_data


def _load_demo():
    raw = load_business_csv("data/demo/fragile_business.csv")
    cleaned, _ = validate_business_data(raw)
    return cleaned


def test_revenue_forecast_returns_three_periods():
    df = _load_demo()

    result = forecast_metric(df, "revenue", horizon=3)

    assert result.metric == "revenue"
    assert result.horizon == 3
    assert len(result.forecasts) == 3
    assert result.validation_mae >= 0


def test_forecast_intervals_are_ordered():
    df = _load_demo()

    result = forecast_metric(df, "revenue", horizon=3)

    for point in result.forecasts:
        assert point.lower <= point.value <= point.upper


def test_forecast_model_is_known():
    df = _load_demo()

    result = forecast_metric(df, "revenue", horizon=3)

    assert result.selected_model in {"naive", "holt"}
