from __future__ import annotations

import json
from typing import Any

from agents import RunContextWrapper
from agents.decorators import tool

from src.ai.v2_context import (
    V2CopilotContext,
)
from src.core.v2_what_if import (
    UnsupportedV2WhatIfError,
    V2WhatIfRequest,
    run_v2_what_if,
)
from src.core.v2_display import format_probability


def _unavailable() -> dict[str, Any]:
    return {
        "available": False,
        "reason": (
            "No V2 Liquidity Decision Brief is available "
            "for the current business context."
        ),
    }


def _json(
    payload: dict[str, Any],
) -> str:
    return json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    )


def run_v2_what_if_snapshot(
    context: V2CopilotContext,
    request: V2WhatIfRequest,
) -> dict[str, Any]:
    """Run the verified V2 adapter and update this runtime's evidence."""
    if context.baseline_scenario is None:
        return {
            "available": False,
            "supported": False,
            "reason": "No baseline V2 scenario is available for what-if analysis.",
        }

    try:
        outcome = run_v2_what_if(
            context.baseline_scenario,
            request,
            created_at=context.what_if_created_at,
            simulations=context.what_if_simulations,
            seed=context.what_if_seed,
        )
    except UnsupportedV2WhatIfError as exc:
        return {
            "available": False,
            "supported": False,
            "reason": str(exc),
            "baseline_unchanged": True,
        }

    context.what_if_request = request
    context.what_if_result = outcome
    context.liquidity_brief = outcome.command_center.brief

    verified_brief = outcome.command_center.brief.model_dump(mode="json")
    recovery_evidence = v2_recovery_evidence_snapshot(context)
    verified_brief["recovery"] = recovery_evidence["recovery"]

    return {
        "available": True,
        "supported": True,
        "engine": "RiskPilot V2 what-if engine",
        "temporary": True,
        "baseline_scenario_id": outcome.baseline_scenario_id,
        "baseline_unchanged": True,
        "applied_changes": outcome.applied_changes,
        "canonical_display_values": {
            "scenario_breach_probability": format_probability(
                outcome.command_center.simulation.shortfall_probability
            ),
            "management_risk_appetite": format_probability(
                outcome.scenario.max_reserve_breach_probability
            ),
        },
        "verified_brief": verified_brief,
        "grounding_note": (
            "Quote canonical_display_values exactly when presenting those "
            "percentages. Do not independently round the raw probability. "
            "Use only the verified brief values. Do not calculate, estimate, "
            "interpolate or invent replacement financial values. Current-plan "
            "recovery outcomes and conditional additional-buffer outcomes are "
            "separate. In temporary analysis, describe pre-recovery probability "
            "as what-if or scenario breach risk, not baseline breach risk."
        ),
    }


@tool
def run_v2_what_if_scenario(
    ctx: RunContextWrapper[V2CopilotContext],
    management_reserve: float | None = None,
    revenue_change_pct: float | None = None,
    cost_change_pct: float | None = None,
    receivable_delay_days: int | None = None,
) -> str:
    """
    Run a temporary, engine-verified V2 what-if scenario.

    Use this tool for hypothetical changes to management reserve,
    modelled residual-sales revenue, modelled variable operating costs,
    or receivable timing. The current engine returns a structured
    unsupported response for receivable-delay requests. Never calculate a
    hypothetical financial result yourself.
    """
    ctx.context.record_tool("run_v2_what_if_scenario")
    request = V2WhatIfRequest(
        management_reserve=management_reserve,
        revenue_change_pct=revenue_change_pct,
        cost_change_pct=cost_change_pct,
        receivable_delay_days=receivable_delay_days,
    )
    return _json(run_v2_what_if_snapshot(ctx.context, request))


def v2_liquidity_decision_brief_snapshot(
    context: V2CopilotContext,
) -> dict[str, Any]:
    """
    Full V2 brief snapshot retained as an offline compatibility
    helper. The live Copilot does not receive this broad snapshot.
    """

    brief = context.liquidity_brief

    if brief is None:
        return _unavailable()

    return {
        "available": True,
        "brief": brief.model_dump(
            mode="json"
        ),
        "grounding_notes": {
            "financial_values": (
                "Treat supplied financial values as authoritative. "
                "Do not recalculate, estimate or invent replacements."
            ),
            "forecast": (
                "The position is a 13-week direct-cash forecast. "
                "Do not combine it with legacy monthly forecasts."
            ),
            "baseline_uncertainty": (
                "Baseline uncertainty is pre-recovery probabilistic "
                "liquidity risk. Do not confuse it with post-recovery "
                "validation."
            ),
            "evidence_coverage": (
                "Evidence coverage is an evidence-quality metric, "
                "not a probability or confidence score."
            ),
            "recovery": (
                "Deterministic recovery feasibility and probabilistic "
                "recovery adequacy are separate conclusions."
            ),
            "actions": (
                "Expected cash impact is not realised cash benefit."
            ),
        },
    }


