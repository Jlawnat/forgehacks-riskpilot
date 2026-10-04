from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from src.core.direct_cash import (
    DirectCashForecastInput,
)


class ModelledCashErrorSample(BaseModel):
    """
    One paired relative-error observation for modelled
    weekly cash flows.

    Example:
        inflow_error_pct=-0.10
        outflow_error_pct=0.05

    means modelled inflows were 10% below expectation
    while modelled outflows were 5% above expectation.

    Percentage errors are dimensionless, unlike the legacy
    monthly absolute revenue/cost residuals.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    inflow_error_pct: float = Field(
        ge=-1.0,
        allow_inf_nan=False,
    )

    outflow_error_pct: float = Field(
        ge=-1.0,
        allow_inf_nan=False,
    )

    @field_validator(
        "inflow_error_pct",
        "outflow_error_pct",
        mode="before",
    )
    @classmethod
    def _reject_boolean_error(
        cls,
        value: object,
    ) -> object:
        if isinstance(value, bool):
            raise ValueError(
                "Cash error percentages must be "
                "numeric, not boolean."
            )

        return value


class CommittedTimingUncertainty(BaseModel):
    """
    Empirical timing uncertainty for one named committed
    cash event.

    Each value is a day shift relative to the event's
    effective cash date:

        negative = earlier
        zero     = unchanged
        positive = later

    At least three observations are required for empirical
    resampling, though three observations should still be
    treated as a severe small-sample limitation.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    event_id: str

    timing_shift_days_samples: tuple[
        int,
        ...,
    ] = Field(
        min_length=3,
    )

    source_reference: str

    @field_validator(
        "event_id",
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
        "timing_shift_days_samples",
        mode="before",
    )
    @classmethod
    def _reject_boolean_day_samples(
        cls,
        values: object,
    ) -> object:
        try:
            items = tuple(values)
        except TypeError as exc:
            raise ValueError(
                "Timing-shift samples must be "
                "an iterable of integers."
            ) from exc

        if any(
            isinstance(value, bool)
            for value in items
        ):
            raise ValueError(
                "Timing-shift samples must be "
                "integers, not booleans."
            )

        return items


class WeeklyUncertaintyProfile(BaseModel):
    """
    Evidence supplied to the 13-week uncertainty engine.

    This object contains no legacy monthly residuals.

    Modelled cash uncertainty:
        paired dimensionless inflow/outflow errors.

    Committed cash uncertainty:
        explicit event-level empirical timing shifts.

    Management assumptions remain deterministic unless
    a future contract explicitly models their uncertainty.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    modelled_flow_error_samples: tuple[
        ModelledCashErrorSample,
        ...,
    ] = ()

    committed_timing_uncertainty: tuple[
        CommittedTimingUncertainty,
        ...,
    ] = ()


def validate_weekly_uncertainty_profile(
    forecast_input: DirectCashForecastInput,
    profile: WeeklyUncertaintyProfile,
) -> None:
    """
    Validate that uncertainty evidence is compatible with
    the actual 13-week cash evidence.

    No uncertainty relationship is inferred automatically.
    """
    active_modelled_events = [
        event
        for event in forecast_input.events
        if (
            event.status == "ACTIVE"
            and event.source_type == "MODELLED"
        )
    ]

    if (
        active_modelled_events
        and len(
            profile.modelled_flow_error_samples
        )
        < 3
    ):
        raise ValueError(
            "At least 3 paired modelled cash-error "
            "samples are required when active "
            "MODELLED cash events are present."
        )

    events_by_id = {
        event.event_id: event
        for event in forecast_input.events
    }

    seen_timing_event_ids: set[str] = set()

    for timing in (
        profile.committed_timing_uncertainty
    ):
        if (
            timing.event_id
            in seen_timing_event_ids
        ):
            raise ValueError(
                "Duplicate committed timing "
                "uncertainty event ID: "
                f"{timing.event_id}"
            )

        seen_timing_event_ids.add(
            timing.event_id
        )

        event = events_by_id.get(
            timing.event_id
        )

        if event is None:
            raise ValueError(
                "Committed timing uncertainty "
                "references unknown event ID: "
                f"{timing.event_id}"
            )

        if event.source_type != "COMMITTED":
            raise ValueError(
                "Committed timing uncertainty must "
                "reference a COMMITTED event."
            )

        if event.status != "ACTIVE":
            raise ValueError(
                "Committed timing uncertainty must "
                "reference an ACTIVE event."
            )
