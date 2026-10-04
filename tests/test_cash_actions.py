from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from src.core.cash_actions import (
    CashAction,
    CashActionRegister,
    create_cash_action_register,
    replace_cash_action,
)


def _action(
    action_id="action-001",
    *,
    action_type="RECEIVABLE_ACCELERATION",
    action="Call customer and agree earlier payment",
    owner="Finance Manager",
    target_date=date(2026, 10, 10),
    expected_cash_impact=10000.0,
    status="PLANNED",
    originating_recovery_plan_id="plan-001",
    realised_cash_benefit=None,
    realised_benefit_evidence_reference=None,
):
    return CashAction(
        action_id=action_id,
        action_type=action_type,
        action=action,
        owner=owner,
        target_date=target_date,
        expected_cash_impact=expected_cash_impact,
        status=status,
        originating_recovery_plan_id=(
            originating_recovery_plan_id
        ),
        realised_cash_benefit=(
            realised_cash_benefit
        ),
        realised_benefit_evidence_reference=(
            realised_benefit_evidence_reference
        ),
        created_at=datetime(
            2026,
            10,
            4,
            9,
            0,
            tzinfo=timezone.utc,
        ),
    )


def test_cash_action_preserves_core_fields():
    action = _action()

    assert action.action_id == "action-001"
    assert (
        action.action_type
        == "RECEIVABLE_ACCELERATION"
    )
    assert action.owner == "Finance Manager"
    assert action.expected_cash_impact == 10000.0
    assert action.status == "PLANNED"
    assert (
        action.originating_recovery_plan_id
        == "plan-001"
    )


@pytest.mark.parametrize(
    "field_name,value",
    [
        ("action_id", ""),
        ("action_id", "   "),
        ("action", ""),
        ("owner", "   "),
    ],
)
def test_required_strings_cannot_be_blank(
    field_name,
    value,
):
    kwargs = {
        field_name: value,
    }

    with pytest.raises(ValidationError):
        _action(**kwargs)


@pytest.mark.parametrize(
    "value",
    [
        -1.0,
        float("inf"),
        float("-inf"),
        float("nan"),
        True,
    ],
)
def test_expected_cash_impact_must_be_valid(
    value,
):
    with pytest.raises(ValidationError):
        _action(
            expected_cash_impact=value,
        )


def test_realised_benefit_requires_evidence():
    with pytest.raises(
        ValidationError,
        match="provided together",
    ):
        _action(
            realised_cash_benefit=8000.0,
        )


def test_realised_evidence_requires_benefit():
    with pytest.raises(
        ValidationError,
        match="provided together",
    ):
        _action(
            realised_benefit_evidence_reference=(
                "bank-transaction-001"
            ),
        )


def test_realised_benefit_with_evidence_is_valid():
    action = _action(
        status="COMPLETED",
        realised_cash_benefit=8000.0,
        realised_benefit_evidence_reference=(
            "bank-transaction-001"
        ),
    )

    assert action.realised_cash_benefit == 8000.0
    assert (
        action.realised_benefit_evidence_reference
        == "bank-transaction-001"
    )


def test_created_at_must_be_timezone_aware():
    with pytest.raises(
        ValidationError,
        match="timezone-aware",
    ):
        CashAction(
            action_id="action-001",
            action_type="COST_REDUCTION",
            action="Pause discretionary spend",
            owner="CFO",
            target_date=date(2026, 10, 10),
            expected_cash_impact=5000.0,
            created_at=datetime(
                2026,
                10,
                4,
                9,
                0,
            ),
        )


def test_register_rejects_duplicate_action_ids():
    with pytest.raises(
        ValidationError,
        match="unique",
    ):
        CashActionRegister(
            actions=(
                _action("action-001"),
                _action("action-001"),
            )
        )


def test_register_has_deterministic_order():
    register = create_cash_action_register(
        (
            _action(
                "action-b",
                target_date=date(
                    2026,
                    10,
                    20,
                ),
            ),
            _action(
                "action-c",
                target_date=date(
                    2026,
                    10,
                    10,
                ),
            ),
            _action(
                "action-a",
                target_date=date(
                    2026,
                    10,
                    10,
                ),
            ),
        )
    )

    assert [
        action.action_id
        for action in register.actions
    ] == [
        "action-a",
        "action-c",
        "action-b",
    ]


def test_replace_action_does_not_mutate_prior_register():
    original_action = _action()

    register = create_cash_action_register(
        (original_action,)
    )

    updated = original_action.model_copy(
        update={
            "status": "IN_PROGRESS",
        }
    )

    next_register = replace_cash_action(
        register,
        updated,
    )

    assert (
        register.actions[0].status
        == "PLANNED"
    )

    assert (
        next_register.actions[0].status
        == "IN_PROGRESS"
    )


def test_replace_unknown_action_is_rejected():
    register = create_cash_action_register(
        (
            _action("action-001"),
        )
    )

    with pytest.raises(
        ValueError,
        match="unknown",
    ):
        replace_cash_action(
            register,
            _action("action-999"),
        )


def test_action_is_immutable():
    action = _action()

    with pytest.raises(ValidationError):
        action.status = "COMPLETED"


def test_register_round_trips():
    register = create_cash_action_register(
        (
            _action("action-001"),
            _action(
                "action-002",
                status="COMPLETED",
                realised_cash_benefit=5000.0,
                realised_benefit_evidence_reference=(
                    "bank-002"
                ),
            ),
        )
    )

    payload = register.model_dump(
        mode="json"
    )

    restored = (
        CashActionRegister
        .model_validate(payload)
    )

    assert restored == register
    assert (
        restored.model_dump(mode="json")
        == payload
    )
