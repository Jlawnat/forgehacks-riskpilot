from io import BytesIO

import pandas as pd

from src.ingestion.customer_mapping import (
    build_standard_cash_dataframe,
    load_customer_table,
    suggest_mapping,
)


def test_csv_mapping_suggests_common_columns():
    payload = b"""Payment Date,Value,Flow,Account,Confidence
2026-10-07,1000,INFLOW,Customer receipts,COMMITTED
"""

    df = load_customer_table(
        payload,
        filename="cash.csv",
    )

    suggestion = suggest_mapping(
        df
    )

    assert (
        suggestion.date_column
        == "payment_date"
    )

    assert (
        suggestion.amount_column
        == "value"
    )

    assert (
        suggestion.direction_column
        == "flow"
    )

    assert (
        suggestion.category_column
        == "account"
    )

    assert (
        suggestion.source_type_column
        == "confidence"
    )


def test_standard_dataframe_can_use_defaults():
    df = pd.DataFrame(
        {
            "invoice_date": [
                "2026-10-08"
            ],
            "invoice_amount": [
                25000
            ],
            "invoice_number": [
                "INV-001"
            ],
        }
    )

    result = (
        build_standard_cash_dataframe(
            df,
            date_column=(
                "invoice_date"
            ),
            amount_column=(
                "invoice_amount"
            ),
            direction_column=None,
            category_column=None,
            source_type_column=None,
            status_column=None,
            description_column=None,
            source_reference_column=(
                "invoice_number"
            ),
            due_date_column=None,
            expected_cash_date_column=None,
            default_direction="INFLOW",
            default_category=(
                "customer receipts"
            ),
            default_source_type=(
                "COMMITTED"
            ),
        )
    )

    assert (
        result.loc[
            0,
            "direction",
        ]
        == "INFLOW"
    )

    assert (
        result.loc[
            0,
            "category",
        ]
        == "customer receipts"
    )

    assert (
        result.loc[
            0,
            "source_type",
        ]
        == "COMMITTED"
    )


def test_xlsx_upload_is_supported():
    source = pd.DataFrame(
        {
            "Date": [
                "2026-10-07"
            ],
            "Amount": [
                12000
            ],
            "Direction": [
                "OUTFLOW"
            ],
            "Category": [
                "Payroll"
            ],
            "Source Type": [
                "COMMITTED"
            ],
        }
    )

    buffer = BytesIO()

    with pd.ExcelWriter(
        buffer,
        engine="openpyxl",
    ) as writer:
        source.to_excel(
            writer,
            index=False,
            sheet_name="Cash Forecast",
        )

    df = load_customer_table(
        buffer.getvalue(),
        filename="cash.xlsx",
        sheet_name=(
            "Cash Forecast"
        ),
    )

    assert list(
        df.columns
    ) == [
        "date",
        "amount",
        "direction",
        "category",
        "source_type",
    ]


def test_mapping_event_prefix_prevents_cross_file_collision():
    first = pd.DataFrame(
        {
            "date": ["2026-10-07"],
            "amount": [1000],
        }
    )

    second = pd.DataFrame(
        {
            "date": ["2026-10-08"],
            "amount": [2000],
        }
    )

    ar = build_standard_cash_dataframe(
        first,
        date_column="date",
        amount_column="amount",
        direction_column=None,
        category_column=None,
        source_type_column=None,
        status_column=None,
        description_column=None,
        source_reference_column=None,
        due_date_column=None,
        expected_cash_date_column=None,
        default_direction="INFLOW",
        default_category="customer receipts",
        default_source_type="COMMITTED",
        event_id_prefix="ar-file",
    )

    ap = build_standard_cash_dataframe(
        second,
        date_column="date",
        amount_column="amount",
        direction_column=None,
        category_column=None,
        source_type_column=None,
        status_column=None,
        description_column=None,
        source_reference_column=None,
        due_date_column=None,
        expected_cash_date_column=None,
        default_direction="OUTFLOW",
        default_category="supplier payments",
        default_source_type="COMMITTED",
        event_id_prefix="ap-file",
    )

    assert (
        ar.loc[0, "event_id"]
        != ap.loc[0, "event_id"]
    )
