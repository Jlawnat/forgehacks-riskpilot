from datetime import date

import pytest

from src.core.cash_events import CashEvent
from src.core.direct_cash import (
    CashCoverageAllocation,
    DirectCashForecastInput,
    build_direct_cash_forecast,
)


def _event(
    event_id: str,
    *,
    date_value: str = "2026-10-05",
    amount: float = 10000.0,
    direction: str = "INFLOW",
    source_type: str = "COMMITTED",
    status: str = "ACTIVE",
    due_date: str | None = None,
    expected_cash_date: str | None = None,
) -> CashEvent:
    return CashEvent(
        event_id=event_id,
        date=date_value,
        amount=amount,
        direction=direction,
        category="cash",
        source_type=source_type,
        status=status,
        source_reference=f"source-{event_id}",
        due_date=due_date,
        expected_cash_date=expected_cash_date,
    )


def _input(
    *,
    opening_cash: float = 50000.0,
    events=(),
    allocations=(),
) -> DirectCashForecastInput:
    return DirectCashForecastInput(
        start_date="2026-10-05",
        opening_cash=opening_cash,
        events=tuple(events),
        coverage_allocations=tuple(
            allocations
        ),
    )


def test_forecast_contains_exactly_13_weeks():
    result = build_direct_cash_forecast(
        _input()
    )

    assert len(result.weeks) == 13

    assert (
        result.weeks[0].start_date
        == date(2026, 10, 5)
    )

    assert (
        result.weeks[0].end_date
        == date(2026, 10, 11)
    )

    assert (
        result.weeks[-1].start_date
        == date(2026, 12, 28)
    )

    assert (
        result.weeks[-1].end_date
        == date(2027, 1, 3)
    )


def test_committed_cash_is_included_at_full_amount():
    result = build_direct_cash_forecast(
        _input(
            events=(
                _event(
                    "invoice-001",
                    amount=26000.0,
                ),
            )
        )
    )

    week = result.weeks[0]

    assert week.committed_inflows == 26000.0
    assert week.total_inflows == 26000.0
    assert week.closing_cash == 76000.0


def test_explicit_coverage_reduces_only_modelled_residual():
    committed = _event(
        "invoice-001",
        amount=26000.0,
    )

    modelled = _event(
        "model-receipts-001",
        amount=40000.0,
        source_type="MODELLED",
    )

    allocation = CashCoverageAllocation(
        coverage_id="coverage-001",
        committed_event_id="invoice-001",
        modelled_event_id="model-receipts-001",
        amount=26000.0,
        source_reference="manual-match",
    )

    result = build_direct_cash_forecast(
        _input(
            events=(
                committed,
                modelled,
            ),
            allocations=(
                allocation,
            ),
        )
    )

    week = result.weeks[0]

    assert week.committed_inflows == 26000.0
    assert week.modelled_inflows == 14000.0
    assert week.total_inflows == 40000.0


def test_overcoverage_floors_modelled_residual_at_zero():
    first = _event(
        "invoice-001",
        amount=6000.0,
    )

    second = _event(
        "invoice-002",
        amount=5000.0,
    )

    modelled = _event(
        "model-receipts-001",
        amount=10000.0,
        source_type="MODELLED",
    )

    result = build_direct_cash_forecast(
        _input(
            events=(
                first,
                second,
                modelled,
            ),
            allocations=(
                CashCoverageAllocation(
                    coverage_id="coverage-001",
                    committed_event_id="invoice-001",
                    modelled_event_id="model-receipts-001",
                    amount=6000.0,
                    source_reference="match-1",
                ),
                CashCoverageAllocation(
                    coverage_id="coverage-002",
                    committed_event_id="invoice-002",
                    modelled_event_id="model-receipts-001",
                    amount=5000.0,
                    source_reference="match-2",
                ),
            ),
        )
    )

    week = result.weeks[0]

    assert week.committed_inflows == 11000.0
    assert week.modelled_inflows == 0.0
    assert week.total_inflows == 11000.0


def test_commitment_timing_can_move_without_restoring_modelled_cash():
    committed = _event(
        "invoice-001",
        amount=26000.0,
        due_date="2026-10-06",
        expected_cash_date="2026-10-13",
    )

    modelled = _event(
        "model-receipts-001",
        amount=40000.0,
        source_type="MODELLED",
        date_value="2026-10-06",
    )

    allocation = CashCoverageAllocation(
        coverage_id="coverage-001",
        committed_event_id="invoice-001",
        modelled_event_id="model-receipts-001",
        amount=26000.0,
        source_reference="manual-match",
    )

    result = build_direct_cash_forecast(
        _input(
            events=(
                committed,
                modelled,
            ),
            allocations=(
                allocation,
            ),
        )
    )

    assert (
        result.weeks[0].modelled_inflows
        == 14000.0
    )

    assert (
        result.weeks[0].committed_inflows
        == 0.0
    )

    assert (
        result.weeks[1].committed_inflows
        == 26000.0
    )


def test_expected_cash_date_controls_bucket_timing():
    event = _event(
        "invoice-001",
        due_date="2026-10-06",
        expected_cash_date="2026-10-20",
    )

    result = build_direct_cash_forecast(
        _input(events=(event,))
    )

    assert (
        result.weeks[0].committed_inflows
        == 0.0
    )

    assert (
        result.weeks[2].committed_inflows
        == 10000.0
    )


