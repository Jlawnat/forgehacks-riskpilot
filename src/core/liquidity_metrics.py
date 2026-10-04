from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from src.core.direct_cash import (
    DirectCashForecastResult,
)
from src.core.risk_policy import (
    first_cash_breach,
)


class LiquidityDecisionMetrics(BaseModel):
    """
    Decision metrics derived from a deterministic
    13-week direct cash forecast.

    Evidence coverage is an evidence-quality metric,
    not a probability or confidence score.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    management_reserve: float = Field(
        ge=0.0,
        allow_inf_nan=False,
    )

    current_cash: float = Field(
        allow_inf_nan=False,
    )

    minimum_closing_cash: float = Field(
        allow_inf_nan=False,
    )

    minimum_closing_cash_week: int = Field(
        ge=1,
        le=13,
    )

    minimum_headroom: float = Field(
        allow_inf_nan=False,
    )

    minimum_headroom_week: int = Field(
        ge=1,
        le=13,
    )

    first_reserve_breach_week: int | None = Field(
        default=None,
        ge=1,
        le=13,
    )

    closing_cash_13_week: float = Field(
        allow_inf_nan=False,
    )

    committed_evidence_amount: float = Field(
        ge=0.0,
        allow_inf_nan=False,
    )

    modelled_residual_amount: float = Field(
        ge=0.0,
        allow_inf_nan=False,
    )

    management_assumption_amount: float = Field(
        ge=0.0,
        allow_inf_nan=False,
    )

    evidence_coverage_ratio: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )


def build_liquidity_decision_metrics(
    forecast: DirectCashForecastResult,
    *,
    management_reserve: float,
) -> LiquidityDecisionMetrics:
    """
    Convert the 13-week direct cash forecast into
    management-facing liquidity decision metrics.

    Evidence coverage is:

        committed evidence
        -----------------------------------------
        committed evidence + modelled residual

    using absolute included cash amounts so inflows and
    outflows cannot cancel each other.

    Management assumptions are reported separately and
    excluded from the coverage ratio.
    """
    if isinstance(
        management_reserve,
        bool,
    ):
        raise ValueError(
            "management_reserve must be numeric, "
            "not boolean."
        )

    reserve = float(
        management_reserve
    )

    if reserve < 0.0:
        raise ValueError(
            "management_reserve must be nonnegative."
        )

    if reserve != reserve or reserve in (
        float("inf"),
        float("-inf"),
    ):
        raise ValueError(
            "management_reserve must be finite."
        )

    closing_cash_values = [
        float(week.closing_cash)
        for week in forecast.weeks
    ]

    headrooms = [
        cash - reserve
        for cash in closing_cash_values
    ]

    minimum_headroom = min(
        headrooms
    )

    minimum_headroom_week = (
        headrooms.index(
            minimum_headroom
        )
        + 1
    )

    first_breach = first_cash_breach(
        closing_cash_values,
        reserve,
    )

    committed_amount = sum(
        contribution.included_amount
        for week in forecast.weeks
        for contribution in week.contributions
        if (
            contribution.source_type
            == "COMMITTED"
        )
    )

    modelled_amount = sum(
        contribution.included_amount
        for week in forecast.weeks
        for contribution in week.contributions
        if (
            contribution.source_type
            == "MODELLED"
        )
    )

    management_amount = sum(
        contribution.included_amount
        for week in forecast.weeks
        for contribution in week.contributions
        if (
            contribution.source_type
            == "MANAGEMENT_ASSUMPTION"
        )
    )

    evidence_denominator = (
        committed_amount
        + modelled_amount
    )

    evidence_coverage_ratio = (
        committed_amount
        / evidence_denominator
        if evidence_denominator > 0.0
        else None
    )

    return LiquidityDecisionMetrics(
        management_reserve=reserve,
        current_cash=float(
            forecast.opening_cash
        ),
        minimum_closing_cash=float(
            forecast.minimum_closing_cash
        ),
        minimum_closing_cash_week=(
            forecast.minimum_closing_cash_week
        ),
        minimum_headroom=float(
            minimum_headroom
        ),
        minimum_headroom_week=(
            minimum_headroom_week
        ),
        first_reserve_breach_week=(
            first_breach
        ),
        closing_cash_13_week=float(
            forecast.closing_cash
        ),
        committed_evidence_amount=float(
            committed_amount
        ),
        modelled_residual_amount=float(
            modelled_amount
        ),
        management_assumption_amount=float(
            management_amount
        ),
        evidence_coverage_ratio=(
            float(evidence_coverage_ratio)
            if evidence_coverage_ratio
            is not None
            else None
        ),
    )
