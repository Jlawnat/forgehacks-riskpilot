import pandas as pd
import pytest

from src.ingestion.loader import load_business_csv
from src.ingestion.validator import validate_business_data


def test_load_demo_csv():
    df = load_business_csv("data/demo/fragile_business.csv")

    assert len(df) == 18
    assert "revenue" in df.columns
    assert "operating_cost" in df.columns


def test_validate_demo_csv():
    df = load_business_csv("data/demo/fragile_business.csv")
    cleaned, report = validate_business_data(df)

    assert len(cleaned) == 18
    assert report.periods_loaded == 18
    assert report.missing_values == 0
    assert report.duplicate_periods == 0


def test_missing_required_column():
    df = pd.DataFrame(
        {
            "date": ["2026-01-01"],
            "revenue": [1000],
        }
    )

    with pytest.raises(ValueError, match="Missing required columns"):
        validate_business_data(df)
