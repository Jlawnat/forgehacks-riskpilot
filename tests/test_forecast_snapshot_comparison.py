from datetime import datetime, timezone

from src.core.cash_events import CashEvent
from src.core.direct_cash import (
    DirectCashForecastInput,
)
from src.core.forecast_monitoring import (
    compare_forecast_snapshots,
    create_forecast_snapshot,
)


def _event(
    event_id,
    *,
    date_value="2026-10-12",
    amount=10000.0,
    source_type="COMMITTED",
    direction="INFLOW",
    status="ACTIVE",
    expected_cash_date=None,
    due_date=None,
):
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
        expected_cash_date=(
            expected_cash_date
        ),
    )


def _snapshot(
    snapshot_id,
    *,
    events=(),
    opening_cash=50000.0,
    reserve=20000.0,
    start_date="2026-10-05",
):
    forecast_input = DirectCashForecastInput(
        start_date=start_date,
        opening_cash=opening_cash,
        events=tuple(events),
    )

    return create_forecast_snapshot(
        forecast_input,
        snapshot_id=snapshot_id,
        created_at=datetime(
            2026,
            10,
            4,
            18,
            30,
            tzinfo=timezone.utc,
        ),
        management_reserve=reserve,
    )


def _categories(comparison):
    return [
        item.category
        for item in comparison.variances
    ]


def test_identical_snapshots_have_no_variances():
    event = _event("invoice-001")

    prior = _snapshot(
        "prior",
        events=(event,),
    )

    current = _snapshot(
        "current",
        events=(event,),
    )

    result = compare_forecast_snapshots(
        prior,
        current,
    )

    assert result.same_forecast_basis is True
    assert result.variances == ()
    assert result.closing_cash_change == 0.0


def test_new_event_is_classified():
    prior = _snapshot("prior")

    current = _snapshot(
        "current",
        events=(
            _event("invoice-001"),
        ),
    )

    result = compare_forecast_snapshots(
        prior,
        current,
    )

    assert _categories(result) == [
        "NEW_EVENT"
    ]


def test_missing_event_is_classified():
    prior = _snapshot(
        "prior",
        events=(
            _event("invoice-001"),
        ),
    )

    current = _snapshot("current")

    result = compare_forecast_snapshots(
        prior,
        current,
    )

    assert _categories(result) == [
        "MISSING_EVENT"
    ]


def test_timing_change_is_not_called_amount_change():
    prior = _snapshot(
        "prior",
        events=(
            _event(
                "invoice-001",
                expected_cash_date="2026-10-12",
            ),
        ),
    )

    current = _snapshot(
        "current",
        events=(
            _event(
                "invoice-001",
                expected_cash_date="2026-10-19",
            ),
        ),
    )

    result = compare_forecast_snapshots(
        prior,
        current,
    )

    assert _categories(result) == [
        "TIMING"
    ]


def test_amount_change_is_classified():
    prior = _snapshot(
        "prior",
        events=(
            _event(
                "invoice-001",
                amount=10000.0,
            ),
        ),
    )

    current = _snapshot(
        "current",
        events=(
            _event(
                "invoice-001",
                amount=12000.0,
            ),
        ),
    )

    result = compare_forecast_snapshots(
        prior,
        current,
    )

    assert _categories(result) == [
        "AMOUNT"
    ]


def test_amount_and_timing_can_both_change():
    prior = _snapshot(
        "prior",
        events=(
            _event(
                "invoice-001",
                amount=10000.0,
                expected_cash_date="2026-10-12",
            ),
        ),
    )

    current = _snapshot(
        "current",
        events=(
            _event(
                "invoice-001",
                amount=12000.0,
                expected_cash_date="2026-10-19",
            ),
        ),
    )

    result = compare_forecast_snapshots(
        prior,
        current,
    )

    assert _categories(result) == [
        "TIMING",
        "AMOUNT",
    ]


