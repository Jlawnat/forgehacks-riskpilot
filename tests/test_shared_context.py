from src.core.context import (
    build_forecast_context,
    dataframe_fingerprint,
)
from src.ingestion.loader import (
    load_business_csv,
)
from src.ingestion.validator import (
    validate_business_data,
)
from src.scenarios.engine import (
    ScenarioInput,
    run_scenario,
    run_scenario_from_context,
    scenario_context_from_forecast_context,
)


def _load_demo():
    raw = load_business_csv(
        "data/demo/borderline_business.csv"
    )

    cleaned, _ = (
        validate_business_data(raw)
    )

    return cleaned


def test_dataframe_fingerprint_is_stable():
    df = _load_demo()

    first = dataframe_fingerprint(
        df
    )

    second = dataframe_fingerprint(
        df.copy()
    )

    assert first == second


def test_forecast_context_contains_shared_outputs():
    df = _load_demo()

    context = build_forecast_context(
        df,
        horizon=3,
    )

    assert context.horizon == 3

    assert (
        context.revenue_forecast
        .selected_model
        in {"holt", "naive"}
    )

    assert (
        context.cost_forecast
        .selected_model
        in {"holt", "naive"}
    )

    assert (
        len(
            context.paired_residuals
        )
        >= 3
    )


def test_context_scenario_matches_standard_path():
    df = _load_demo()

    scenario = ScenarioInput(
        revenue_change=-0.15,
        cost_change=0.10,
        receivable_delay_days=30,
        horizon=3,
    )

    standard = run_scenario(
        df,
        scenario,
    )

    forecast_context = (
        build_forecast_context(
            df,
            horizon=3,
        )
    )

    scenario_context = (
        scenario_context_from_forecast_context(
            forecast_context
        )
    )

    shared = (
        run_scenario_from_context(
            scenario_context,
            scenario,
        )
    )

    assert (
        standard.stressed_end_cash
        == shared.stressed_end_cash
    )

    assert (
        standard.peak_liquidity_gap
        == shared.peak_liquidity_gap
    )

    assert (
        standard.stressed_first_negative_period
        == shared.stressed_first_negative_period
    )


def test_context_liquidity_matches_standard_path():
    from src.simulation.liquidity import (
        SimulationInput,
        simulate_liquidity,
        simulate_liquidity_from_context,
    )

    df = _load_demo()

    config = SimulationInput(
        revenue_change=-0.05,
        cost_change=0.02,
        receivable_delay_days=15,
        horizon=3,
        simulations=1000,
        seed=42,
    )

    standard = simulate_liquidity(
        df,
        config,
    )

    context = build_forecast_context(
        df,
        horizon=3,
    )

    shared = (
        simulate_liquidity_from_context(
            context,
            config,
        )
    )

    assert (
        standard.shortfall_probability
        == shared.shortfall_probability
    )

    assert (
        standard.median_end_cash
        == shared.median_end_cash
    )

    assert (
        standard.liquidity_buffer_at_confidence
        == shared.liquidity_buffer_at_confidence
    )


def test_multiple_simulations_share_one_context():
    from src.simulation.liquidity import (
        SimulationInput,
        simulate_liquidity_from_context,
    )

    df = _load_demo()

    context = build_forecast_context(
        df,
        horizon=3,
    )

    scenarios = [
        SimulationInput(
            horizon=3,
            simulations=500,
            seed=42,
        ),
        SimulationInput(
            revenue_change=-0.05,
            cost_change=0.02,
            horizon=3,
            simulations=500,
            seed=42,
        ),
        SimulationInput(
            revenue_change=-0.15,
            cost_change=0.10,
            receivable_delay_days=30,
            horizon=3,
            simulations=500,
            seed=42,
        ),
    ]

    results = [
        simulate_liquidity_from_context(
            context,
            scenario,
        )
        for scenario in scenarios
    ]

    assert len(results) == 3

    assert (
        results[2]
        .median_end_cash
        <
        results[0]
        .median_end_cash
    )
