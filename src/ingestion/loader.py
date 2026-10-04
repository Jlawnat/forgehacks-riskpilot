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


def load_business_csv(path: str | Path) -> pd.DataFrame:
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    df = pd.read_csv(path)

    if df.empty:
        raise ValueError("CSV contains no rows.")

    df.columns = [
        str(col).strip().lower().replace(" ", "_")
        for col in df.columns
    ]

    df = df.rename(columns=COLUMN_ALIASES)

    return df
