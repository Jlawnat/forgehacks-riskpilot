from __future__ import annotations

from src.schemas.reports import (
    BusinessMetrics,
    RiskAssessment,
    RiskLevel,
)


RISK_ORDER = {
    "low": 0,
    "medium": 1,
    "high": 2,
}


def _max_risk(*levels: RiskLevel) -> RiskLevel:
    return max(levels, key=lambda level: RISK_ORDER[level])


def assess_business_risk(
    metrics: BusinessMetrics,
) -> RiskAssessment:
    # Liquidity
    runway = metrics.cash_runway_months

    if runway is None:
        liquidity_risk: RiskLevel = "low"
    elif runway < 3:
        liquidity_risk = "high"
    elif runway < 6:
        liquidity_risk = "medium"
    else:
        liquidity_risk = "low"

    # Revenue trend
    growth = metrics.revenue_growth

    if growth is None:
        revenue_risk: RiskLevel = "medium"
    elif growth <= -0.10:
        revenue_risk = "high"
    elif growth < 0:
        revenue_risk = "medium"
    else:
        revenue_risk = "low"

    # Cost pressure
    ratio = metrics.cost_to_revenue_ratio

    if ratio is None:
        cost_pressure_risk: RiskLevel = "medium"
    elif ratio >= 1.0:
        cost_pressure_risk = "high"
    elif ratio >= 0.85:
        cost_pressure_risk = "medium"
    else:
        cost_pressure_risk = "low"

    # Receivables exposure
    if metrics.latest_revenue <= 0:
        receivables_risk: RiskLevel = "high"
    else:
        receivable_ratio = (
            metrics.latest_receivables /
            metrics.latest_revenue
        )

        if receivable_ratio >= 0.60:
            receivables_risk = "high"
        elif receivable_ratio >= 0.35:
            receivables_risk = "medium"
        else:
            receivables_risk = "low"

    overall_risk = _max_risk(
        liquidity_risk,
        revenue_risk,
        cost_pressure_risk,
        receivables_risk,
    )

    return RiskAssessment(
        liquidity_risk=liquidity_risk,
        revenue_risk=revenue_risk,
        cost_pressure_risk=cost_pressure_risk,
        receivables_risk=receivables_risk,
        overall_risk=overall_risk,
    )
