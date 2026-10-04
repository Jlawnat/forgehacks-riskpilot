from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.core.cash_events import CashEvent
from src.core.direct_cash import (
    DirectCashForecastInput,
)
from src.core.forecast_monitoring import (
    DirectCashForecastSnapshot,
    create_forecast_snapshot,
    forecast_basis_fingerprint,
)


def _event(
    event_id: str,
    *,
    amount: float = 10000.0,
    direction: str = "INFLOW",
    source_type: str = "COMMITTED",
) -> CashEvent:
    return CashEvent(
        event_id=event_id,
        date="2026-10-12",
        amount=amount,
        direction=direction,
        category="cash",
        source_type=source_type,
        status="ACTIVE",
        source_reference=f"source-{event_id}",
    )


def _input(
    *,
    opening_cash: float = 50000.0,
    events=(),
) -> DirectCashForecastInput:
    return DirectCashForecastInput(
        start_date="2026-10-05",
        opening_cash=opening_cash,
        events=tuple(events),
    )


def _created_at():
    return datetime(
        2026,
        10,
        4,
        18,
        30,
        tzinfo=timezone.utc,
    )


def test_baseline_snapshot_captures_exact_forecast():
    forecast_input = _input(
        events=(
            _event(
                "receipt-001",
                amount=10000.0,
            ),
        )
    )

    snapshot = create_forecast_snapshot(
        forecast_input,
        snapshot_id="snapshot-001",
        created_at=_created_at(),
        management_reserve=25000.0,
    )

    assert snapshot.snapshot_type == "BASELINE"
    assert snapshot.scenario_name is None

    assert (
        snapshot.forecast_input
        == forecast_input
    )

    assert (
        snapshot.forecast.closing_cash
        == 60000.0
    )

    assert (
        snapshot.decision_metrics
        .management_reserve
        == 25000.0
    )


def test_snapshot_does_not_mutate_input():
    forecast_input = _input(
        events=(
            _event("receipt-001"),
        )
    )

    before = forecast_input.model_dump(
        mode="json"
    )

    create_forecast_snapshot(
        forecast_input,
        snapshot_id="snapshot-001",
        created_at=_created_at(),
        management_reserve=25000.0,
    )

    assert (
        forecast_input.model_dump(
            mode="json"
        )
        == before
    )


def test_fingerprint_is_stable():
    forecast_input = _input(
        events=(
            _event("receipt-001"),
        )
    )

    first = forecast_basis_fingerprint(
        forecast_input,
        management_reserve=25000.0,
    )

    second = forecast_basis_fingerprint(
        forecast_input.model_copy(),
        management_reserve=25000.0,
    )

    assert first == second


def test_fingerprint_changes_when_cash_evidence_changes():
    first_input = _input(
        events=(
            _event(
                "receipt-001",
                amount=10000.0,
            ),
        )
    )

    second_input = _input(
        events=(
            _event(
                "receipt-001",
                amount=11000.0,
            ),
        )
    )

    assert (
        forecast_basis_fingerprint(
            first_input,
            management_reserve=25000.0,
        )
        != forecast_basis_fingerprint(
            second_input,
            management_reserve=25000.0,
        )
    )


def test_fingerprint_changes_when_reserve_changes():
    forecast_input = _input()

    assert (
        forecast_basis_fingerprint(
            forecast_input,
            management_reserve=10000.0,
        )
        != forecast_basis_fingerprint(
            forecast_input,
            management_reserve=20000.0,
        )
    )


def test_scenario_snapshot_requires_name():
    with pytest.raises(
        ValidationError,
        match="scenario_name",
    ):
        create_forecast_snapshot(
            _input(),
            snapshot_id="scenario-001",
            created_at=_created_at(),
            management_reserve=0.0,
            snapshot_type="SCENARIO",
        )


def test_named_scenario_snapshot_is_valid():
    snapshot = create_forecast_snapshot(
        _input(),
        snapshot_id="scenario-001",
        created_at=_created_at(),
        management_reserve=0.0,
        snapshot_type="SCENARIO",
        scenario_name="Delayed customer receipt",
    )

    assert snapshot.snapshot_type == "SCENARIO"

    assert (
        snapshot.scenario_name
        == "Delayed customer receipt"
    )


def test_baseline_cannot_have_scenario_name():
    with pytest.raises(
        ValidationError,
        match="BASELINE",
    ):
        create_forecast_snapshot(
            _input(),
            snapshot_id="snapshot-001",
            created_at=_created_at(),
            management_reserve=0.0,
            snapshot_type="BASELINE",
            scenario_name="Not allowed",
        )


def test_created_at_must_be_timezone_aware():
    with pytest.raises(
        ValidationError,
        match="timezone-aware",
    ):
        create_forecast_snapshot(
            _input(),
            snapshot_id="snapshot-001",
            created_at=datetime(
                2026,
                10,
                4,
                18,
                30,
            ),
            management_reserve=0.0,
        )


@pytest.mark.parametrize(
    "snapshot_id",
    [
        "",
        "   ",
    ],
)
def test_snapshot_id_must_be_nonblank(
    snapshot_id,
):
    with pytest.raises(ValidationError):
        create_forecast_snapshot(
            _input(),
            snapshot_id=snapshot_id,
            created_at=_created_at(),
            management_reserve=0.0,
        )


def test_snapshot_is_immutable():
    snapshot = create_forecast_snapshot(
        _input(),
        snapshot_id="snapshot-001",
        created_at=_created_at(),
        management_reserve=0.0,
    )

    with pytest.raises(ValidationError):
        snapshot.snapshot_id = "changed"


def test_snapshot_round_trips_deterministically():
    snapshot = create_forecast_snapshot(
        _input(
            events=(
                _event("receipt-001"),
            )
        ),
        snapshot_id="snapshot-001",
        created_at=_created_at(),
        management_reserve=25000.0,
    )

    payload = snapshot.model_dump(
        mode="json"
    )

    restored = (
        DirectCashForecastSnapshot
        .model_validate(payload)
    )

    assert restored == snapshot

    assert (
        restored.model_dump(mode="json")
        == payload
    )
