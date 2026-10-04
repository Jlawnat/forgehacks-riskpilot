from __future__ import annotations

import numpy as np
import pandas as pd

from src.schemas.reports import BusinessMetrics


def calculate_business_metrics(df: pd.DataFrame) -> BusinessMetrics:
    if df.empty:
        raise ValueError("Cannot calculate metrics from empty data.")

    latest = df.iloc[-1]

    # Compare recent 3 periods with the previous 3 periods where possible.
    revenue_growth = None
    if len(df) >= 6:
        recent = df["revenue"].iloc[-3:].mean()
        previous = df["revenue"].iloc[-6:-3].mean()

        if previous != 0:
            revenue_growth = float((recent - previous) / previous)

    latest_revenue = float(latest["revenue"])
    latest_operating_cost = float(latest["operating_cost"])
    latest_cash_balance = float(latest["cash_balance"])
    latest_receivables = float(latest["receivables"])

    cost_to_revenue_ratio = None
    if latest_revenue != 0:
        cost_to_revenue_ratio = float(
            latest_operating_cost / latest_revenue
        )

    # Coefficient of variation on recent revenue.
    revenue_volatility = None
    recent_revenue = df["revenue"].tail(min(6, len(df))).dropna()

    if len(recent_revenue) >= 2:
        mean_revenue = recent_revenue.mean()
        if mean_revenue != 0:
            revenue_volatility = float(
                recent_revenue.std(ddof=1) / abs(mean_revenue)
            )

    # Cash runway based on average positive operating burn
    # over the most recent 3 periods.
    recent = df.tail(min(3, len(df))).copy()
    recent["burn"] = (
        recent["operating_cost"] - recent["revenue"]
    ).clip(lower=0)

    average_burn = float(recent["burn"].mean())

    if average_burn > 0:
        cash_runway_months = max(
            0.0,
            latest_cash_balance / average_burn,
        )
    else:
        cash_runway_months = None

    return BusinessMetrics(
        latest_revenue=latest_revenue,
        latest_operating_cost=latest_operating_cost,
        latest_cash_balance=latest_cash_balance,
        latest_receivables=latest_receivables,
        revenue_growth=revenue_growth,
        cost_to_revenue_ratio=cost_to_revenue_ratio,
        revenue_volatility=revenue_volatility,
        cash_runway_months=cash_runway_months,
    )
