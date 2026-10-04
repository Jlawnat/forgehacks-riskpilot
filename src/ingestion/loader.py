from __future__ import annotations

from pathlib import Path

import pandas as pd


COLUMN_ALIASES = {
    "sales": "revenue",
    "income": "revenue",
    "turnover": "revenue",
    "opex": "operating_cost",
    "operating_expenses": "operating_cost",
    "expenses": "operating_cost",
    "cash": "cash_balance",
    "accounts_receivable": "receivables",
    "ar": "receivables",
}


def normalize_business_dataframe(
    df: pd.DataFrame,
) -> pd.DataFrame:
    if df.empty:
        raise ValueError("CSV contains no rows.")

    normalized = df.copy()

    normalized.columns = [
        str(col).strip().lower().replace(" ", "_")
        for col in normalized.columns
    ]

    normalized = normalized.rename(
        columns=COLUMN_ALIASES
    )

    return normalized


def load_business_csv(
    path: str | Path,
) -> pd.DataFrame:
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"CSV file not found: {path}"
        )

    return normalize_business_dataframe(
        pd.read_csv(path)
    )
