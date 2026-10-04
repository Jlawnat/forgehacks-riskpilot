from __future__ import annotations

import pandas as pd

from src.schemas.reports import DataQualityReport


REQUIRED_COLUMNS = {
    "date",
    "revenue",
    "operating_cost",
    "cash_balance",
    "receivables",
}


def validate_business_data(df: pd.DataFrame) -> tuple[pd.DataFrame, DataQualityReport]:
    missing_columns = REQUIRED_COLUMNS - set(df.columns)

    if missing_columns:
        raise ValueError(
            "Missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    cleaned = df.copy()

    cleaned["date"] = pd.to_datetime(cleaned["date"], errors="coerce")

    if cleaned["date"].isna().any():
        raise ValueError("One or more dates could not be parsed.")

    numeric_columns = [
        "revenue",
        "operating_cost",
        "cash_balance",
        "receivables",
    ]

    for col in numeric_columns:
        cleaned[col] = pd.to_numeric(cleaned[col], errors="coerce")

    warnings: list[str] = []

    missing_values = int(cleaned[numeric_columns].isna().sum().sum())

    if missing_values:
        warnings.append(
            f"{missing_values} missing numeric value(s) detected."
        )

    duplicate_periods = int(cleaned["date"].duplicated().sum())

    if duplicate_periods:
        warnings.append(
            f"{duplicate_periods} duplicate date(s) detected."
        )

    if (cleaned["revenue"] < 0).any():
        warnings.append("Negative revenue values detected.")

    if (cleaned["operating_cost"] < 0).any():
        warnings.append("Negative operating-cost values detected.")

    cleaned = cleaned.sort_values("date").reset_index(drop=True)

    if len(cleaned) < 6:
        warnings.append(
            "Fewer than 6 periods are available; forecasting may be unreliable."
        )

    inferred = pd.infer_freq(cleaned["date"])

    report = DataQualityReport(
        periods_loaded=len(cleaned),
        start_date=cleaned["date"].min().date().isoformat(),
        end_date=cleaned["date"].max().date().isoformat(),
        frequency=inferred or "irregular",
        missing_values=missing_values,
        duplicate_periods=duplicate_periods,
        warnings=warnings,
    )

    return cleaned, report
