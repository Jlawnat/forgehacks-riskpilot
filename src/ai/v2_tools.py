from __future__ import annotations

import json
from typing import Any

from agents import RunContextWrapper
from agents.decorators import tool

from src.ai.v2_context import (
    V2CopilotContext,
)


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

    return {
        "available": True,
        "scope": "RECOVERY",
        "recovery": (
            None
            if brief.recovery is None
            else brief.recovery.model_dump(
                mode="json"
            )
        ),
        "limitations": brief.limitations,
        "grounding_notes": {
            "recovery": (
                "Deterministic feasibility and probabilistic "
                "adequacy are separate recovery conclusions."
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
