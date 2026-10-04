from __future__ import annotations

from datetime import date, datetime
from math import isfinite
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
    model_validator,
)


CashActionStatus = Literal[
    "PLANNED",
    "IN_PROGRESS",
    "COMPLETED",
    "CANCELLED",
]


CashActionType = Literal[
    "REVENUE_IMPROVEMENT",
    "COST_REDUCTION",
    "RECEIVABLE_ACCELERATION",
    "EXTERNAL_LIQUIDITY",
    "OTHER",
]


class CashAction(BaseModel):
    """
    One management action intended to improve liquidity.

    expected_cash_impact is a nonnegative expected liquidity
    benefit. It is not treated as realised cash until supported
    by explicit evidence.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    action_id: str
    action_type: CashActionType

    action: str
    owner: str

    target_date: date

    expected_cash_impact: float

    status: CashActionStatus = "PLANNED"

    originating_recovery_plan_id: str | None = None

    realised_cash_benefit: float | None = None
    realised_benefit_evidence_reference: str | None = None

    created_at: datetime

    @field_validator(
        "action_id",
        "action",
        "owner",
    )
    @classmethod
    def _require_nonblank_string(
        cls,
        value: str,
    ) -> str:
        if not isinstance(value, str):
            raise ValueError(
                "Value must be a string."
            )

        cleaned = value.strip()

        if not cleaned:
            raise ValueError(
                "Value must not be blank."
            )

        return cleaned

    @field_validator(
        "originating_recovery_plan_id",
        "realised_benefit_evidence_reference",
    )
    @classmethod
    def _clean_optional_string(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        if not isinstance(value, str):
            raise ValueError(
                "Value must be a string."
            )

        cleaned = value.strip()

        if not cleaned:
            raise ValueError(
                "Optional string must not be blank."
            )

        return cleaned

    @field_validator(
        "expected_cash_impact",
        "realised_cash_benefit",
        mode="before",
    )
    @classmethod
    def _validate_money(
        cls,
        value: object,
    ) -> object:
        if value is None:
            return value

        if isinstance(value, bool):
            raise ValueError(
                "Cash amount must be numeric, not boolean."
            )

        numeric = float(value)

        if (
            not isfinite(numeric)
            or numeric < 0.0
        ):
            raise ValueError(
                "Cash amount must be finite and nonnegative."
            )

        return value

    @field_validator("created_at")
    @classmethod
    def _require_timezone(
        cls,
        value: datetime,
    ) -> datetime:
        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "created_at must be timezone-aware."
            )

        return value

    @model_validator(mode="after")
    def _validate_realised_benefit_evidence(
        self,
    ) -> "CashAction":
        has_benefit = (
            self.realised_cash_benefit is not None
        )

        has_evidence = (
            self.realised_benefit_evidence_reference
            is not None
        )

        if has_benefit != has_evidence:
            raise ValueError(
                "realised_cash_benefit and "
                "realised_benefit_evidence_reference "
                "must be provided together."
            )

        return self


class CashActionRegister(BaseModel):
    """
    Immutable lightweight register of liquidity actions.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    actions: tuple[CashAction, ...] = ()

    @model_validator(mode="after")
    def _require_unique_action_ids(
        self,
    ) -> "CashActionRegister":
        ids = [
            action.action_id
            for action in self.actions
        ]

        if len(ids) != len(set(ids)):
            raise ValueError(
                "Cash action IDs must be unique."
            )

        return self


def create_cash_action_register(
    actions: tuple[CashAction, ...],
) -> CashActionRegister:
    """
    Create an immutable action register with deterministic
    action ordering.
    """
    return CashActionRegister(
        actions=tuple(
            sorted(
                actions,
                key=lambda item: (
                    item.target_date,
                    item.action_id,
                ),
            )
        )
    )


def replace_cash_action(
    register: CashActionRegister,
    updated_action: CashAction,
) -> CashActionRegister:
    """
    Return a new register with one explicitly updated action.

    The prior register remains unchanged.
    """
    matches = [
        action
        for action in register.actions
        if (
            action.action_id
            == updated_action.action_id
        )
    ]

    if not matches:
        raise ValueError(
            "Cannot replace unknown cash action ID: "
            f"{updated_action.action_id}"
        )

    actions = tuple(
        updated_action
        if (
            action.action_id
            == updated_action.action_id
        )
        else action
        for action in register.actions
    )

    return create_cash_action_register(
        actions
    )