def test_outflows_reduce_cash():
    result = build_direct_cash_forecast(
        _input(
            events=(
                _event(
                    "supplier-001",
                    amount=12000.0,
                    direction="OUTFLOW",
                ),
            )
        )
    )

    week = result.weeks[0]

    assert week.committed_outflows == 12000.0
    assert week.net_cash_flow == -12000.0
    assert week.closing_cash == 38000.0


def test_management_assumptions_are_separate():
    event = _event(
        "management-001",
        amount=7000.0,
        source_type="MANAGEMENT_ASSUMPTION",
    )

    result = build_direct_cash_forecast(
        _input(events=(event,))
    )

    week = result.weeks[0]

    assert (
        week.management_assumption_inflows
        == 7000.0
    )

    assert week.committed_inflows == 0.0
    assert week.modelled_inflows == 0.0


@pytest.mark.parametrize(
    ("source_type", "status"),
    [
        ("ACTUAL", "SETTLED"),
        ("ACTUAL", "ACTIVE"),
        ("COMMITTED", "SETTLED"),
        ("COMMITTED", "CANCELLED"),
        ("MODELLED", "SETTLED"),
        ("MANAGEMENT_ASSUMPTION", "CANCELLED"),
    ],
)
def test_non_future_cash_is_excluded(
    source_type,
    status,
):
    event = _event(
        "ignored-001",
        source_type=source_type,
        status=status,
    )

    result = build_direct_cash_forecast(
        _input(events=(event,))
    )

    assert result.closing_cash == 50000.0

    assert all(
        not week.contributions
        for week in result.weeks
    )


def test_last_day_of_horizon_is_included():
    event = _event(
        "last-day",
        date_value="2027-01-03",
        amount=1000.0,
    )

    result = build_direct_cash_forecast(
        _input(events=(event,))
    )

    assert (
        result.weeks[-1].committed_inflows
        == 1000.0
    )


def test_first_day_after_horizon_is_excluded():
    event = _event(
        "outside",
        date_value="2027-01-04",
        amount=1000.0,
    )

    result = build_direct_cash_forecast(
        _input(events=(event,))
    )

    assert result.closing_cash == 50000.0


def test_active_past_dated_forecast_event_is_rejected():
    event = _event(
        "overdue-001",
        date_value="2026-10-04",
    )

    with pytest.raises(
        ValueError,
        match="before forecast start_date",
    ):
        build_direct_cash_forecast(
            _input(events=(event,))
        )


def test_past_actual_event_does_not_block_forecast():
    event = _event(
        "actual-001",
        date_value="2026-09-01",
        source_type="ACTUAL",
        status="SETTLED",
    )

    result = build_direct_cash_forecast(
        _input(events=(event,))
    )

    assert result.closing_cash == 50000.0


def test_weekly_cash_rolls_forward():
    events = (
        _event(
            "receipt-001",
            date_value="2026-10-05",
            amount=10000.0,
        ),
        _event(
            "payment-001",
            date_value="2026-10-12",
            amount=7000.0,
            direction="OUTFLOW",
        ),
    )

    result = build_direct_cash_forecast(
        _input(events=events)
    )

    assert result.weeks[0].opening_cash == 50000.0
    assert result.weeks[0].closing_cash == 60000.0

    assert result.weeks[1].opening_cash == 60000.0
    assert result.weeks[1].closing_cash == 53000.0


def test_minimum_closing_cash_and_week_are_reported():
    events = (
        _event(
            "payment-001",
            date_value="2026-10-05",
            amount=10000.0,
            direction="OUTFLOW",
        ),
        _event(
            "receipt-001",
            date_value="2026-10-12",
            amount=5000.0,
        ),
    )

    result = build_direct_cash_forecast(
        _input(events=events)
    )

    assert result.minimum_closing_cash == 40000.0
    assert result.minimum_closing_cash_week == 1
    assert result.closing_cash == 45000.0


def test_contributions_preserve_event_date_and_reconciliation():
    committed = _event(
        "invoice-001",
        amount=6000.0,
    )

    modelled = _event(
        "model-001",
        amount=10000.0,
        source_type="MODELLED",
    )

    allocation = CashCoverageAllocation(
        coverage_id="coverage-001",
        committed_event_id="invoice-001",
        modelled_event_id="model-001",
        amount=6000.0,
        source_reference="manual-match",
    )

    result = build_direct_cash_forecast(
        _input(
            events=(
                committed,
                modelled,
            ),
            allocations=(
                allocation,
            ),
        )
    )

    by_id = {
        contribution.event_id: contribution
        for contribution
        in result.weeks[0].contributions
    }

    assert (
        by_id["model-001"]
        .effective_cash_date
        == date(2026, 10, 5)
    )

    assert (
        by_id["model-001"]
        .gross_amount
        == 10000.0
    )

    assert (
        by_id["model-001"]
        .included_amount
        == 4000.0
    )

    assert (
        by_id["model-001"]
        .reconciled_coverage_amount
        == 6000.0
    )


def test_result_serialization_is_deterministic():
    result = build_direct_cash_forecast(
        _input(
            events=(
                _event(
                    "invoice-001",
                    amount=1000.0,
                ),
            )
        )
    )

    first = result.model_dump(
        mode="json"
    )

    second = result.model_dump(
        mode="json"
    )

    assert first == second
