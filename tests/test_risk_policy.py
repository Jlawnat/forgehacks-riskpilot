from src.core.risk_policy import (
    RiskPolicy,
    first_cash_breach,
    probability_within_appetite,
    reserve_headroom,
)


def test_first_cash_breach_detected():
    result = first_cash_breach(
        [50000, 32000, 18000, 10000],
        minimum_cash_reserve=20000,
    )

    assert result == 3


def test_no_cash_breach_returns_none():
    result = first_cash_breach(
        [50000, 42000, 35000],
        minimum_cash_reserve=20000,
    )

    assert result is None


def test_reserve_headroom():
    assert (
        reserve_headroom(
            49000,
            20000,
        )
        == 29000
    )


def test_probability_appetite():
    policy = RiskPolicy(
        minimum_cash_reserve=20000,
        max_shortfall_probability=0.05,
    )

    assert probability_within_appetite(
        0.04,
        policy.max_shortfall_probability,
    )

    assert not probability_within_appetite(
        0.08,
        policy.max_shortfall_probability,
    )
