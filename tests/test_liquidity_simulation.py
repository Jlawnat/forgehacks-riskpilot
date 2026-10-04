import pytest

from src.ingestion.loader import load_business_csv
from src.ingestion.validator import validate_business_data
from src.simulation.liquidity import (
    SimulationInput,
    simulate_liquidity,
)


def _load_demo():
    raw = load_business_csv(
        "data/demo/fragile_business.csv"
    )

    cleaned, _ = validate_business_data(
        raw
    )

    return cleaned


def test_simulation_is_reproducible():
    df = _load_demo()

    config = SimulationInput(
        horizon=3,
        simulations=1000,
        seed=42,
    )

    first = simulate_liquidity(
        df,
        config,
    )

    second = simulate_liquidity(
        df,
        config,
    )

    assert (
        first.shortfall_probability
        == second.shortfall_probability
    )

    assert (
        first.median_end_cash
        == pytest.approx(
            second.median_end_cash
        )
    )


def test_probabilities_are_valid():
    df = _load_demo()

    result = simulate_liquidity(
        df,
        SimulationInput(
            horizon=3,
            simulations=1000,
        ),
    )

    assert (
        0
        <= result.shortfall_probability
        <= 1
    )

    assert (
        0
        <= result.first_period_shortfall_probability
        <= 1
    )

    for point in result.cash_path_quantiles:
        assert (
            0
            <= point.shortfall_probability
            <= 1
        )


def test_cash_quantiles_are_ordered():
    df = _load_demo()

    result = simulate_liquidity(
        df,
        SimulationInput(
            horizon=3,
            simulations=1000,
        ),
    )

    assert (
        result.p10_end_cash
        <= result.median_end_cash
        <= result.p90_end_cash
    )

    for point in result.cash_path_quantiles:
        assert (
            point.p10_cash
            <= point.p50_cash
            <= point.p90_cash
        )


def test_severe_scenario_increases_shortfall_risk():
    df = _load_demo()

    baseline = simulate_liquidity(
        df,
        SimulationInput(
            horizon=3,
            simulations=2000,
            seed=42,
        ),
    )

    severe = simulate_liquidity(
        df,
        SimulationInput(
            revenue_change=-0.15,
            cost_change=0.10,
            receivable_delay_days=30,
            horizon=3,
            simulations=2000,
            seed=42,
        ),
    )

    assert (
        severe.shortfall_probability
        >= baseline.shortfall_probability
    )

    assert (
        severe.median_end_cash
        < baseline.median_end_cash
    )


def test_liquidity_buffer_is_nonnegative():
    df = _load_demo()

    result = simulate_liquidity(
        df,
        SimulationInput(
            revenue_change=-0.15,
            cost_change=0.10,
            receivable_delay_days=30,
            horizon=3,
            simulations=1000,
        ),
    )

    assert (
        result.liquidity_buffer_at_confidence
        >= 0
    )

    assert (
        result.expected_tail_buffer
        >= result.liquidity_buffer_at_confidence
    )


def test_simulation_returns_requested_path_count():
    df = _load_demo()

    result = simulate_liquidity(
        df,
        SimulationInput(
            horizon=4,
            simulations=1234,
        ),
    )

    assert result.simulations == 1234
    assert len(
        result.cash_path_quantiles
    ) == 4


def test_borderline_demo_has_non_degenerate_risk():
    raw = load_business_csv(
        "data/demo/borderline_business.csv"
    )

    df, _ = validate_business_data(raw)

    # Borderline Business is intentionally calibrated
    # around a $20k management liquidity reserve rather
    # than literal cash insolvency.
    reserve_result = simulate_liquidity(
        df,
        SimulationInput(
            horizon=3,
            simulations=5000,
            seed=42,
            cash_floor=20000.0,
        ),
    )

    insolvency_result = simulate_liquidity(
        df,
        SimulationInput(
            horizon=3,
            simulations=5000,
            seed=42,
            cash_floor=0.0,
        ),
    )

    # The demo should sit near the management-policy
    # boundary so risk is informative rather than
    # trivially 0% or 100%.
    assert (
        0.05
        < reserve_result.shortfall_probability
        < 0.95
    )

    # At the same time, the company should not already
    # be close to literal cash exhaustion.
    assert (
        insolvency_result.shortfall_probability
        < reserve_result.shortfall_probability
    )


def test_borderline_severe_scenario_materially_worsens_risk():
    raw = load_business_csv(
        "data/demo/borderline_business.csv"
    )

    df, _ = validate_business_data(raw)

    baseline = simulate_liquidity(
        df,
        SimulationInput(
            horizon=3,
            simulations=5000,
            seed=42,
        ),
    )

    severe = simulate_liquidity(
        df,
        SimulationInput(
            revenue_change=-0.15,
            cost_change=0.10,
            receivable_delay_days=30,
            horizon=3,
            simulations=5000,
            seed=42,
        ),
    )

    assert severe.shortfall_probability > baseline.shortfall_probability

    assert (
        severe.liquidity_buffer_at_confidence
        > baseline.liquidity_buffer_at_confidence
    )
