from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from src.core.cash_events import CashEvent
from src.core.forecast_monitoring import (
    ActualCashObservation,
    compare_forecast_to_actual,
    create_forecast_snapshot,
    roll_forward_forecast,
)
from src.core.direct_cash import (
    DirectCashForecastInput,
)


def _event(
    event_id,
    *,
    date_value="2026-10-05",
    amount=10000.0,
    direction="INFLOW",
    source_type="COMMITTED",
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


def _snapshot(
    *,
    events=(),
    opening_cash=50000.0,
):
    return create_forecast_snapshot(
        DirectCashForecastInput(
            start_date="2026-10-05",
            opening_cash=opening_cash,
            events=tuple(events),
        ),
        snapshot_id="snapshot-001",
        created_at=datetime(
            2026,
            10,
            4,
            8,
            0,
            tzinfo=timezone.utc,
        ),
        management_reserve=20000.0,
    )


def _actual(
    actual_id,
    *,
    date_value="2026-10-05",
    amount=10000.0,
    direction="INFLOW",
    forecast_event_id=None,
):
    return ActualCashObservation(
        actual_id=actual_id,
        date=date_value,
        amount=amount,
        direction=direction,
        source_reference=f"bank-{actual_id}",
        forecast_event_id=(
            forecast_event_id
        ),
    )


def _categories(result):
    return [
        item.category
        for item in result.variances
    ]


def test_exact_actual_has_no_variance():
    snapshot = _snapshot(
        events=(
            _event("invoice-001"),
        )
    )

    result = compare_forecast_to_actual(
        snapshot,
        (
            _actual(
                "actual-001",
                forecast_event_id="invoice-001",
            ),
        ),
        through_date=date(2026, 10, 11),
    )

    assert result.variances == ()
    assert result.actual_inflows == 10000.0
    assert result.actual_net_cash == 10000.0


def test_unlinked_actual_is_new_event():
    result = compare_forecast_to_actual(
        _snapshot(),
        (
            _actual(
                "actual-001",
                amount=5000.0,
            ),
        ),
        through_date=date(2026, 10, 11),
    )

    assert _categories(result) == [
        "NEW_EVENT"
    ]


def test_missing_forecast_cash_is_classified():
    result = compare_forecast_to_actual(
        _snapshot(
            events=(
                _event("invoice-001"),
            )
        ),
        (),
        through_date=date(2026, 10, 11),
    )

    assert _categories(result) == [
        "MISSING_EVENT"
    ]


def test_committed_amount_difference_is_amount_variance():
    result = compare_forecast_to_actual(
        _snapshot(
            events=(
                _event(
                    "invoice-001",
                    amount=10000.0,
                ),
            )
        ),
        (
            _actual(
                "actual-001",
                amount=8000.0,
                forecast_event_id="invoice-001",
            ),
        ),
        through_date=date(2026, 10, 11),
    )

    assert _categories(result) == [
        "AMOUNT"
    ]


def test_modelled_amount_difference_is_model_error():
    result = compare_forecast_to_actual(
        _snapshot(
            events=(
                _event(
                    "model-001",
                    amount=10000.0,
                    source_type="MODELLED",
                ),
            )
        ),
        (
            _actual(
                "actual-001",
                amount=8000.0,
                forecast_event_id="model-001",
            ),
        ),
        through_date=date(2026, 10, 11),
    )

    assert _categories(result) == [
        "MODEL_ERROR"
    ]


def test_timing_difference_stays_timing():
    result = compare_forecast_to_actual(
        _snapshot(
            events=(
                _event(
                    "invoice-001",
                    date_value="2026-10-05",
                ),
            )
        ),
        (
            _actual(
                "actual-001",
                date_value="2026-10-07",
                forecast_event_id="invoice-001",
            ),
        ),
        through_date=date(2026, 10, 11),
    )

    assert _categories(result) == [
        "TIMING"
    ]


def test_partial_actuals_are_aggregated():
    result = compare_forecast_to_actual(
        _snapshot(
            events=(
                _event(
                    "invoice-001",
                    amount=10000.0,
                ),
            )
        ),
        (
            _actual(
                "actual-001",
                amount=4000.0,
                forecast_event_id="invoice-001",
            ),
            _actual(
                "actual-002",
                amount=6000.0,
                forecast_event_id="invoice-001",
            ),
        ),
        through_date=date(2026, 10, 11),
    )

    assert result.variances == ()


def test_direction_mismatch_is_rejected():
    with pytest.raises(
        ValueError,
        match="direction",
    ):
        compare_forecast_to_actual(
            _snapshot(
                events=(
                    _event("invoice-001"),
                )
            ),
            (
                _actual(
                    "actual-001",
                    direction="OUTFLOW",
                    forecast_event_id="invoice-001",
                ),
            ),
            through_date=date(2026, 10, 11),
        )


def test_duplicate_actual_ids_are_rejected():
    actual = _actual("actual-001")

    with pytest.raises(
        ValueError,
        match="Duplicate actual",
    ):
        compare_forecast_to_actual(
            _snapshot(),
            (
                actual,
                actual,
            ),
            through_date=date(2026, 10, 11),
        )


def test_actual_outside_monitoring_period_is_rejected():
    with pytest.raises(
        ValueError,
        match="outside",
    ):
        compare_forecast_to_actual(
            _snapshot(),
            (
                _actual(
                    "actual-001",
                    date_value="2026-10-12",
                ),
            ),
            through_date=date(2026, 10, 11),
        )


def test_roll_forward_advances_exactly_one_week():
    prior = _snapshot(
        events=(
            _event(
                "invoice-001",
                date_value="2026-10-05",
            ),
        )
    )

    result = roll_forward_forecast(
        prior,
        new_start_date=date(
            2026,
            10,
            12,
        ),
        actual_opening_cash=52000.0,
        actual_observations=(
            _actual(
                "actual-001",
                amount=12000.0,
                forecast_event_id="invoice-001",
            ),
        ),
        future_events=(
            _event(
                "invoice-002",
                date_value="2026-10-19",
                amount=5000.0,
            ),
        ),
        snapshot_id="snapshot-002",
        created_at=datetime(
            2026,
            10,
            11,
            8,
            0,
            tzinfo=timezone.utc,
        ),
    )

    assert (
        result.current_snapshot
        .forecast_input
        .start_date
        == date(2026, 10, 12)
    )

    assert (
        result.current_snapshot
        .forecast
        .opening_cash
        == 52000.0
    )

    assert (
        result.current_snapshot
        .forecast
        .closing_cash
        == 57000.0
    )

    assert (
        result.actual_comparison
        .through_date
        == date(2026, 10, 11)
    )

    assert (
        result.actual_comparison
        .variances[0]
        .category
        == "AMOUNT"
    )


def test_roll_forward_preserves_reserve_by_default():
    prior = _snapshot()

    result = roll_forward_forecast(
        prior,
        new_start_date=date(
            2026,
            10,
            12,
        ),
        actual_opening_cash=50000.0,
        actual_observations=(),
        future_events=(),
        snapshot_id="snapshot-002",
        created_at=datetime(
            2026,
            10,
            11,
            8,
            0,
            tzinfo=timezone.utc,
        ),
    )

    assert (
        result.current_snapshot
        .decision_metrics
        .management_reserve
        == 20000.0
    )


def test_roll_forward_can_update_reserve_explicitly():
    prior = _snapshot()

    result = roll_forward_forecast(
        prior,
        new_start_date=date(
            2026,
            10,
            12,
        ),
        actual_opening_cash=50000.0,
        actual_observations=(),
        future_events=(),
        snapshot_id="snapshot-002",
        created_at=datetime(
            2026,
            10,
            11,
            8,
            0,
            tzinfo=timezone.utc,
        ),
        management_reserve=25000.0,
    )

    assert (
        result.current_snapshot
        .decision_metrics
        .management_reserve
        == 25000.0
    )


def test_roll_forward_rejects_non_weekly_start():
    with pytest.raises(
        ValueError,
        match="exactly 7 days",
    ):
        roll_forward_forecast(
            _snapshot(),
            new_start_date=date(
                2026,
                10,
                13,
            ),
            actual_opening_cash=50000.0,
            actual_observations=(),
            future_events=(),
            snapshot_id="snapshot-002",
            created_at=datetime(
                2026,
                10,
                11,
                8,
                0,
                tzinfo=timezone.utc,
            ),
        )


def test_actual_amount_validation_rejects_boolean():
    with pytest.raises(ValidationError):
        _actual(
            "actual-001",
            amount=True,
        )


def test_roll_forward_result_round_trips():
    result = roll_forward_forecast(
        _snapshot(),
        new_start_date=date(
            2026,
            10,
            12,
        ),
        actual_opening_cash=50000.0,
        actual_observations=(),
        future_events=(),
        snapshot_id="snapshot-002",
        created_at=datetime(
            2026,
            10,
            11,
            8,
            0,
            tzinfo=timezone.utc,
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
