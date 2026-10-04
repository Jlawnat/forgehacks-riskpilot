from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


CashDirection = Literal[
    "INFLOW",
    "OUTFLOW",
]

CashEventSourceType = Literal[
    "ACTUAL",
    "COMMITTED",
    "MODELLED",
    "MANAGEMENT_ASSUMPTION",
]

CashEventStatus = Literal[
    "ACTIVE",
    "SETTLED",
    "CANCELLED",
]


class CashEvent(BaseModel):
    """
    Canonical dated cash-event representation.

    `date` is the base/default cash date attached to the event.

    `due_date`, when present, preserves the contractual due date.

    `expected_cash_date`, when present, represents the current
    expected timing of the cash movement without altering the
    contractual due date.

    For future cash-forecast timing, the effective date is:

        expected_cash_date -> due_date -> date

    Scenario timing adjustments are intentionally not represented
    here. They belong to a separate scenario overlay.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    event_id: str
    date: date

    amount: float = Field(
        ge=0.0,
        allow_inf_nan=False,
    )

    direction: CashDirection
    category: str
    source_type: CashEventSourceType
    status: CashEventStatus

    description: str | None = None
    source_reference: str

    due_date: date | None = None
    expected_cash_date: date | None = None

    @field_validator(
        "event_id",
        "category",
        "source_reference",
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
        "amount",
        mode="before",
    )
    @classmethod
    def _reject_boolean_amount(
        cls,
        value: object,
    ) -> object:
        if isinstance(value, bool):
            raise ValueError(
                "amount must be numeric, not boolean."
            )

        return value

    @property
    def signed_amount(self) -> float:
        """
        Cash-sign representation derived from direction.

        Stored amounts remain nonnegative.
        """
        if self.direction == "INFLOW":
            return float(self.amount)

        return -float(self.amount)

    @property
    def effective_cash_date(self) -> date:
        """
        Resolve base forecast timing without mutating source dates.
        """
        return (
            self.expected_cash_date
            or self.due_date
            or self.date
        )


def ensure_unique_cash_event_ids(
    *collections: Iterable[CashEvent],
) -> None:
    """
    Reject duplicate event IDs within or across event collections.
    """
    seen: set[str] = set()

    for events in collections:
        for event in events:
            if event.event_id in seen:
                raise ValueError(
                    "Duplicate cash event ID: "
                    f"{event.event_id}"
                )

            seen.add(event.event_id)
