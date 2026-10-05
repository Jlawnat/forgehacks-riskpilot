from __future__ import annotations

from datetime import datetime
from hashlib import sha256

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from src.core.command_center import (
    CommandCenterResult,
    build_command_center,
)
from src.core.direct_cash import DirectCashForecastInput
from src.demo.v2_scenarios import V2DemoScenario


class V2WhatIfRequest(BaseModel):
    """Strict, intentionally small V2 scenario overlay request."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    management_reserve: float | None = Field(
        default=None,
        ge=0.0,
        allow_inf_nan=False,
    )
    revenue_change_pct: float | None = Field(
        default=None,
        ge=-100.0,
        le=100.0,
        allow_inf_nan=False,
    )
    cost_change_pct: float | None = Field(
        default=None,
        ge=-100.0,
        le=100.0,
        allow_inf_nan=False,
    )
    receivable_delay_days: int | None = Field(
        default=None,
        ge=0,
    )

    @field_validator(
        "management_reserve",
        "revenue_change_pct",
        "cost_change_pct",
        "receivable_delay_days",
        mode="before",
    )
    @classmethod
    def _reject_boolean_numbers(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("what-if values must be numeric, not boolean.")
        return value

    @model_validator(mode="after")
    def _require_adjustment(self) -> "V2WhatIfRequest":
        if all(
            value is None
            for value in (
                self.management_reserve,
                self.revenue_change_pct,
                self.cost_change_pct,
                self.receivable_delay_days,
            )
        ):
            raise ValueError("At least one V2 what-if adjustment is required.")
        return self


class V2WhatIfResult(BaseModel):
    """Verified temporary scenario and its complete Command Center result."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=True,
    )

    baseline_scenario_id: str
    request: V2WhatIfRequest
    scenario: V2DemoScenario
    command_center: CommandCenterResult
    applied_changes: tuple[str, ...]


class UnsupportedV2WhatIfError(ValueError):
    """Raised when a valid request needs an unavailable V2 overlay."""


def _scaled_forecast_input(
    forecast_input: DirectCashForecastInput,
    request: V2WhatIfRequest,
) -> DirectCashForecastInput:
    revenue_factor = (
        None
        if request.revenue_change_pct is None
        else 1.0 + request.revenue_change_pct / 100.0
    )
    cost_factor = (
        None
        if request.cost_change_pct is None
        else 1.0 + request.cost_change_pct / 100.0
    )

    events = []
    for event in forecast_input.events:
        factor = None
        if (
            revenue_factor is not None
            and event.source_type == "MODELLED"
            and event.direction == "INFLOW"
            and event.category == "residual sales receipts"
        ):
            factor = revenue_factor
        elif (
            cost_factor is not None
            and event.source_type == "MODELLED"
            and event.direction == "OUTFLOW"
            and event.category == "variable operating costs"
        ):
            factor = cost_factor

        events.append(
            event
            if factor is None
            else event.__class__.model_validate(
                {
                    **event.model_dump(),
                    "amount": float(event.amount) * factor,
                }
            )
        )

    return DirectCashForecastInput.model_validate(
        {
            **forecast_input.model_dump(),
            "events": tuple(events),
        }
    )


def _temporary_identity(
    baseline: V2DemoScenario,
    request: V2WhatIfRequest,
) -> tuple[str, str]:
    canonical = request.model_dump_json(exclude_none=True)
    digest = sha256(canonical.encode("utf-8")).hexdigest()[:10]
    return (
        f"{baseline.scenario_id}-what-if-{digest}",
        f"{baseline.name} · AI what-if",
    )


def _change_summaries(request: V2WhatIfRequest) -> tuple[str, ...]:
    changes: list[str] = []
    if request.management_reserve is not None:
        changes.append(f"Management reserve ${request.management_reserve:,.0f}")
    if request.revenue_change_pct is not None:
        changes.append(f"Modelled revenue {request.revenue_change_pct:+.1f}%")
    if request.cost_change_pct is not None:
        changes.append(f"Modelled operating costs {request.cost_change_pct:+.1f}%")
    return tuple(changes)


def run_v2_what_if(
    baseline: V2DemoScenario,
    request: V2WhatIfRequest,
    *,
    created_at: datetime,
    simulations: int = 2000,
    seed: int = 42,
) -> V2WhatIfResult:
    """
    Apply an immutable V2 overlay and rerun the authoritative workflow.

    Timing shocks are deliberately unavailable until the direct-cash
    engine accepts a first-class timing overlay. Source evidence dates are
    never mutated to simulate timing.
    """
    if request.receivable_delay_days is not None:
        raise UnsupportedV2WhatIfError(
            "receivable_delay_days is not supported by the current V2 "
            "what-if engine because it has no first-class timing-overlay "
            "input; source cash-event dates remain unchanged."
        )

    scenario_id, name = _temporary_identity(baseline, request)
    temporary = V2DemoScenario.model_validate(
        {
            **baseline.model_dump(),
            "scenario_id": scenario_id,
            "name": name,
            "management_reserve": (
                baseline.management_reserve
                if request.management_reserve is None
                else request.management_reserve
            ),
            "forecast_input": _scaled_forecast_input(
                baseline.forecast_input,
                request,
            ),
        }
    )

    command_center = build_command_center(
        temporary,
        created_at=created_at,
        simulations=simulations,
        seed=seed,
    )
    return V2WhatIfResult(
        baseline_scenario_id=baseline.scenario_id,
        request=request,
        scenario=temporary,
        command_center=command_center,
        applied_changes=_change_summaries(request),
    )
