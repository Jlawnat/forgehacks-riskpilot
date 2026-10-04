from __future__ import annotations

from math import floor


def fractional_receivable_delay_adjustments(
    latest_receivables: float,
    delay_days: int,
    horizon: int,
    days_per_period: int = 30,
) -> tuple[float, ...]:
    """
    Convert a collection delay into incremental monthly
    cash-flow adjustments.

    The latest receivables balance is assumed to be
    collected in forecast period 1 under the baseline.

    A fractional delay is linearly split across adjacent
    forecast periods.

    Examples for a $30,000 balance:

        15 days:
            P1 -15,000
            P2 +15,000

        30 days:
            P1 -30,000
            P2 +30,000

        45 days:
            P1 -30,000
            P2 +15,000
            P3 +15,000

        60 days:
            P1 -30,000
            P3 +30,000

    Cash delayed beyond the selected forecast horizon is
    intentionally not recovered inside that horizon.
    """

    if horizon < 1:
        raise ValueError(
            "horizon must be at least 1."
        )

    if days_per_period <= 0:
        raise ValueError(
            "days_per_period must be positive."
        )

    adjustments = [
        0.0
        for _ in range(horizon)
    ]

    receivables = float(
        latest_receivables
    )

    if (
        delay_days <= 0
        or receivables <= 0.0
    ):
        return tuple(adjustments)

    delay_periods = (
        float(delay_days)
        / float(days_per_period)
    )

    lower_shift = floor(
        delay_periods
    )

    fractional_part = (
        delay_periods
        - lower_shift
    )

    # Remove the collection from its baseline position.
    adjustments[0] -= receivables

    if fractional_part == 0.0:
        recovery_index = lower_shift

        if recovery_index < horizon:
            adjustments[
                recovery_index
            ] += receivables

        return tuple(
            float(value)
            for value in adjustments
        )

    lower_weight = (
        1.0
        - fractional_part
    )

    upper_weight = (
        fractional_part
    )

    lower_index = lower_shift
    upper_index = lower_shift + 1

    if lower_index < horizon:
        adjustments[
            lower_index
        ] += (
            receivables
            * lower_weight
        )

    if upper_index < horizon:
        adjustments[
            upper_index
        ] += (
            receivables
            * upper_weight
        )

    return tuple(
        float(value)
        for value in adjustments
    )
