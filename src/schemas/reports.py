from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


RiskLevel = Literal["low", "medium", "high"]


class DataQualityReport(BaseModel):
    periods_loaded: int = Field(ge=0)
    start_date: str
    end_date: str
    frequency: str
    missing_values: int = Field(ge=0)
    duplicate_periods: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)


class BusinessMetrics(BaseModel):
    latest_revenue: float
    latest_operating_cost: float
    latest_cash_balance: float
    latest_receivables: float

    revenue_growth: float | None = None
    cost_to_revenue_ratio: float | None = None
    revenue_volatility: float | None = None
    cash_runway_months: float | None = None


class RiskAssessment(BaseModel):
    liquidity_risk: RiskLevel
    revenue_risk: RiskLevel
    cost_pressure_risk: RiskLevel
    receivables_risk: RiskLevel
    overall_risk: RiskLevel


class BusinessHealthReport(BaseModel):
    data_quality: DataQualityReport
    metrics: BusinessMetrics
    risks: RiskAssessment
