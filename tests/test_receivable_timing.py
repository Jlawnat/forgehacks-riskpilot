import pytest

from src.core.receivables import (
    fractional_receivable_delay_adjustments,
)


@pytest.mark.parametrize(
    (
        "delay_days",
        "expected",
    ),
    [
        (
            0,
            (
                0.0,
                0.0,
                0.0,
                0.0,
            ),
        ),
        (
            15,
            (
                -15000.0,
                15000.0,
                0.0,
                0.0,
            ),
        ),
        (
            30,
            (
                -30000.0,
                30000.0,
                0.0,
                0.0,
            ),
        ),
        (
            45,
            (
                -30000.0,
                15000.0,
                15000.0,
                0.0,
            ),
        ),
        (
            60,
            (
                -30000.0,
                0.0,
                30000.0,
                0.0,
            ),
        ),
    ],
)
def test_fractional_receivable_delay(
    delay_days,
    expected,
):
    result = (
        fractional_receivable_delay_adjustments(
            latest_receivables=30000.0,
            delay_days=delay_days,
            horizon=4,
        )
    )

    assert result == pytest.approx(
        expected
    )


def test_delay_beyond_horizon_stays_uncollected():
    result = (
        fractional_receivable_delay_adjustments(
            latest_receivables=30000.0,
            delay_days=60,
            horizon=2,
        )
    )

    assert result == pytest.approx(
        (
            -30000.0,
            0.0,
        )
    )

    assert sum(result) == pytest.approx(
        -30000.0
    )