def v2_liquidity_position_snapshot(
    context: V2CopilotContext,
) -> dict[str, Any]:
    """
    Management-facing deterministic position plus headline
    baseline uncertainty evidence.
    """

    brief = context.liquidity_brief

    if brief is None:
        return _unavailable()

    position = brief.position
    uncertainty = brief.uncertainty

    return {
        "available": True,
        "scope": "LIQUIDITY_POSITION",
        "scenario_name": brief.scenario_name,
        "forecast_start_date": (
            brief.forecast_start_date.isoformat()
        ),
        "position": {
            "current_cash":
                position.current_cash,
            "management_reserve":
                position.management_reserve,
            "minimum_closing_cash":
                position.minimum_closing_cash,
            "minimum_closing_cash_week":
                position.minimum_closing_cash_week,
            "minimum_headroom":
                position.minimum_headroom,
            "minimum_headroom_week":
                position.minimum_headroom_week,
            "first_reserve_breach_week":
                position.first_reserve_breach_week,
            "closing_cash_13_week":
                position.closing_cash_13_week,
        },
        "baseline_uncertainty": (
            None
            if uncertainty is None
            else {
                "simulations":
                    uncertainty.simulations,
                "confidence_level":
                    uncertainty.confidence_level,
                "reserve_breach_probability":
                    uncertainty
                    .reserve_breach_probability,
                "maximum_acceptable_breach_probability":
                    uncertainty
                    .maximum_acceptable_breach_probability,
                "within_risk_appetite":
                    uncertainty
                    .within_risk_appetite,
                "liquidity_buffer_at_confidence":
                    uncertainty
                    .liquidity_buffer_at_confidence,
                "expected_tail_buffer":
                    uncertainty
                    .expected_tail_buffer,
                "limitations":
                    uncertainty.limitations,
            }
        ),
        "grounding_notes": {
            "baseline_vs_recovery": (
                "These probability values describe baseline risk "
                "before recovery actions."
            ),
            "language": (
                "Describe whether the deterministic cash path "
                "breaches reserve and whether baseline probability "
                "is within management appetite."
            ),
        },
    }


def v2_cash_evidence_snapshot(
    context: V2CopilotContext,
) -> dict[str, Any]:
    """
    Evidence quality and ranked deterministic cash drivers.
    """

    brief = context.liquidity_brief

    if brief is None:
        return _unavailable()

    position = brief.position

    return {
        "available": True,
        "scope": "CASH_EVIDENCE",
        "evidence_quality": {
            "committed_evidence_amount":
                position.committed_evidence_amount,
            "modelled_residual_amount":
                position.modelled_residual_amount,
            "management_assumption_amount":
                position.management_assumption_amount,
            "evidence_coverage_ratio":
                position.evidence_coverage_ratio,
        },
        "cash_drivers": [
            driver.model_dump(
                mode="json"
            )
            for driver in brief.cash_drivers
        ],
        "grounding_notes": {
            "evidence_coverage": (
                "Evidence coverage is not a probability or "
                "confidence score."
            ),
            "drivers": (
                "Cash-driver values are already calculated. "
                "Do not recompute or aggregate new financial values."
            ),
        },
    }


