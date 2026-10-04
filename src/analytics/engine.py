from __future__ import annotations

from pathlib import Path

from src.analytics.metrics import calculate_business_metrics
from src.analytics.risk import assess_business_risk
from src.ingestion.loader import load_business_csv
from src.ingestion.validator import validate_business_data
from src.schemas.reports import BusinessHealthReport


def analyse_business(path: str | Path) -> BusinessHealthReport:
    raw = load_business_csv(path)
    cleaned, data_quality = validate_business_data(raw)

    metrics = calculate_business_metrics(cleaned)
    risks = assess_business_risk(metrics)

    return BusinessHealthReport(
        data_quality=data_quality,
        metrics=metrics,
        risks=risks,
    )
