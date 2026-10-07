import pandas as pd
import pytest

from src.ingestion.customer_multi_source import (
    get_source_profile,
    merge_standardized_sources,
)


def test_standard_source_profiles_are_available():
    ar = get_source_profile("ar")
    ap = get_source_profile("ap")
    payroll = get_source_profile("payroll")

    assert ar.default_direction == "INFLOW"
    assert ar.default_source_type == "COMMITTED"

    assert ap.default_direction == "OUTFLOW"
    assert payroll.default_category == "payroll"


def test_multiple_standardized_sources_merge():
    ar = pd.DataFrame(
        {
            "event_id": ["ar-0001"],
            "date": ["2026-10-07"],
            "amount": [10000],
            "direction": ["INFLOW"],
            "category": ["customer receipts"],
            "source_type": ["COMMITTED"],
        }
    )

    ap = pd.DataFrame(
        {
            "event_id": ["ap-0001"],
            "date": ["2026-10-09"],
            "amount": [6000],
            "direction": ["OUTFLOW"],
            "category": ["supplier payments"],
            "source_type": ["COMMITTED"],
        }
    )

    merged = merge_standardized_sources(
        (
            ("ar.xlsx", ar),
            ("ap.xlsx", ap),
        )
    )

    assert len(merged) == 2

    assert set(
        merged["_riskpilot_source_file"]
    ) == {
        "ar.xlsx",
        "ap.xlsx",
    }


def test_duplicate_event_ids_across_sources_are_rejected():
    first = pd.DataFrame(
        {
            "event_id": ["duplicate-1"],
        }
    )

    second = pd.DataFrame(
        {
            "event_id": ["duplicate-1"],
        }
    )

    with pytest.raises(
        ValueError,
        match="duplicate cash event IDs",
    ):
        merge_standardized_sources(
            (
                ("first.csv", first),
                ("second.csv", second),
            )
        )
