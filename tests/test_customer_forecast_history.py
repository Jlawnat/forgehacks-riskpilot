from datetime import date, datetime, timezone

from src.core.cash_events import (
    CashEvent,
)
from src.core.forecast_monitoring import (
    compare_forecast_snapshots,
    create_forecast_snapshot,
)
from src.core.direct_cash import (
    DirectCashForecastInput,
)


def _snapshot(
    snapshot_id: str,
    *,
    receipt_amount: float,
    receipt_date: str = "2026-10-12",
    reserve: float = 40000.0,
):
    forecast_input = (
        DirectCashForecastInput(
            start_date=date(
                2026,
                10,
                5,
            ),
            opening_cash=100000.0,
            events=(
                CashEvent(
                    event_id="invoice-001",
                    date=receipt_date,
                    amount=(
                        receipt_amount
                    ),
                    direction="INFLOW",
                    category=(
                        "customer receipts"
                    ),
                    source_type=(
                        "COMMITTED"
                    ),
                    status="ACTIVE",
                    source_reference=(
                        "ar-ledger"
                    ),
                ),
            ),
        )
    )

    return create_forecast_snapshot(
        forecast_input,
        snapshot_id=snapshot_id,
        created_at=datetime(
            2026,
            10,
            7,
            7,
            0,
            tzinfo=timezone.utc,
        ),
        management_reserve=reserve,
    )


def test_customer_snapshot_comparison_detects_amount_change():
    prior = _snapshot(
        "v001",
        receipt_amount=25000.0,
    )

    current = _snapshot(
        "v002",
        receipt_amount=18000.0,
    )

    comparison = (
        compare_forecast_snapshots(
            prior,
            current,
        )
    )

    assert (
        comparison.same_forecast_basis
        is False
    )

    assert len(
        comparison.variances
    ) == 1

    assert (
        comparison.variances[0]
        .category
        == "AMOUNT"
    )

    assert (
        comparison
        .closing_cash_change
        == -7000.0
    )


def test_customer_snapshot_comparison_detects_timing_change():
    prior = _snapshot(
        "v001",
        receipt_amount=25000.0,
        receipt_date="2026-10-12",
    )

    current = _snapshot(
        "v002",
        receipt_amount=25000.0,
        receipt_date="2026-10-19",
    )

    comparison = (
        compare_forecast_snapshots(
            prior,
            current,
        )
    )

    assert any(
        item.category
        == "TIMING"
        for item in (
            comparison.variances
        )
    )


def test_customer_snapshot_comparison_detects_reserve_change():
    prior = _snapshot(
        "v001",
        receipt_amount=25000.0,
        reserve=40000.0,
    )

    current = _snapshot(
        "v002",
        receipt_amount=25000.0,
        reserve=50000.0,
    )

    comparison = (
        compare_forecast_snapshots(
            prior,
            current,
        )
    )

    assert (
        comparison
        .management_reserve_changed
        is True
    )

    assert (
        comparison
        .current_management_reserve
        == 50000.0
    )