def v2_recovery_evidence_snapshot(
    context: V2CopilotContext,
) -> dict[str, Any]:
    """
    Recovery-plan feasibility and probabilistic validation only.
    """

    brief = context.liquidity_brief

    if brief is None:
        return _unavailable()

    recovery = brief.recovery

    if recovery is None:
        recovery_evidence = None
    else:
        recovery_evidence = {
            "current_recovery_plan": {
                "revenue_improvement_pct":
                    recovery.revenue_improvement_pct,
                "cost_reduction_pct":
                    recovery.cost_reduction_pct,
                "receivable_acceleration_days":
                    recovery.receivable_acceleration_days,
                "external_liquidity":
                    recovery.external_liquidity,
                "deterministic_feasible":
                    recovery.deterministic_feasible,
                "resulting_min_cash":
                    recovery.resulting_min_cash,
                "resulting_min_cash_week":
                    recovery.resulting_min_cash_week,
                "remaining_reserve_gap":
                    recovery.remaining_reserve_gap,
                "reserve_breach_probability":
                    recovery.reserve_breach_probability,
                "maximum_acceptable_breach_probability":
                    recovery.maximum_acceptable_breach_probability,
                "within_risk_appetite":
                    recovery.within_risk_appetite,
                "probabilistic_validation_status":
                    recovery.probabilistic_validation_status,
            },
            "additional_liquidity_requirement": {
                "additional_upfront_buffer_at_confidence":
                    recovery.additional_upfront_buffer_at_confidence,
                "breach_probability_with_additional_buffer":
                    recovery.risk_adjusted_breach_probability,
                "within_risk_appetite_with_additional_buffer":
                    recovery.risk_adjusted_within_risk_appetite,
                "dependency": (
                    "These risk-adjusted values apply only if the "
                    "additional upfront liquidity buffer is provided. "
                    "They are not the outcome of the current recovery plan."
                ),
            },
        }

    return {
        "available": True,
        "scope": "RECOVERY",
        "recovery": recovery_evidence,
        "limitations": brief.limitations,
        "grounding_notes": {
            "recovery": (
                "Deterministic feasibility and probabilistic adequacy are "
                "separate current-plan conclusions."
            ),
            "current_plan": (
                "Lead with the current recovery-plan outcome. If it is "
                "deterministically infeasible and its reserve-breach "
                "probability exceeds appetite, state that the current "
                "recovery plan remains inadequate."
            ),
            "additional_liquidity": (
                "risk_adjusted_breach_probability is conditional on adding "
                "additional_upfront_buffer_at_confidence. Never describe it "
                "as the current recovery plan succeeding or being within "
                "appetite."
            ),
            "baseline": (
                "Do not treat post-recovery probability as the "
                "baseline reserve-breach probability."
            ),
        },
    }


def v2_actions_monitoring_snapshot(
    context: V2CopilotContext,
) -> dict[str, Any]:
    """
    Management actions and monitoring triggers only.
    """

    brief = context.liquidity_brief

    if brief is None:
        return _unavailable()

    return {
        "available": True,
        "scope": "ACTIONS_MONITORING",
        "actions": brief.actions.model_dump(
            mode="json"
        ),
        "monitoring": (
            None
            if brief.monitoring is None
            else brief.monitoring.model_dump(
                mode="json"
            )
        ),
        "grounding_notes": {
            "actions": (
                "Expected cash impact is not realised benefit "
                "unless evidence-backed realised benefit is reported."
            ),
        },
    }


@tool
def get_v2_liquidity_position(
    ctx: RunContextWrapper[
        V2CopilotContext
    ],
) -> str:
    """
    Retrieve the V2 deterministic liquidity position and headline
    baseline uncertainty evidence.

    Use for reserve/headroom, deterministic breach timing,
    baseline reserve-breach probability, risk appetite and
    liquidity-buffer questions.
    """

    ctx.context.record_tool(
        "get_v2_liquidity_position"
    )

    return _json(
        v2_liquidity_position_snapshot(
            ctx.context
        )
    )


@tool
def get_v2_cash_evidence(
    ctx: RunContextWrapper[
        V2CopilotContext
    ],
) -> str:
    """
    Retrieve V2 forecast evidence quality and ranked cash drivers.

    Use for evidence coverage, committed versus modelled evidence,
    or questions about what cash flows drive the forecast.
    """

    ctx.context.record_tool(
        "get_v2_cash_evidence"
    )

    return _json(
        v2_cash_evidence_snapshot(
            ctx.context
        )
    )


@tool
def get_v2_recovery_evidence(
    ctx: RunContextWrapper[
        V2CopilotContext
    ],
) -> str:
    """
    Retrieve V2 recovery-plan evidence and probabilistic recovery
    validation.

    Use when the user asks whether the recovery plan is feasible,
    adequate, sufficient, or how it changes liquidity risk.
    """

    ctx.context.record_tool(
        "get_v2_recovery_evidence"
    )

    return _json(
        v2_recovery_evidence_snapshot(
            ctx.context
        )
    )


@tool
def get_v2_actions_monitoring(
    ctx: RunContextWrapper[
        V2CopilotContext
    ],
) -> str:
    """
    Retrieve V2 management actions and monitoring triggers.

    Use when the user asks what management should do, what action
    is due, or what should be monitored.
    """

    ctx.context.record_tool(
        "get_v2_actions_monitoring"
    )

    return _json(
        v2_actions_monitoring_snapshot(
            ctx.context
        )
    )
