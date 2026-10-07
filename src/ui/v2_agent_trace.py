from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from src.core.liquidity_brief import (
    LiquidityDecisionBrief,
)


@dataclass(frozen=True)
class AgentToolDisplay:
    label: str
    description: str
    engine: str


_TOOL_DISPLAY = {
    "run_v2_what_if_scenario": AgentToolDisplay(
        label="Scenario orchestration",
        description=(
            "Applied supported management assumptions "
            "through the verified V2 what-if engine."
        ),
        engine="V2 What-if Engine",
    ),
    "get_v2_liquidity_position": AgentToolDisplay(
        label="Liquidity position",
        description=(
            "Retrieved deterministic cash position, "
            "reserve headroom and baseline liquidity risk."
        ),
        engine="13-week Liquidity Engine",
    ),
    "get_v2_cash_evidence": AgentToolDisplay(
        label="Cash evidence",
        description=(
            "Retrieved evidence coverage and ranked "
            "cash-flow drivers."
        ),
        engine="Evidence Engine",
    ),
    "get_v2_recovery_evidence": AgentToolDisplay(
        label="Recovery validation",
        description=(
            "Retrieved deterministic recovery feasibility "
            "and probabilistic recovery validation."
        ),
        engine="Recovery Engine",
    ),
    "get_v2_actions_monitoring": AgentToolDisplay(
        label="Actions & monitoring",
        description=(
            "Retrieved management actions and active "
            "monitoring triggers."
        ),
        engine="Action & Monitoring Engine",
    ),
}


def agent_tool_display(
    tool_name: str,
) -> AgentToolDisplay:
    return _TOOL_DISPLAY.get(
        tool_name,
        AgentToolDisplay(
            label=tool_name.replace(
                "_",
                " ",
            ).title(),
            description=(
                "Verified RiskPilot tool used by "
                "the AI Decision Agent."
            ),
            engine="RiskPilot verified tool",
        ),
    )


def build_agent_execution_steps(
    tools_used: tuple[str, ...],
    *,
    has_what_if: bool,
) -> tuple[
    tuple[str, str, str],
    ...,
]:
    """
    Human-facing execution trace.

    This is deliberately not chain-of-thought. It exposes only
    observable application actions and verified tool provenance.
    """
    steps: list[
        tuple[str, str, str]
    ] = [
        (
            "01",
            "Interpret management request",
            (
                "RiskPilot identifies the decision being asked "
                "without calculating replacement financial values."
            ),
        ),
    ]

    seen: set[str] = set()

    for tool_name in tools_used:
        if tool_name in seen:
            continue

        seen.add(
            tool_name
        )

        display = agent_tool_display(
            tool_name
        )

        steps.append(
            (
                f"{len(steps) + 1:02d}",
                display.label,
                (
                    f"{display.engine} · "
                    f"{display.description}"
                ),
            )
        )

    if has_what_if:
        steps.append(
            (
                f"{len(steps) + 1:02d}",
                "Preserve baseline",
                (
                    "Temporary scenario results remain isolated; "
                    "the selected baseline is not overwritten."
                ),
            )
        )

    steps.append(
        (
            f"{len(steps) + 1:02d}",
            "Ground recommendation",
            (
                "The response is constrained to verified engine "
                "evidence returned during this run."
            ),
        )
    )

    return tuple(
        steps
    )


def render_agent_execution_trace(
    tools_used: tuple[str, ...],
    brief: LiquidityDecisionBrief,
    *,
    has_what_if: bool = False,
) -> None:
    if not tools_used:
        return

    st.markdown(
        """
        <style>
        .rp-agent-shell {
            margin: 0.75rem 0 0.85rem 0;
            border: 1px solid #dbe4f0;
            border-radius: 12px;
            overflow: hidden;
            background: #ffffff;
        }

        .rp-agent-head {
            padding: 0.78rem 0.9rem;
            background:
                linear-gradient(
                    135deg,
                    #0b1739 0%,
                    #102556 100%
                );
        }

        .rp-agent-kicker {
            color: #93c5fd;
            font-size: 0.60rem;
            font-weight: 800;
            letter-spacing: 0.105em;
            text-transform: uppercase;
        }

        .rp-agent-title {
            margin-top: 0.18rem;
            color: #ffffff;
            font-size: 0.93rem;
            font-weight: 720;
        }

        .rp-agent-subtitle {
            margin-top: 0.15rem;
            color: #cbd5e1;
            font-size: 0.70rem;
            line-height: 1.4;
        }

        .rp-agent-step {
            display: grid;
            grid-template-columns: 34px 1fr 86px;
            gap: 0.65rem;
            align-items: center;
            padding: 0.66rem 0.82rem;
            border-top: 1px solid #edf2f7;
        }

        .rp-agent-number {
            color: #2563eb;
            font-size: 0.67rem;
            font-weight: 800;
        }

        .rp-agent-step-title {
            color: #0f172a;
            font-size: 0.76rem;
            font-weight: 700;
        }

        .rp-agent-step-copy {
            margin-top: 0.08rem;
            color: #64748b;
            font-size: 0.65rem;
            line-height: 1.38;
        }

        .rp-agent-done {
            justify-self: end;
            padding: 0.18rem 0.40rem;
            border-radius: 999px;
            background: #ecfdf5;
            border: 1px solid #a7f3d0;
            color: #047857;
            font-size: 0.56rem;
            font-weight: 800;
            letter-spacing: 0.04em;
        }

        .rp-agent-lock {
            padding: 0.60rem 0.82rem;
            border-top: 1px solid #dbeafe;
            background: #f8fbff;
            color: #475569;
            font-size: 0.65rem;
            line-height: 1.4;
        }

        .rp-agent-lock strong {
            color: #1d4ed8;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    steps = build_agent_execution_steps(
        tools_used,
        has_what_if=has_what_if,
    )

    html = (
        '<div class="rp-agent-shell">'
        '<div class="rp-agent-head">'
        '<div class="rp-agent-kicker">'
        'AGENT EXECUTION'
        '</div>'
        '<div class="rp-agent-title">'
        'Verified decision orchestration'
        '</div>'
        '<div class="rp-agent-subtitle">'
        'Observable runtime actions only — '
        'not private model reasoning.'
        '</div>'
        '</div>'
    )

    for number, title, copy in steps:
        html += (
            '<div class="rp-agent-step">'
            f'<div class="rp-agent-number">{number}</div>'
            '<div>'
            f'<div class="rp-agent-step-title">{title}</div>'
            f'<div class="rp-agent-step-copy">{copy}</div>'
            '</div>'
            '<div class="rp-agent-done">VERIFIED</div>'
            '</div>'
        )

    html += (
        '<div class="rp-agent-lock">'
        '<strong>Financial-value lock:</strong> '
        'the AI may interpret and orchestrate, but '
        'forecast, probability and recovery values '
        'come from RiskPilot engines.'
        '</div>'
        '</div>'
    )

    st.markdown(
        html,
        unsafe_allow_html=True,
    )

    if (
        brief.uncertainty
        is not None
    ):
        st.caption(
            "Runtime evidence remains tied to the current "
            f"{brief.uncertainty.simulations:,}-path "
            "verified liquidity analysis."
        )
