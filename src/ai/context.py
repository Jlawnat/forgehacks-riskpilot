from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.analytics.metrics import (
    calculate_business_metrics,
)
from src.analytics.risk import (
    assess_business_risk,
)
from src.core.context import (
    ForecastContext,
    build_forecast_context,
)
from src.core.risk_policy import RiskPolicy


@dataclass
class RiskAnalystContext:
    dataframe: pd.DataFrame
    policy: RiskPolicy
    forecast: ForecastContext
    metrics: object
    risks: object

    tool_calls: list[str] = field(
        default_factory=list
    )

    def record_tool(
        self,
        name: str,
    ) -> None:
        self.tool_calls.append(name)


def build_risk_analyst_context(
    df: pd.DataFrame,
    policy: RiskPolicy,
    horizon: int = 3,
) -> RiskAnalystContext:
    """
    Prepare all deterministic dependencies needed
    by the AI Risk Analyst.

    Forecast fitting happens once here and is reused
    by downstream tools.
    """

    metrics = calculate_business_metrics(
        df
    )

    risks = assess_business_risk(
        metrics
    )

    forecast = build_forecast_context(
        df,
        horizon=horizon,
    )

    return RiskAnalystContext(
        dataframe=df.copy(),
        policy=policy,
        forecast=forecast,
        metrics=metrics,
        risks=risks,
    )
