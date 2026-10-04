from src.core.context import build_forecast_context
from src.ingestion.loader import load_business_csv
from src.ingestion.validator import validate_business_data
from src.simulation.liquidity import (
    SimulationInput,
    simulate_liquidity_from_context,
)


def _context():
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
    revenue_change=0.0,
    cost_change=0.0,
    receivable_delay_days=0,
):
    return simulate_liquidity_from_context(
        context,
        SimulationInput(
            revenue_change=revenue_change,
            cost_change=cost_change,
            receivable_delay_days=receivable_delay_days,
            horizon=3,
            simulations=5000,
            seed=42,
            cash_floor=20000.0,
        ),
    )


def test_demo_scenario_risk_ladder_is_ordered():
    context = _context()

    baseline = _run(context)

    moderate = _run(
        context,
        revenue_change=-0.002,
        cost_change=0.004,
    )

    severe = _run(
        context,
        revenue_change=-0.15,
        cost_change=0.10,
        receivable_delay_days=30,
    )

    assert (
        baseline.shortfall_probability
        < moderate.shortfall_probability
        < severe.shortfall_probability
    )


def test_moderate_downside_is_near_target_risk_level():
    context = _context()

    moderate = _run(
        context,
        revenue_change=-0.002,
        cost_change=0.004,
    )

    assert (
        0.70
        <= moderate.shortfall_probability
        <= 0.80
    )
