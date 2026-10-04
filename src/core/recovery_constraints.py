from __future__ import annotations

from datetime import date

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from src.core.direct_cash import (
    DirectCashForecastInput,
)


class RevenueImprovementConstraint(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    enabled: bool = True

    max_improvement_pct: float = Field(
        default=0.0,
        ge=0.0,
        allow_inf_nan=False,
    )

    available_from: date
    eligible_event_ids: tuple[str, ...] = ()

    @field_validator("eligible_event_ids")
    @classmethod
    def _validate_ids(
        cls,
        values: tuple[str, ...],
    ) -> tuple[str, ...]:
        return _clean_unique_ids(values)


class CostReductionConstraint(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    enabled: bool = True

    max_reduction_pct: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        allow_inf_nan=False,
    )

    available_from: date
    eligible_event_ids: tuple[str, ...] = ()

    @field_validator("eligible_event_ids")
    @classmethod
    def _validate_ids(
        cls,
        values: tuple[str, ...],
    ) -> tuple[str, ...]:
        return _clean_unique_ids(values)


class ReceivableAccelerationConstraint(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    enabled: bool = True

    max_acceleration_days: int = Field(
        default=0,
        ge=0,
    )

    available_from: date
    eligible_event_ids: tuple[str, ...] = ()

    @field_validator("eligible_event_ids")
    @classmethod
    def _validate_ids(
        cls,
        values: tuple[str, ...],
    ) -> tuple[str, ...]:
        return _clean_unique_ids(values)


class ExternalLiquidityConstraint(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    enabled: bool = True

    max_amount: float = Field(
        default=0.0,
        ge=0.0,
        allow_inf_nan=False,
    )

    available_from: date


class RecoveryConstraintSet(BaseModel):
    """
    Hard management constraints for deterministic
    13-week recovery analysis.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    revenue_improvement: RevenueImprovementConstraint
    cost_reduction: CostReductionConstraint
    receivable_acceleration: ReceivableAccelerationConstraint
    external_liquidity: ExternalLiquidityConstraint


def _clean_unique_ids(
    values: tuple[str, ...],
) -> tuple[str, ...]:
    cleaned: list[str] = []
    seen: set[str] = set()

    for value in values:
        if not isinstance(value, str):
            raise ValueError(
                "eligible event IDs must be strings."
            )

        event_id = value.strip()

        if not event_id:
            raise ValueError(
                "eligible event IDs must not be blank."
            )

        if event_id in seen:
            raise ValueError(
                "Duplicate eligible event ID: "
                f"{event_id}"
            )

        seen.add(event_id)
        cleaned.append(event_id)

    return tuple(cleaned)


def validate_recovery_constraints(
    forecast_input: DirectCashForecastInput,
    constraints: RecoveryConstraintSet,
) -> None:
    """
    Validate that each recovery lever is explicitly scoped
    to compatible cash events.

    No event eligibility is inferred from category or timing.
    """
    events = {
        event.event_id: event
        for event in forecast_input.events
    }

    _validate_target_events(
        events=events,
        event_ids=(
            constraints
            .revenue_improvement
            .eligible_event_ids
        ),
        expected_source_type="MODELLED",
        expected_direction="INFLOW",
        lever_name="Revenue improvement",
    )

    _validate_target_events(
        events=events,
        event_ids=(
            constraints
            .cost_reduction
            .eligible_event_ids
        ),
        expected_source_type="MODELLED",
        expected_direction="OUTFLOW",
        lever_name="Cost reduction",
    )

    _validate_target_events(
        events=events,
        event_ids=(
            constraints
            .receivable_acceleration
            .eligible_event_ids
        ),
        expected_source_type="COMMITTED",
        expected_direction="INFLOW",
        lever_name="Receivable acceleration",
    )


def _validate_target_events(
    *,
    events: dict,
    event_ids: tuple[str, ...],
    expected_source_type: str,
    expected_direction: str,
    lever_name: str,
) -> None:
    for event_id in event_ids:
        event = events.get(event_id)

        if event is None:
            raise ValueError(
                f"{lever_name} references unknown "
                f"event ID: {event_id}"
            )

        if event.status != "ACTIVE":
            raise ValueError(
                f"{lever_name} can only target "
                "ACTIVE events."
            )

        if (
            event.source_type
            != expected_source_type
        ):
            raise ValueError(
                f"{lever_name} requires "
                f"{expected_source_type} events."
            )

        if (
            event.direction
            != expected_direction
        ):
            raise ValueError(
                f"{lever_name} requires "
                f"{expected_direction} events."
            )
