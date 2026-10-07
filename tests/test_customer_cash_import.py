from datetime import date

import pandas as pd
import pytest

from src.core.direct_cash import (
    build_direct_cash_forecast,
)
from src.ingestion.customer_cash import (
    build_customer_cash_events,
    build_customer_import_report,
    build_customer_scenario,
    parse_customer_cash_csv,
)


def _csv() -> bytes:
    return b"""event_id,date,amount,direction,category,source_type,status,source_reference
invoice-1,2026-10-06,25000,INFLOW,customer receipts,COMMITTED,ACTIVE,ar-ledger
payroll-1,2026-10-09,18000,OUTFLOW,payroll,COMMITTED,ACTIVE,payroll
sales-1,2026-10-13,12000,INFLOW,residual sales receipts,MODELLED,ACTIVE,sales-model
supplier-1,2026-10-16,9000,OUTFLOW,supplier payments,COMMITTED,ACTIVE,ap-ledger
"""


def test_customer_csv_parses_and_preserves_evidence():
    df = parse_customer_cash_csv(
        _csv()
    )

    events = build_customer_cash_events(
        df,
        upload_reference="upload:test.csv",
    )

    assert len(events) == 4

    assert (
        events[0].source_type
        == "COMMITTED"
    )

    assert (
        events[2].source_type
        == "MODELLED"
    )

    assert (
        events[1].direction
        == "OUTFLOW"
    )


def test_customer_import_report_counts_evidence():
    df = parse_customer_cash_csv(
        _csv()
    )

    events = build_customer_cash_events(
        df,
        upload_reference="upload:test.csv",
    )

    report = build_customer_import_report(
        events,
        forecast_start=date(
            2026,
            10,
            5,
        ),
    )

    assert report.rows_loaded == 4
    assert report.active_events == 4
    assert report.committed_events == 3
    assert report.modelled_events == 1
    assert report.forecast_horizon_events == 4


def test_customer_scenario_runs_existing_direct_cash_engine():
    df = parse_customer_cash_csv(
        _csv()
    )

    events = build_customer_cash_events(
        df,
        upload_reference="upload:test.csv",
    )

    scenario = build_customer_scenario(
        company_name="Pilot Company",
        forecast_start=date(
            2026,
            10,
            5,
        ),
        opening_cash=100000.0,
        management_reserve=40000.0,
        max_breach_probability=0.10,
        uncertainty_profile_name="Standard",
        events=events,
    )

    result = build_direct_cash_forecast(
        scenario.forecast_input
    )

    assert result.opening_cash == 100000.0
    assert len(result.weeks) == 13

    # W1:
    # +25k committed receipt
    # -18k payroll
    assert (
        result.weeks[0].closing_cash
        == pytest.approx(
            107000.0
        )
    )

    # W2:
    # +12k modelled receipt
    # -9k supplier payment
    assert (
        result.weeks[1].closing_cash
        == pytest.approx(
            110000.0
        )
    )


def test_customer_csv_rejects_bad_direction():
    df = pd.DataFrame(
        [
            {
                "date": "2026-10-06",
                "amount": 1000,
                "direction": "SIDEWAYS",
                "category": "test",
                "source_type": "COMMITTED",
            }
        ]
    )

    with pytest.raises(
        ValueError,
        match="direction",
    ):
        build_customer_cash_events(
            df,
            upload_reference="upload:test.csv",
        )


def test_customer_csv_rejects_missing_required_column():
    bad = b"""date,amount,direction,category
2026-10-06,1000,INFLOW,receipt
"""

    with pytest.raises(
        ValueError,
        match="Missing required columns",
    ):
        parse_customer_cash_csv(
            bad
        )


def test_active_event_before_forecast_start_is_rejected():
    raw = b"""date,amount,direction,category,source_type
2026-10-01,1000,INFLOW,receipt,COMMITTED
"""

    df = parse_customer_cash_csv(
        raw
    )

    events = build_customer_cash_events(
        df,
        upload_reference="upload:test.csv",
    )

    with pytest.raises(
        ValueError,
        match="before the forecast start date",
    ):
        build_customer_import_report(
            events,
            forecast_start=date(
                2026,
                10,
                5,
            ),
        )
