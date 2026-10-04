import pytest

from src.core.cash_events import CashEvent
from src.core.direct_cash import (
    CashCoverageAllocation,
    DirectCashForecastInput,
)
from src.core.weekly_simulation import (
    WeeklySimulationConfig,
    simulate_weekly_liquidity,
)
from src.core.weekly_uncertainty import (
    CommittedTimingUncertainty,
    ModelledCashErrorSample,
    WeeklyUncertaintyProfile,
)


def _event(
    event_id,
    *,
    date_value="2026-10-05",
    amount=10000.0,
    direction="INFLOW",
    source_type="MODELLED",
):
    return CashEvent(
        event_id=event_id,
        date=date_value,
        amount=amount,
        direction=direction,
        category="cash",
        source_type=source_type,
        status="ACTIVE",
        source_reference=f"source-{event_id}",
    )


def _input(
    *,
    opening_cash=50000.0,
    events=(),
    allocations=(),
):
    return DirectCashForecastInput(
        start_date="2026-10-05",
        opening_cash=opening_cash,
        events=tuple(events),
        coverage_allocations=tuple(
            allocations
        ),
    )


def _errors(
    *pairs,
):
    return tuple(
        ModelledCashErrorSample(
            inflow_error_pct=inflow,
            outflow_error_pct=outflow,
        )
        for inflow, outflow in pairs
    )


def test_simulation_is_reproducible():
    forecast_input = _input(
        events=(
            _event(
                "model-001",
                amount=10000.0,
            ),
        )
    )

    profile = WeeklyUncertaintyProfile(
        modelled_flow_error_samples=_errors(
            (-0.20, 0.10),
            (0.00, 0.00),
            (0.20, -0.10),
        )
    )

    config = WeeklySimulationConfig(
        simulations=1000,
        seed=42,
    )

    first = simulate_weekly_liquidity(
        forecast_input,
        profile,
        config,
    )

    second = simulate_weekly_liquidity(
        forecast_input,
        profile,
        config,
    )

    assert first == second


def test_modelled_relative_errors_are_applied():
    forecast_input = _input(
        events=(
            _event(
                "model-001",
                amount=10000.0,
            ),
        )
    )

    profile = WeeklyUncertaintyProfile(
        modelled_flow_error_samples=_errors(
            (-0.50, 0.0),
            (-0.50, 0.0),
            (-0.50, 0.0),
        )
    )

    result = simulate_weekly_liquidity(
        forecast_input,
        profile,
        WeeklySimulationConfig(
            simulations=100,
        ),
    )

    assert result.median_end_cash == 55000.0


def test_modelled_coverage_is_respected():
    committed = _event(
        "invoice-001",
        amount=6000.0,
        source_type="COMMITTED",
    )

    modelled = _event(
        "model-001",
        amount=10000.0,
    )

    allocation = CashCoverageAllocation(
        coverage_id="coverage-001",
        committed_event_id="invoice-001",
        modelled_event_id="model-001",
        amount=6000.0,
        source_reference="manual-match",
    )

    profile = WeeklyUncertaintyProfile(
        modelled_flow_error_samples=_errors(
            (0.0, 0.0),
            (0.0, 0.0),
            (0.0, 0.0),
        )
    )

    result = simulate_weekly_liquidity(
        _input(
            events=(
                committed,
                modelled,
            ),
            allocations=(
                allocation,
            ),
        ),
        profile,
        WeeklySimulationConfig(
            simulations=100,
        ),
    )

    assert result.median_end_cash == 60000.0


def test_committed_timing_delay_moves_cash_between_weeks():
    committed = _event(
        "invoice-001",
        amount=10000.0,
        source_type="COMMITTED",
    )

    profile = WeeklyUncertaintyProfile(
        committed_timing_uncertainty=(
            CommittedTimingUncertainty(
                event_id="invoice-001",
                timing_shift_days_samples=(
                    7,
                    7,
                    7,
                ),
                source_reference="timing-history",
            ),
        )
    )

    result = simulate_weekly_liquidity(
        _input(
            events=(committed,)
        ),
        profile,
        WeeklySimulationConfig(
            simulations=100,
        ),
    )

    assert (
        result.cash_path_quantiles[0]
        .p50_cash
        == 50000.0
    )

    assert (
        result.cash_path_quantiles[1]
        .p50_cash
        == 60000.0
    )


def test_early_timing_draw_is_clamped_to_forecast_start():
    committed = _event(
        "invoice-001",
        date_value="2026-10-07",
        amount=10000.0,
        source_type="COMMITTED",
    )

    profile = WeeklyUncertaintyProfile(
        committed_timing_uncertainty=(
            CommittedTimingUncertainty(
                event_id="invoice-001",
                timing_shift_days_samples=(
                    -10,
                    -10,
                    -10,
                ),
                source_reference="timing-history",
            ),
        )
    )

    result = simulate_weekly_liquidity(
        _input(
            events=(committed,)
        ),
        profile,
        WeeklySimulationConfig(
            simulations=100,
        ),
    )

    assert (
        result.cash_path_quantiles[0]
        .p50_cash
        == 60000.0
    )


