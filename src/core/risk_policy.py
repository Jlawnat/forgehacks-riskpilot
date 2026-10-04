from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, Field


class RiskPolicy(BaseModel):
    """
    Management-defined liquidity risk appetite.
    """

    minimum_cash_reserve: float = Field(
        default=0.0,
        ge=0.0,
    )

    max_shortfall_probability: float = Field(
        default=0.05,
        ge=0.0,
        le=1.0,
    )


def first_cash_breach(
    cash_values: Iterable[float],
    minimum_cash_reserve: float,
) -> int | None:
    """
    Return the first 1-indexed forecast period in which
    cash drops below the selected reserve.
    """

    for period, value in enumerate(
        cash_values,
        start=1,
    ):
        if float(value) < minimum_cash_reserve:
            return period

    return None


def reserve_headroom(
    current_cash: float,
    minimum_cash_reserve: float,
) -> float:
    return float(
        current_cash
        - minimum_cash_reserve
    )


def probability_within_appetite(
    shortfall_probability: float,
    maximum_probability: float,
) -> bool:
    return (
        shortfall_probability
        <= maximum_probability
    )
