from datetime import datetime, timezone

import pytest

from src.ai.context import (
    build_risk_analyst_context,
)
from src.ai.tools import (
    liquidity_decision_brief_snapshot,
)
from src.core.cash_actions import (
    create_cash_action_register,
)
from src.core.cash_events import CashEvent
from src.core.direct_cash import (
    DirectCashForecastInput,
)
from src.core.forecast_monitoring import (
    create_forecast_snapshot,
)
from src.core.liquidity_brief import (
    build_liquidity_decision_brief,
)
from src.core.risk_policy import RiskPolicy
from src.ingestion.loader import (
    load_business_csv,
)
from src.ingestion.validator import (
    validate_business_data,
)


@pytest.fixture(scope="module")
def legacy_df():
    raw = load_business_csv(
        "data/demo/borderline_business.csv"
    )

    df, _ = validate_business_data(
        raw
    )

    return df


def _policy():
    return RiskPolicy(
        minimum_cash_reserve=20000.0,
        max_shortfall_probability=0.05,
    )


def _brief():
    forecast_input = DirectCashForecastInput(
        start_date="2026-10-05",
        opening_cash=50000.0,
        events=(
            CashEvent(
                event_id="invoice-001",
                date="2026-10-12",
                amount=10000.0,
                direction="INFLOW",
                category="customer receipts",
                source_type="COMMITTED",
                status="ACTIVE",
                source_reference="invoice-system",
            ),
        ),
    )

    snapshot = create_forecast_snapshot(
        forecast_input,
        snapshot_id="snapshot-v2",
        created_at=datetime(
            2026,
            10,
            4,
            9,
            0,
            tzinfo=timezone.utc,
        ),
        management_reserve=20000.0,
    )

    return build_liquidity_decision_brief(
        snapshot,
        create_cash_action_register(()),
        brief_id="brief-v2",
        created_at=datetime(
            2026,
            10,
            4,
            9,
            30,
            tzinfo=timezone.utc,
        ),
    )


def test_v2_brief_snapshot_reports_unavailable(
    legacy_df,
):
    context = build_risk_analyst_context(
        legacy_df,
        _policy(),
        horizon=3,
    )

    payload = liquidity_decision_brief_snapshot(
        context
    )

    assert payload["available"] is False
    assert "brief" not in payload


def test_context_can_carry_precomputed_v2_brief(
    legacy_df,
):
    brief = _brief()

    context = build_risk_analyst_context(
        legacy_df,
        _policy(),
        horizon=3,
        liquidity_brief=brief,
    )

    assert context.liquidity_brief is brief


def test_v2_snapshot_returns_exact_precomputed_values(
    legacy_df,
):
    brief = _brief()

    context = build_risk_analyst_context(
        legacy_df,
        _policy(),
        horizon=3,
        liquidity_brief=brief,
    )

    payload = liquidity_decision_brief_snapshot(
        context
    )

    assert payload["available"] is True

    assert (
        payload["brief"]["brief_id"]
        == "brief-v2"
    )

    assert (
        payload["brief"]["position"][
            "current_cash"
        ]
        == 50000.0
    )

    assert (
        payload["brief"]["position"][
            "management_reserve"
        ]
        == 20000.0
    )

    assert (
        payload["brief"]["position"][
            "closing_cash_13_week"
        ]
        == 60000.0
    )


def test_v2_snapshot_preserves_cash_driver_evidence(
    legacy_df,
):
    brief = _brief()

    context = build_risk_analyst_context(
        legacy_df,
        _policy(),
        horizon=3,
        liquidity_brief=brief,
    )

    payload = liquidity_decision_brief_snapshot(
        context
    )

    driver = payload["brief"][
        "cash_drivers"
    ][0]

    assert driver["event_id"] == "invoice-001"
    assert driver["source_type"] == "COMMITTED"
    assert driver["included_amount"] == 10000.0


def test_grounding_notes_protect_metric_semantics(
    legacy_df,
):
    context = build_risk_analyst_context(
        legacy_df,
        _policy(),
        horizon=3,
        liquidity_brief=_brief(),
    )

    payload = liquidity_decision_brief_snapshot(
        context
    )

    notes = payload[
        "grounding_notes"
    ]

    assert (
        "not a probability"
        in notes["evidence_coverage"]
    )

    assert (
        "not realised"
        in notes["cash_actions"]
    )

    assert (
        "separate"
        in notes["recovery"]
    )
