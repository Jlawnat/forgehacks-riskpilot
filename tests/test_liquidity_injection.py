import pytest

from src.core.context import (
    build_forecast_context,
)
from src.ingestion.loader import (
    load_business_csv,
)
from src.ingestion.validator import (
    validate_business_data,
)
from src.simulation.liquidity import (
    SimulationInput,
    simulate_liquidity_from_context,
)


@pytest.fixture(scope="module")
def context():
    raw = load_business_csv(
        "data/demo/borderline_business.csv"
    )

    df, _ = validate_business_data(raw)

    return build_forecast_context(
        df,
        horizon=3,
    )


def _run(
    context,
    injection,
):
    return simulate_liquidity_from_context(
        context,
        SimulationInput(
            horizon=3,
            simulations=5000,
            seed=42,
            cash_floor=20000.0,
            initial_liquidity_injection=injection,
        ),
    )


def test_liquidity_injection_shifts_cash_distribution(
    context,
):
    baseline = _run(
        context,
        0.0,
    )

    funded = _run(
        context,
        10000.0,
    )

    assert (
        funded.median_end_cash
        == pytest.approx(
            baseline.median_end_cash
            + 10000.0
        )
    )

    assert (
        funded.p10_end_cash
        == pytest.approx(
            baseline.p10_end_cash
            + 10000.0
        )
    )

    assert (
        funded.median_min_cash
        == pytest.approx(
            baseline.median_min_cash
            + 10000.0
        )
    )


def test_liquidity_injection_does_not_increase_risk(
    context,
):
    baseline = _run(
        context,
        0.0,
    )

    funded = _run(
        context,
        10000.0,
    )

    assert (
        funded.shortfall_probability
        <= baseline.shortfall_probability
    )
