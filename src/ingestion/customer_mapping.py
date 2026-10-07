from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict


SupportedFileType = Literal[
    "csv",
    "xlsx",
]


class MappingSuggestion(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    date_column: str | None = None
    amount_column: str | None = None
    direction_column: str | None = None
    category_column: str | None = None
    source_type_column: str | None = None
    status_column: str | None = None
    description_column: str | None = None
    source_reference_column: str | None = None
    due_date_column: str | None = None
    expected_cash_date_column: str | None = None


COLUMN_HINTS = {
    "date": (
        "date",
        "cash_date",
        "payment_date",
        "receipt_date",
        "transaction_date",
        "expected_date",
        "forecast_date",
    ),
    "amount": (
        "amount",
        "cash_amount",
        "value",
        "payment_amount",
        "receipt_amount",
        "invoice_amount",
        "total",
    ),
    "direction": (
        "direction",
        "cash_direction",
        "type",
        "flow",
        "inflow_outflow",
    ),
    "category": (
        "category",
        "cash_category",
        "account",
        "account_name",
        "expense_type",
        "payment_type",
        "transaction_type",
    ),
    "source_type": (
        "source_type",
        "evidence_type",
        "confidence",
        "forecast_type",
        "source_classification",
    ),
    "status": (
        "status",
        "payment_status",
        "invoice_status",
    ),
    "description": (
        "description",
        "memo",
        "notes",
        "reference_text",
        "details",
    ),
    "source_reference": (
        "source_reference",
        "reference",
        "invoice_number",
        "invoice_no",
        "payment_reference",
        "document_id",
    ),
    "due_date": (
        "due_date",
        "invoice_due_date",
        "payment_due_date",
    ),
    "expected_cash_date": (
        "expected_cash_date",
        "expected_date",
        "collection_date",
        "expected_payment_date",
    ),
}


def _normalize_column(
    value: object,
) -> str:
    return (
        str(value)
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("/", "_")
    )


def load_customer_table(
    data: bytes,
    *,
    filename: str,
    sheet_name: str | int | None = 0,
) -> pd.DataFrame:
    suffix = (
        Path(filename)
        .suffix
        .lower()
    )

    if suffix == ".csv":
        df = pd.read_csv(
            BytesIO(data)
        )

    elif suffix in {
        ".xlsx",
        ".xlsm",
    }:
        df = pd.read_excel(
            BytesIO(data),
            sheet_name=sheet_name,
            engine="openpyxl",
        )

    else:
        raise ValueError(
            "Supported files are CSV and XLSX."
        )

    if df.empty:
        raise ValueError(
            "Uploaded file contains no rows."
        )

    cleaned = df.copy()

    cleaned.columns = [
        _normalize_column(column)
        for column in cleaned.columns
    ]

    if len(
        set(cleaned.columns)
    ) != len(cleaned.columns):
        raise ValueError(
            "The uploaded file contains duplicate "
            "column names after normalization."
        )

    return cleaned


def list_excel_sheets(
    data: bytes,
) -> tuple[str, ...]:
    workbook = pd.ExcelFile(
        BytesIO(data),
        engine="openpyxl",
    )

    return tuple(
        workbook.sheet_names
    )


def suggest_mapping(
    df: pd.DataFrame,
) -> MappingSuggestion:
    columns = list(
        df.columns
    )

    def choose(
        target: str,
    ) -> str | None:
        hints = COLUMN_HINTS[
            target
        ]

        for hint in hints:
            if hint in columns:
                return hint

        for column in columns:
            for hint in hints:
                if (
                    hint in column
                    or column in hint
                ):
                    return column

        return None

    return MappingSuggestion(
        date_column=choose(
            "date"
        ),
        amount_column=choose(
            "amount"
        ),
        direction_column=choose(
            "direction"
        ),
        category_column=choose(
            "category"
        ),
        source_type_column=choose(
            "source_type"
        ),
        status_column=choose(
            "status"
        ),
        description_column=choose(
            "description"
        ),
        source_reference_column=choose(
            "source_reference"
        ),
        due_date_column=choose(
            "due_date"
        ),
        expected_cash_date_column=choose(
            "expected_cash_date"
        ),
    )


def _blank_series(
    df: pd.DataFrame,
) -> pd.Series:
    return pd.Series(
        [""] * len(df),
        index=df.index,
        dtype="object",
    )


def build_standard_cash_dataframe(
    df: pd.DataFrame,
    *,
    date_column: str,
    amount_column: str,
    direction_column: str | None,
    category_column: str | None,
    source_type_column: str | None,
    status_column: str | None,
    description_column: str | None,
    source_reference_column: str | None,
    due_date_column: str | None,
    expected_cash_date_column: str | None,
    default_direction: str | None,
    default_category: str,
    default_source_type: str,
    event_id_prefix: str = "mapped-event",
) -> pd.DataFrame:
    required = {
        date_column,
        amount_column,
    }

    missing = required - set(
        df.columns
    )

    if missing:
        raise ValueError(
            "Mapped column not found: "
            + ", ".join(
                sorted(missing)
            )
        )

    standardized = pd.DataFrame(
        index=df.index
    )

    standardized[
        "date"
    ] = df[
        date_column
    ]

    standardized[
        "amount"
    ] = df[
        amount_column
    ]

    if direction_column:
        standardized[
            "direction"
        ] = df[
            direction_column
        ]
    else:
        if not default_direction:
            raise ValueError(
                "Direction must either be mapped "
                "to a column or supplied as a default."
            )

        standardized[
            "direction"
        ] = default_direction

    if category_column:
        standardized[
            "category"
        ] = df[
            category_column
        ]
    else:
        standardized[
            "category"
        ] = default_category

    if source_type_column:
        standardized[
            "source_type"
        ] = df[
            source_type_column
        ]
    else:
        standardized[
            "source_type"
        ] = default_source_type

    standardized[
        "status"
    ] = (
        df[
            status_column
        ]
        if status_column
        else "ACTIVE"
    )

    standardized[
        "description"
    ] = (
        df[
            description_column
        ]
        if description_column
        else _blank_series(df)
    )

    standardized[
        "source_reference"
    ] = (
        df[
            source_reference_column
        ]
        if source_reference_column
        else _blank_series(df)
    )

    standardized[
        "due_date"
    ] = (
        df[
            due_date_column
        ]
        if due_date_column
        else _blank_series(df)
    )

    standardized[
        "expected_cash_date"
    ] = (
        df[
            expected_cash_date_column
        ]
        if expected_cash_date_column
        else _blank_series(df)
    )

    safe_prefix = (
        "".join(
            char.lower()
            if char.isalnum()
            else "-"
            for char in event_id_prefix
        )
        .strip("-")
        or "mapped-event"
    )

    standardized[
        "event_id"
    ] = [
        f"{safe_prefix}-{i + 1:04d}"
        for i in range(
            len(
                standardized
            )
        )
    ]

    return standardized[
        [
            "event_id",
            "date",
            "amount",
            "direction",
            "category",
            "source_type",
            "status",
            "description",
            "source_reference",
            "due_date",
            "expected_cash_date",
        ]
    ]
