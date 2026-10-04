from datetime import date

import pytest
from pydantic import ValidationError

from src.core.cash_events import (
    CashEvent,
    ensure_unique_cash_event_ids,
)


def _event(**overrides):
    values = {
        "event_id": "receipt-001",
        "date": "2026-10-05",
        "amount": 12500.0,
        "direction": "INFLOW",
        "category": "customer_receipt",
        "source_type": "COMMITTED",
        "status": "ACTIVE",
        "description": "Customer invoice receipt",
        "source_reference": "invoice-001",
        "due_date": "2026-10-03",
        "expected_cash_date": "2026-10-07",
    }

    values.update(overrides)

    return CashEvent(**values)


def test_cash_event_preserves_dates_independently():
    event = _event()

    assert event.date == date(2026, 10, 5)
    assert event.due_date == date(2026, 10, 3)
    assert event.expected_cash_date == date(2026, 10, 7)


def test_expected_cash_date_has_timing_precedence():
    event = _event()

    assert (
        event.effective_cash_date
        == date(2026, 10, 7)
    )


def test_due_date_is_fallback_timing():
    event = _event(
        expected_cash_date=None,
    )

    assert (
        event.effective_cash_date
        == date(2026, 10, 3)
    )


def test_base_date_is_final_timing_fallback():
    event = _event(
        due_date=None,
        expected_cash_date=None,
    )

    assert (
        event.effective_cash_date
        == date(2026, 10, 5)
    )


def test_outflow_sign_is_derived_from_direction():
    event = _event(
        direction="OUTFLOW",
        amount=250.0,
    )

    assert event.amount == 250.0
    assert event.signed_amount == -250.0


@pytest.mark.parametrize(
    "amount",
    [
        -1.0,
        float("nan"),
        float("inf"),
        float("-inf"),
        True,
        False,
    ],
)
def test_invalid_amounts_are_rejected(amount):
    with pytest.raises(ValidationError):
        _event(amount=amount)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("event_id", ""),
        ("event_id", "   "),
        ("category", ""),
        ("category", "   "),
        ("source_reference", ""),
        ("source_reference", "   "),
    ],
)
def test_required_strings_must_be_nonblank(
    field,
    value,
):
    with pytest.raises(ValidationError):
        _event(**{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("direction", "SIDEWAYS"),
        ("source_type", "SCENARIO_ADJUSTMENT"),
        ("source_type", "UNKNOWN"),
        ("status", "UNKNOWN"),
    ],
)
def test_invalid_domain_values_are_rejected(
    field,
    value,
):
    with pytest.raises(ValidationError):
        _event(**{field: value})


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        _event(unexpected_field="value")


def test_cash_event_is_immutable():
    event = _event()

    with pytest.raises(ValidationError):
        event.amount = 1.0


def test_serialization_is_deterministic_and_round_trips():
    event = _event()

    first = event.model_dump(
        mode="json"
    )

    second = event.model_dump(
        mode="json"
    )

    assert first == second

    restored = CashEvent.model_validate(
        first
    )

    assert restored == event
    assert (
        restored.model_dump(mode="json")
        == first
    )


def test_duplicate_ids_in_one_collection_are_rejected():
    first = _event()
    duplicate = _event(
        amount=9000.0,
    )

    with pytest.raises(
        ValueError,
        match="Duplicate cash event ID",
    ):
        ensure_unique_cash_event_ids(
            [first, duplicate]
        )


def test_duplicate_ids_across_collections_are_rejected():
    first = _event()
    duplicate = _event(
        amount=9000.0,
    )

    with pytest.raises(
        ValueError,
        match="Duplicate cash event ID",
    ):
        ensure_unique_cash_event_ids(
            [first],
            [duplicate],
        )


def test_distinct_event_ids_are_accepted():
    first = _event()

    second = _event(
        event_id="payment-001",
        direction="OUTFLOW",
        amount=5000.0,
        source_reference="bill-001",
    )

    ensure_unique_cash_event_ids(
        [first],
        [second],
    )
