import pytest

from src.core.cash_events import CashEvent
from src.core.direct_cash import (
    CashCoverageAllocation,
    DirectCashForecastInput,
    build_direct_cash_forecast,
)
from src.core.liquidity_metrics import (
    build_liquidity_decision_metrics,
)


def _event(
    event_id: str,
    *,
    date_value: str = "2026-10-05",
    amount: float = 10000.0,
    direction: str = "INFLOW",
    source_type: str = "COMMITTED",
) -> CashEvent:
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


def _forecast(
    *,
    opening_cash: float = 50000.0,
    events=(),
    allocations=(),
):
    forecast_input = DirectCashForecastInput(
        start_date="2026-10-05",
        opening_cash=opening_cash,
        events=tuple(events),
        coverage_allocations=tuple(
            allocations
        ),
    )

    return build_direct_cash_forecast(
        forecast_input
    )


def test_basic_liquidity_decision_metrics():
    forecast = _forecast(
        events=(
            _event(
                "payment-001",
                amount=20000.0,
                direction="OUTFLOW",
            ),
            _event(
                "receipt-001",
                date_value="2026-10-12",
                amount=10000.0,
            ),
        )
    )

    metrics = build_liquidity_decision_metrics(
        forecast,
        management_reserve=35000.0,
    )

    assert metrics.current_cash == 50000.0
    assert metrics.minimum_closing_cash == 30000.0
    assert metrics.minimum_closing_cash_week == 1

    assert metrics.minimum_headroom == -5000.0
    assert metrics.minimum_headroom_week == 1

    assert metrics.first_reserve_breach_week == 1
    assert metrics.closing_cash_13_week == 40000.0


def test_no_reserve_breach_returns_none():
    forecast = _forecast(
        events=(
            _event(
                "receipt-001",
                amount=5000.0,
            ),
        )
    )

    metrics = build_liquidity_decision_metrics(
        forecast,
        management_reserve=40000.0,
    )

    assert (
        metrics.first_reserve_breach_week
        is None
    )

    assert metrics.minimum_headroom == 15000.0


def test_exact_reserve_is_not_a_breach():
    forecast = _forecast(
        opening_cash=50000.0,
        events=(
            _event(
                "payment-001",
                amount=10000.0,
                direction="OUTFLOW",
            ),
        ),
    )

    metrics = build_liquidity_decision_metrics(
        forecast,
        management_reserve=40000.0,
    )

    assert (
        metrics.first_reserve_breach_week
        is None
    )

    assert metrics.minimum_headroom == 0.0


def test_evidence_coverage_uses_committed_and_modelled():
    committed = _event(
        "invoice-001",
        amount=26000.0,
    )

    modelled = _event(
        "model-001",
        amount=40000.0,
        source_type="MODELLED",
    )

    allocation = CashCoverageAllocation(
        coverage_id="coverage-001",
        committed_event_id="invoice-001",
        modelled_event_id="model-001",
        amount=26000.0,
        source_reference="manual-match",
    )

    forecast = _forecast(
        events=(
            committed,
            modelled,
        ),
        allocations=(
            allocation,
        ),
    )

    metrics = build_liquidity_decision_metrics(
        forecast,
        management_reserve=0.0,
    )

    assert (
        metrics.committed_evidence_amount
        == 26000.0
    )

    assert (
        metrics.modelled_residual_amount
        == 14000.0
    )

    assert (
        metrics.evidence_coverage_ratio
        == pytest.approx(0.65)
    )


def test_management_assumptions_are_excluded_from_coverage():
    forecast = _forecast(
        events=(
            _event(
                "committed-001",
                amount=6000.0,
            ),
            _event(
                "modelled-001",
                amount=4000.0,
                source_type="MODELLED",
            ),
            _event(
                "management-001",
                amount=90000.0,
                source_type="MANAGEMENT_ASSUMPTION",
            ),
        )
    )

    metrics = build_liquidity_decision_metrics(
        forecast,
        management_reserve=0.0,
    )

    assert (
        metrics.committed_evidence_amount
        == 6000.0
    )

    assert (
        metrics.modelled_residual_amount
        == 4000.0
    )

    assert (
        metrics.management_assumption_amount
        == 90000.0
    )

    assert (
        metrics.evidence_coverage_ratio
        == pytest.approx(0.6)
    )


def test_inflows_and_outflows_do_not_cancel_in_coverage():
    forecast = _forecast(
        events=(
            _event(
                "committed-in",
                amount=10000.0,
            ),
            _event(
                "committed-out",
                amount=10000.0,
                direction="OUTFLOW",
            ),
            _event(
                "modelled-in",
                amount=20000.0,
                source_type="MODELLED",
            ),
        )
    )

    metrics = build_liquidity_decision_metrics(
        forecast,
        management_reserve=0.0,
    )

    assert (
        metrics.committed_evidence_amount
        == 20000.0
    )

    assert (
        metrics.modelled_residual_amount
        == 20000.0
    )

    assert (
        metrics.evidence_coverage_ratio
        == pytest.approx(0.5)
    )


def test_no_committed_or_modelled_cash_has_no_coverage_ratio():
    forecast = _forecast(
        events=(
            _event(
                "management-001",
                amount=5000.0,
                source_type="MANAGEMENT_ASSUMPTION",
            ),
        )
    )

    metrics = build_liquidity_decision_metrics(
        forecast,
        management_reserve=0.0,
    )

    assert (
        metrics.evidence_coverage_ratio
        is None
    )


def test_only_committed_cash_has_full_coverage():
    forecast = _forecast(
        events=(
            _event(
                "committed-001",
                amount=10000.0,
            ),
        )
    )

    metrics = build_liquidity_decision_metrics(
        forecast,
        management_reserve=0.0,
    )

    assert metrics.evidence_coverage_ratio == 1.0


def test_only_modelled_cash_has_zero_coverage():
    forecast = _forecast(
        events=(
            _event(
                "modelled-001",
                amount=10000.0,
                source_type="MODELLED",
            ),
        )
    )

    metrics = build_liquidity_decision_metrics(
        forecast,
        management_reserve=0.0,
    )

    assert metrics.evidence_coverage_ratio == 0.0


@pytest.mark.parametrize(
    "reserve",
    [
        -1.0,
        float("nan"),
        float("inf"),
        float("-inf"),
        True,
        False,
    ],
)
def test_invalid_management_reserve_is_rejected(
    reserve,
):
    forecast = _forecast()

    with pytest.raises(ValueError):
        build_liquidity_decision_metrics(
            forecast,
            management_reserve=reserve,
        )


def test_minimum_headroom_can_occur_after_minimum_cash_tie():
    forecast = _forecast(
        opening_cash=50000.0,
        events=(
            _event(
                "payment-001",
                amount=10000.0,
                direction="OUTFLOW",
            ),
        ),
    )

    metrics = build_liquidity_decision_metrics(
        forecast,
        management_reserve=20000.0,
    )

    assert metrics.minimum_headroom == 20000.0
    assert metrics.minimum_headroom_week == 1


def test_metrics_round_trip_deterministically():
    forecast = _forecast(
        events=(
            _event(
                "receipt-001",
                amount=1000.0,
            ),
        )
    )

    metrics = build_liquidity_decision_metrics(
        forecast,
        management_reserve=25000.0,
    )

    payload = metrics.model_dump(
        mode="json"
    )

    restored = (
        type(metrics)
        .model_validate(payload)
    )

    assert restored == metrics
    assert (
        restored.model_dump(mode="json")
        == payload
    )