def test_management_assumption_change_is_distinct():
    prior = _snapshot(
        "prior",
        events=(
            _event(
                "management-001",
                amount=10000.0,
                source_type=(
                    "MANAGEMENT_ASSUMPTION"
                ),
            ),
        ),
    )

    current = _snapshot(
        "current",
        events=(
            _event(
                "management-001",
                amount=15000.0,
                source_type=(
                    "MANAGEMENT_ASSUMPTION"
                ),
            ),
        ),
    )

    result = compare_forecast_snapshots(
        prior,
        current,
    )

    assert _categories(result) == [
        "ASSUMPTION_CHANGE"
    ]


def test_modelled_revision_is_not_called_model_error():
    prior = _snapshot(
        "prior",
        events=(
            _event(
                "model-001",
                amount=10000.0,
                source_type="MODELLED",
            ),
        ),
    )

    current = _snapshot(
        "current",
        events=(
            _event(
                "model-001",
                amount=12000.0,
                source_type="MODELLED",
            ),
        ),
    )

    result = compare_forecast_snapshots(
        prior,
        current,
    )

    assert _categories(result) == [
        "AMOUNT"
    ]

    assert all(
        item.category != "MODEL_ERROR"
        for item in result.variances
    )


def test_cancelled_future_event_becomes_missing():
    prior = _snapshot(
        "prior",
        events=(
            _event(
                "invoice-001",
                status="ACTIVE",
            ),
        ),
    )

    current = _snapshot(
        "current",
        events=(
            _event(
                "invoice-001",
                status="CANCELLED",
            ),
        ),
    )

    result = compare_forecast_snapshots(
        prior,
        current,
    )

    assert _categories(result) == [
        "MISSING_EVENT"
    ]


def test_reactivated_event_becomes_new():
    prior = _snapshot(
        "prior",
        events=(
            _event(
                "invoice-001",
                status="CANCELLED",
            ),
        ),
    )

    current = _snapshot(
        "current",
        events=(
            _event(
                "invoice-001",
                status="ACTIVE",
            ),
        ),
    )

    result = compare_forecast_snapshots(
        prior,
        current,
    )

    assert _categories(result) == [
        "NEW_EVENT"
    ]


def test_source_type_change_is_basis_change():
    prior = _snapshot(
        "prior",
        events=(
            _event(
                "cash-001",
                source_type="MODELLED",
            ),
        ),
    )

    current = _snapshot(
        "current",
        events=(
            _event(
                "cash-001",
                source_type="COMMITTED",
            ),
        ),
    )

    result = compare_forecast_snapshots(
        prior,
        current,
    )

    assert _categories(result) == [
        "ASSUMPTION_CHANGE"
    ]


def test_reserve_change_is_reported_separately():
    prior = _snapshot(
        "prior",
        reserve=10000.0,
    )

    current = _snapshot(
        "current",
        reserve=20000.0,
    )

    result = compare_forecast_snapshots(
        prior,
        current,
    )

    assert (
        result.management_reserve_changed
        is True
    )

    assert result.variances == ()


def test_headline_cash_changes_are_reported():
    prior = _snapshot(
        "prior",
        opening_cash=50000.0,
    )

    current = _snapshot(
        "current",
        opening_cash=55000.0,
    )

    result = compare_forecast_snapshots(
        prior,
        current,
    )

    assert result.opening_cash_change == 5000.0
    assert result.closing_cash_change == 5000.0
    assert result.minimum_cash_change == 5000.0


def test_variance_order_is_deterministic():
    prior = _snapshot(
        "prior",
        events=(
            _event(
                "b-event",
                amount=10000.0,
            ),
            _event(
                "a-event",
                amount=10000.0,
            ),
        ),
    )

    current = _snapshot(
        "current",
        events=(
            _event(
                "b-event",
                amount=12000.0,
            ),
            _event(
                "a-event",
                expected_cash_date="2026-10-19",
            ),
        ),
    )

    result = compare_forecast_snapshots(
        prior,
        current,
    )

    assert [
        item.event_id
        for item in result.variances
    ] == [
        "a-event",
        "b-event",
    ]


def test_comparison_round_trips():
    prior = _snapshot("prior")
    current = _snapshot("current")

    result = compare_forecast_snapshots(
        prior,
        current,
    )

    payload = result.model_dump(
        mode="json"
    )

    restored = (
        type(result)
        .model_validate(payload)
    )

    assert restored == result
