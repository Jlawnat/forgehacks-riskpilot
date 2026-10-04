from src.analytics.metrics import calculate_business_metrics
from src.analytics.risk import assess_business_risk
from src.ingestion.loader import load_business_csv
from src.ingestion.validator import validate_business_data


def _load_demo():
    df = load_business_csv("data/demo/fragile_business.csv")
    cleaned, _ = validate_business_data(df)
    return cleaned


def test_metrics_are_calculated():
    df = _load_demo()

    metrics = calculate_business_metrics(df)

    assert metrics.latest_revenue == 42100
    assert metrics.latest_operating_cost == 52600
    assert metrics.latest_cash_balance == 23500
    assert metrics.latest_receivables == 32800

    assert metrics.revenue_growth is not None
    assert metrics.revenue_growth < 0

    assert metrics.cost_to_revenue_ratio is not None
    assert metrics.cost_to_revenue_ratio > 1

    assert metrics.cash_runway_months is not None
    assert metrics.cash_runway_months > 0


def test_fragile_business_is_high_risk():
    df = _load_demo()

    metrics = calculate_business_metrics(df)
    risks = assess_business_risk(metrics)

    assert risks.liquidity_risk == "high"
    assert risks.revenue_risk in {"medium", "high"}
    assert risks.cost_pressure_risk == "high"
    assert risks.receivables_risk == "high"
    assert risks.overall_risk == "high"


def test_zero_shock_data_does_not_mutate_metrics():
    df = _load_demo()

    first = calculate_business_metrics(df)
    second = calculate_business_metrics(df.copy())

    assert first == second
