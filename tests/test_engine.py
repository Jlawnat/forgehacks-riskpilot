from src.analytics.engine import analyse_business


def test_analyse_business_returns_complete_report():
    report = analyse_business("data/demo/fragile_business.csv")

    assert report.data_quality.periods_loaded == 18
    assert report.metrics.latest_revenue == 42100
    assert report.risks.overall_risk == "high"


def test_report_serializes_to_json():
    report = analyse_business("data/demo/fragile_business.csv")

    payload = report.model_dump()

    assert "data_quality" in payload
    assert "metrics" in payload
    assert "risks" in payload
