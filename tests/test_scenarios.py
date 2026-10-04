import pytest

from src.ingestion.loader import load_business_csv
from src.ingestion.validator import validate_business_data
from src.scenarios.decomposition import decompose_scenario
from src.scenarios.engine import ScenarioInput, run_scenario


def _load_demo():
    raw = load_business_csv(
        "data/demo/fragile_business.csv"
    )
    cleaned, _ = validate_business_data(raw)
    return cleaned


def test_zero_shock_matches_baseline():
    df = _load_demo()

    result = run_scenario(
        df,
        ScenarioInput(horizon=3),
    )

    assert result.stressed_end_cash == pytest.approx(
        result.baseline_end_cash
    )

    assert result.peak_liquidity_gap == pytest.approx(0)


def test_revenue_drop_cannot_improve_cash():
    df = _load_demo()

    result = run_scenario(
        df,
        ScenarioInput(
            revenue_change=-0.15,
            horizon=3,
        ),
    )

    assert result.end_cash_impact < 0
    assert result.peak_liquidity_gap > 0


def test_cost_increase_cannot_improve_cash():
    df = _load_demo()

    result = run_scenario(
        df,
        ScenarioInput(
            cost_change=0.10,
            horizon=3,
        ),
    )

    assert result.end_cash_impact < 0


def test_receivable_delay_creates_liquidity_gap():
    df = _load_demo()

    result = run_scenario(
        df,
        ScenarioInput(
            receivable_delay_days=30,
            horizon=3,
        ),
    )

    assert result.peak_liquidity_gap == pytest.approx(
        32800.0
    )


def test_receivable_delay_is_not_permanent_loss():
    df = _load_demo()

    result = run_scenario(
        df,
        ScenarioInput(
            receivable_delay_days=30,
            horizon=3,
        ),
    )

    assert result.end_cash_impact == pytest.approx(0)


def test_combined_stress_accelerates_cash_failure():
    df = _load_demo()

    result = run_scenario(
        df,
        ScenarioInput(
            revenue_change=-0.15,
            cost_change=0.10,
            receivable_delay_days=30,
            horizon=3,
        ),
    )

    assert result.stressed_first_negative_period == 1
    assert result.baseline_first_negative_period == 2


def test_decomposition_includes_receivable_timing_risk():
    df = _load_demo()

    result = decompose_scenario(
        df,
        ScenarioInput(
            revenue_change=-0.15,
            cost_change=0.10,
            receivable_delay_days=30,
            horizon=3,
        ),
    )

    receivables = next(
        driver
        for driver in result.drivers
        if driver.driver == "receivable_delay"
    )

    assert receivables.peak_liquidity_impact > 0
    assert receivables.contribution_share > 0


def test_decomposition_shares_sum_to_one():
    df = _load_demo()

    result = decompose_scenario(
        df,
        ScenarioInput(
            revenue_change=-0.15,
            cost_change=0.10,
            receivable_delay_days=30,
            horizon=3,
        ),
    )

    assert sum(
        driver.contribution_share
        for driver in result.drivers
    ) == pytest.approx(1.0)
