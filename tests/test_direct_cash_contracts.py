from datetime import date

import pytest
from pydantic import ValidationError

from src.core.cash_events import CashEvent
from src.core.direct_cash import (
    CashCoverageAllocation,
    DirectCashForecastInput,
)


def _event(
    event_id: str,
    *,
    amount: float = 10000.0,
    direction: str = "INFLOW",
    source_type: str = "COMMITTED",
    status: str = "ACTIVE",
) -> CashEvent:
    return CashEvent(
        event_id=event_id,
        date="2026-10-12",
        amount=amount,
        direction=direction,
        category="customer_receipt",
        source_type=source_type,
        status=status,
        source_reference=f"source-{event_id}",
    )


def _coverage(
    *,
    coverage_id: str = "coverage-001",
    committed_event_id: str = "invoice-001",
    modelled_event_id: str = "model-receipts-001",
    amount: float = 6000.0,
) -> CashCoverageAllocation:
    return CashCoverageAllocation(
        coverage_id=coverage_id,
        committed_event_id=committed_event_id,
        modelled_event_id=modelled_event_id,
        amount=amount,
        source_reference="manual-match-001",
    )


def _valid_input(
    **overrides,
) -> DirectCashForecastInput:
    committed = _event(
        "invoice-001",
        amount=6000.0,
    )

    modelled = _event(
        "model-receipts-001",
        amount=10000.0,
        source_type="MODELLED",
    )

    values = {
        "start_date": "2026-10-05",
        "opening_cash": 50000.0,
        "events": (
            committed,
            modelled,
        ),
        "coverage_allocations": (
            _coverage(),
        ),
    }

    values.update(overrides)

    return DirectCashForecastInput(
        **values
    )


def test_direct_cash_contract_is_fixed_to_13_weeks():
    contract = _valid_input()

    assert contract.horizon_weeks == 13

    with pytest.raises(ValidationError):
        _valid_input(
            horizon_weeks=12
        )


def test_opening_cash_may_be_negative():
    contract = _valid_input(
        opening_cash=-5000.0
    )

    assert contract.opening_cash == -5000.0


@pytest.mark.parametrize(
    "opening_cash",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
        True,
        False,
    ],
)
def test_invalid_opening_cash_is_rejected(
    opening_cash,
):
    with pytest.raises(ValidationError):
        _valid_input(
            opening_cash=opening_cash
        )


def test_duplicate_event_ids_are_rejected():
    duplicate = _event(
        "invoice-001",
        source_type="MODELLED",
    )

    with pytest.raises(
        ValidationError,
        match="Duplicate cash event ID",
    ):
        DirectCashForecastInput(
            start_date="2026-10-05",
            opening_cash=50000.0,
            events=(
                _event("invoice-001"),
                duplicate,
            ),
        )


def test_unknown_committed_reference_is_rejected():
    modelled = _event(
        "model-receipts-001",
        source_type="MODELLED",
    )

    with pytest.raises(
        ValidationError,
        match="unknown committed event ID",
    ):
        DirectCashForecastInput(
            start_date="2026-10-05",
            opening_cash=50000.0,
            events=(modelled,),
            coverage_allocations=(
                _coverage(),
            ),
        )


def test_unknown_modelled_reference_is_rejected():
    committed = _event(
        "invoice-001"
    )

    with pytest.raises(
        ValidationError,
        match="unknown modelled event ID",
    ):
        DirectCashForecastInput(
            start_date="2026-10-05",
            opening_cash=50000.0,
            events=(committed,),
            coverage_allocations=(
                _coverage(),
            ),
        )


def test_committed_reference_must_be_committed():
    wrong = _event(
        "invoice-001",
        source_type="MODELLED",
    )

    modelled = _event(
        "model-receipts-001",
        source_type="MODELLED",
    )

    with pytest.raises(
        ValidationError,
        match="must reference a COMMITTED",
    ):
        DirectCashForecastInput(
            start_date="2026-10-05",
            opening_cash=50000.0,
            events=(wrong, modelled),
            coverage_allocations=(
                _coverage(),
            ),
        )


def test_modelled_reference_must_be_modelled():
    committed = _event(
        "invoice-001"
    )

    wrong = _event(
        "model-receipts-001",
        source_type="COMMITTED",
    )

    with pytest.raises(
        ValidationError,
        match="must reference a MODELLED",
    ):
        DirectCashForecastInput(
            start_date="2026-10-05",
            opening_cash=50000.0,
            events=(committed, wrong),
            coverage_allocations=(
                _coverage(),
            ),
        )


@pytest.mark.parametrize(
    ("event_id", "source_type"),
    [
        ("invoice-001", "COMMITTED"),
        ("model-receipts-001", "MODELLED"),
    ],
)
def test_coverage_requires_active_events(
    event_id,
    source_type,
):
    committed = _event(
        "invoice-001"
    )

    modelled = _event(
        "model-receipts-001",
        source_type="MODELLED",
    )

    replacement = _event(
        event_id,
        source_type=source_type,
        status="CANCELLED",
    )

    events = tuple(
        replacement
        if event.event_id == event_id
        else event
        for event in (
            committed,
            modelled,
        )
    )

    with pytest.raises(
        ValidationError,
        match="non-active",
    ):
        DirectCashForecastInput(
            start_date="2026-10-05",
            opening_cash=50000.0,
            events=events,
            coverage_allocations=(
                _coverage(),
            ),
        )