def test_outside_horizon_commitment_can_shift_into_horizon():
    committed = _event(
        "invoice-001",
        date_value="2027-01-05",
        amount=10000.0,
        source_type="COMMITTED",
    )

    profile = WeeklyUncertaintyProfile(
        committed_timing_uncertainty=(
            CommittedTimingUncertainty(
                event_id="invoice-001",
                timing_shift_days_samples=(
                    -7,
                    -7,
                    -7,
                ),
                source_reference="timing-history",
            ),
        )
    )

    result = simulate_weekly_liquidity(
        _input(
            events=(committed,)
        ),
        profile,
        WeeklySimulationConfig(
            simulations=100,
        ),
    )

    assert result.median_end_cash == 60000.0


def test_management_assumption_remains_deterministic():
    management = _event(
        "management-001",
        amount=7000.0,
        source_type="MANAGEMENT_ASSUMPTION",
    )

    result = simulate_weekly_liquidity(
        _input(
            events=(management,)
        ),
        WeeklyUncertaintyProfile(),
        WeeklySimulationConfig(
            simulations=100,
        ),
    )

    assert result.p10_end_cash == 57000.0
    assert result.median_end_cash == 57000.0
    assert result.p90_end_cash == 57000.0


def test_shortfall_probability_is_valid():
    modelled = _event(
        "cost-001",
        amount=10000.0,
        direction="OUTFLOW",
    )

    profile = WeeklyUncertaintyProfile(
        modelled_flow_error_samples=_errors(
            (0.0, 0.0),
            (0.0, 0.5),
            (0.0, 1.0),
        )
    )

    result = simulate_weekly_liquidity(
        _input(
            opening_cash=12000.0,
            events=(modelled,),
        ),
        profile,
        WeeklySimulationConfig(
            simulations=1000,
            seed=7,
            cash_floor=0.0,
        ),
    )

    assert 0.0 <= result.shortfall_probability <= 1.0
    assert result.shortfall_probability > 0.0


def test_cash_quantiles_are_ordered():
    modelled = _event(
        "model-001",
        amount=10000.0,
    )

    profile = WeeklyUncertaintyProfile(
        modelled_flow_error_samples=_errors(
            (-0.5, 0.0),
            (0.0, 0.0),
            (0.5, 0.0),
        )
    )

    result = simulate_weekly_liquidity(
        _input(
            events=(modelled,)
        ),
        profile,
        WeeklySimulationConfig(
            simulations=1000,
        ),
    )

    for point in result.cash_path_quantiles:
        assert (
            point.p10_cash
            <= point.p50_cash
            <= point.p90_cash
        )


def test_liquidity_buffer_is_nonnegative():
    result = simulate_weekly_liquidity(
        _input(
            opening_cash=5000.0,
        ),
        WeeklyUncertaintyProfile(),
        WeeklySimulationConfig(
            simulations=100,
            cash_floor=10000.0,
        ),
    )

    assert (
        result.liquidity_buffer_at_confidence
        == 5000.0
    )

    assert result.expected_tail_buffer >= 0.0


def test_requested_simulation_count_is_returned():
    result = simulate_weekly_liquidity(
        _input(),
        WeeklyUncertaintyProfile(),
        WeeklySimulationConfig(
            simulations=321,
        ),
    )

    assert result.simulations == 321


def test_small_sample_limitations_are_explicit():
    modelled = _event(
        "model-001",
    )

    committed = _event(
        "invoice-001",
        source_type="COMMITTED",
    )

    profile = WeeklyUncertaintyProfile(
        modelled_flow_error_samples=_errors(
            (-0.1, 0.1),
            (0.0, 0.0),
            (0.1, -0.1),
        ),
        committed_timing_uncertainty=(
            CommittedTimingUncertainty(
                event_id="invoice-001",
                timing_shift_days_samples=(
                    0,
                    2,
                    7,
                ),
                source_reference="timing-history",
            ),
        ),
    )

    result = simulate_weekly_liquidity(
        _input(
            events=(
                modelled,
                committed,
            )
        ),
        profile,
        WeeklySimulationConfig(
            simulations=100,
        ),
    )

    assert len(result.limitations) == 2
    assert "small-sample" in result.limitations[0]
    assert "small-sample" in result.limitations[1]


def test_result_has_13_week_quantiles():
    result = simulate_weekly_liquidity(
        _input(),
        WeeklyUncertaintyProfile(),
        WeeklySimulationConfig(
            simulations=100,
        ),
    )

    assert len(result.cash_path_quantiles) == 13

    assert [
        point.week_number
        for point in result.cash_path_quantiles
    ] == list(range(1, 14))


def test_result_round_trips_deterministically():
    result = simulate_weekly_liquidity(
        _input(),
        WeeklyUncertaintyProfile(),
        WeeklySimulationConfig(
            simulations=100,
        ),
    )

    payload = result.model_dump(
        mode="json"
    )

    restored = (
        type(result)
        .model_validate(payload)
    )

    assert restored == result


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        float("nan"),
        float("inf"),
    ],
)
def test_invalid_cash_floor_is_rejected(
    value,
):
    with pytest.raises(Exception):
        WeeklySimulationConfig(
            cash_floor=value
        )