def test_coverage_cannot_cross_cash_direction():
    committed = _event(
        "invoice-001",
        direction="INFLOW",
    )

    modelled = _event(
        "model-receipts-001",
        direction="OUTFLOW",
        source_type="MODELLED",
    )

    with pytest.raises(
        ValidationError,
        match="different cash directions",
    ):
        DirectCashForecastInput(
            start_date="2026-10-05",
            opening_cash=50000.0,
            events=(committed, modelled),
            coverage_allocations=(
                _coverage(),
            ),
        )


def test_coverage_cannot_exceed_commitment():
    with pytest.raises(
        ValidationError,
        match="cannot exceed",
    ):
        _valid_input(
            coverage_allocations=(
                _coverage(
                    amount=6000.01
                ),
            ),
        )


def test_one_commitment_cannot_cover_two_models():
    committed = _event(
        "invoice-001",
        amount=6000.0,
    )

    first_model = _event(
        "model-receipts-001",
        amount=10000.0,
        source_type="MODELLED",
    )

    second_model = _event(
        "model-receipts-002",
        amount=8000.0,
        source_type="MODELLED",
    )

    with pytest.raises(
        ValidationError,
        match="at most one coverage",
    ):
        DirectCashForecastInput(
            start_date="2026-10-05",
            opening_cash=50000.0,
            events=(
                committed,
                first_model,
                second_model,
            ),
            coverage_allocations=(
                _coverage(
                    coverage_id="coverage-001",
                    modelled_event_id="model-receipts-001",
                    amount=3000.0,
                ),
                _coverage(
                    coverage_id="coverage-002",
                    modelled_event_id="model-receipts-002",
                    amount=3000.0,
                ),
            ),
        )


def test_multiple_commitments_can_cover_one_model():
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

    contract = DirectCashForecastInput(
        start_date="2026-10-05",
        opening_cash=50000.0,
        events=(
            first,
            second,
            modelled,
        ),
        coverage_allocations=(
            _coverage(
                coverage_id="coverage-001",
                committed_event_id="invoice-001",
                amount=6000.0,
            ),
            _coverage(
                coverage_id="coverage-002",
                committed_event_id="invoice-002",
                amount=5000.0,
            ),
        ),
    )

    assert (
        len(contract.coverage_allocations)
        == 2
    )


def test_modelled_overcoverage_is_allowed():
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

    contract = DirectCashForecastInput(
        start_date="2026-10-05",
        opening_cash=50000.0,
        events=(
            first,
            second,
            modelled,
        ),
        coverage_allocations=(
            _coverage(
                coverage_id="coverage-001",
                committed_event_id="invoice-001",
                amount=6000.0,
            ),
            _coverage(
                coverage_id="coverage-002",
                committed_event_id="invoice-002",
                amount=5000.0,
            ),
        ),
    )

    total_coverage = sum(
        allocation.amount
        for allocation
        in contract.coverage_allocations
    )

    assert total_coverage == 11000.0


def test_duplicate_coverage_ids_are_rejected():
    committed = _event(
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

    with pytest.raises(
        ValidationError,
        match="Duplicate cash coverage ID",
    ):
        DirectCashForecastInput(
            start_date="2026-10-05",
            opening_cash=50000.0,
            events=(
                committed,
                second,
                modelled,
            ),
            coverage_allocations=(
                _coverage(
                    coverage_id="same-id",
                    committed_event_id="invoice-001",
                    amount=6000.0,
                ),
                _coverage(
                    coverage_id="same-id",
                    committed_event_id="invoice-002",
                    amount=5000.0,
                ),
            ),
        )


@pytest.mark.parametrize(
    "amount",
    [
        0.0,
        -1.0,
        float("nan"),
        float("inf"),
        float("-inf"),
        True,
        False,
    ],
)
def test_invalid_coverage_amount_is_rejected(
    amount,
):
    with pytest.raises(ValidationError):
        _coverage(
            amount=amount
        )


def test_contract_is_immutable():
    contract = _valid_input()

    with pytest.raises(ValidationError):
        contract.opening_cash = 1.0


def test_contract_round_trips_deterministically():
    contract = _valid_input()

    first = contract.model_dump(
        mode="json"
    )

    second = contract.model_dump(
        mode="json"
    )

    assert first == second

    restored = (
        DirectCashForecastInput
        .model_validate(first)
    )

    assert restored == contract
    assert (
        restored.model_dump(mode="json")
        == first
    )


def test_start_date_is_explicit():
    contract = _valid_input()

    assert (
        contract.start_date
        == date(2026, 10, 5)
    )
