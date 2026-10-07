from __future__ import annotations

import streamlit as st

from src.ai.v2_context import (
    V2CopilotContext,
)
from src.ai.v2_copilot import (
    run_v2_copilot,
)
from src.core.liquidity_brief import (
    LiquidityDecisionBrief,
)
from src.core.v2_what_if import V2WhatIfResult
from src.demo.v2_scenarios import V2DemoScenario


V2_WHAT_IF_RESULT_KEY = "riskpilot_v2_what_if_result"
V2_WHAT_IF_BASELINE_KEY = "riskpilot_v2_what_if_baseline_id"


def _safe_ai_markdown(
    text: str,
) -> str:
    """
    Prevent currency dollar signs in model prose from being
    interpreted as Markdown/LaTeX delimiters by Streamlit.
    """
    return text.replace(
        "$",
        r"\$",
    )


class V2CopilotExecutionResult:
    def __init__(
        self,
        *,
        succeeded: bool,
        answer: str | None = None,
        tools_used: tuple[str, ...] = (),
        error_kind: str | None = None,
        technical_details: str | None = None,
        what_if_result: V2WhatIfResult | None = None,
    ) -> None:
        self.succeeded = succeeded
        self.answer = answer
        self.tools_used = tools_used
        self.error_kind = error_kind
        self.technical_details = technical_details
        self.what_if_result = what_if_result


def classify_v2_copilot_error(
    exc: Exception,
) -> str:
    message = str(exc).lower()

    auth_markers = (
        "openai_api_key",
        "api key",
        "invalid key",
        "authentication",
        "unauthorized",
        "forbidden",
        "401",
        "403",
    )

    if any(
        marker in message
        for marker in auth_markers
    ):
        return "CONFIGURATION_OR_AUTH"

    if (
        "timeout" in message
        or "timed out" in message
    ):
        return "TIMEOUT"

    return "RUNTIME_ERROR"


def execute_v2_copilot_request(
    brief: LiquidityDecisionBrief,
    question: str,
    *,
    baseline_scenario: V2DemoScenario | None = None,
    runner=run_v2_copilot,
) -> V2CopilotExecutionResult:
    """
    Execute the optional AI layer without allowing model/runtime
    failure to escape into the deterministic Command Center.
    """

    cleaned = question.strip()

    if not cleaned:
        return V2CopilotExecutionResult(
            succeeded=False,
            error_kind="EMPTY_QUESTION",
        )

    context = V2CopilotContext(
        liquidity_brief=brief,
        baseline_scenario=baseline_scenario,
        what_if_created_at=brief.created_at,
        what_if_simulations=(
            brief.uncertainty.simulations
            if brief.uncertainty is not None
            else 2000
        ),
    )

    try:
        response = runner(
            context,
            cleaned,
        )

        answer = (
            response.answer.strip()
            if response.answer
            else ""
        )

        if not answer:
            return V2CopilotExecutionResult(
                succeeded=False,
                error_kind="EMPTY_RESPONSE",
            )

        return V2CopilotExecutionResult(
            succeeded=True,
            answer=answer,
            tools_used=response.tools_used,
            what_if_result=context.what_if_result,
        )

    except Exception as exc:
        return V2CopilotExecutionResult(
            succeeded=False,
            error_kind=(
                classify_v2_copilot_error(
                    exc
                )
            ),
            technical_details=(
                type(exc).__name__
                + ": "
                + str(exc)
            ),
        )


def suggested_questions_for_brief(
    brief: LiquidityDecisionBrief,
) -> tuple[
    tuple[str, str],
    ...,
]:
    """
    Return management questions that match the current
    V2 liquidity state.

    Questions contain no hard-coded financial conclusions.
    """

    position = brief.position
    uncertainty = brief.uncertainty

    deterministic_breach = (
        position.first_reserve_breach_week
        is not None
    )

    probabilistic_risk_above_appetite = (
        uncertainty is not None
        and not uncertainty.within_risk_appetite
    )

    if deterministic_breach:
        return (
            (
                "What should we do first?",
                (
                    "What should management do first to address "
                    "the projected liquidity problem?"
                ),
            ),
            (
                "Is recovery adequate?",
                (
                    "Is the current recovery plan actually adequate "
                    "after uncertainty is considered?"
                ),
            ),
            (
                "What supports this?",
                (
                    "What evidence supports the recommended "
                    "management action?"
                ),
            ),
        )

    if probabilistic_risk_above_appetite:
        return (
            (
                "Why is risk high?",
                (
                    "Why is liquidity risk high even though the "
                    "deterministic forecast does not breach the "
                    "management reserve?"
                ),
            ),
            (
                "How much buffer?",
                (
                    "How much liquidity buffer does RiskPilot "
                    "indicate is needed, and why?"
                ),
            ),
            (
                "What supports this?",
                (
                    "What evidence supports the liquidity "
                    "recommendation?"
                ),
            ),
        )

    return (
        (
            "Do we need to act?",
            (
                "Do we need to take immediate liquidity action, "
                "or is continued monitoring appropriate?"
            ),
        ),
        (
            "Why is this healthy?",
            (
                "Why does RiskPilot consider the current liquidity "
                "position acceptable?"
            ),
        ),
        (
            "What should we monitor?",
            (
                "What should management continue monitoring over "
                "the 13-week forecast horizon?"
            ),
        ),
    )


def _copilot_signature(
    brief: LiquidityDecisionBrief,
) -> str:
    return "|".join(
        [
            brief.brief_id,
            brief.created_at.isoformat(),
        ]
    )


def reset_copilot_state_for_signature(
    state,
    signature: str,
) -> bool:
    """
    Reset scenario-specific Copilot state when the authoritative
    V2 brief changes.

    Returns True when stale state was cleared and False when the
    current state already belongs to the supplied brief.
    """

    previous = state.get(
        "riskpilot_v2_ai_signature"
    )

    if previous == signature:
        return False

    state[
        "riskpilot_v2_ai_signature"
    ] = signature

    state[
        "riskpilot_v2_ai_question"
    ] = ""

    state.pop(
        "riskpilot_v2_ai_answer",
        None,
    )
    state.pop(
        "riskpilot_v2_ai_tools",
        None,
    )
    state.pop(
        "riskpilot_v2_ai_asked_question",
        None,
    )

    return True


def clear_v2_copilot_answer_state(state) -> None:
    """Clear all answer/provenance state without touching other UI state."""
    state["riskpilot_v2_ai_question"] = ""
    for key in (
        "riskpilot_v2_ai_answer",
        "riskpilot_v2_ai_tools",
        "riskpilot_v2_ai_asked_question",
        "riskpilot_v2_ai_signature",
    ):
        state.pop(key, None)


def sync_v2_what_if_state(state, baseline_scenario_id: str) -> bool:
    """Invalidate temporary analysis and AI state on baseline changes."""
    previous = state.get(V2_WHAT_IF_BASELINE_KEY)
    if previous == baseline_scenario_id:
        return False

    state[V2_WHAT_IF_BASELINE_KEY] = baseline_scenario_id
    state.pop(V2_WHAT_IF_RESULT_KEY, None)
    clear_v2_copilot_answer_state(state)
    return True


def reset_v2_what_if_state(state, baseline_scenario_id: str) -> None:
    """Restore the selected immutable baseline and clear stale AI state."""
    state[V2_WHAT_IF_BASELINE_KEY] = baseline_scenario_id
    state.pop(V2_WHAT_IF_RESULT_KEY, None)
    clear_v2_copilot_answer_state(state)


def _reset_stale_copilot(
    brief: LiquidityDecisionBrief,
) -> None:
    reset_copilot_state_for_signature(
        st.session_state,
        _copilot_signature(
            brief
        ),
    )


def evidence_items_for_tools(
    tools_used: tuple[str, ...],
    brief: LiquidityDecisionBrief,
    *,
    is_temporary_what_if: bool = False,
) -> tuple[str, ...]:
    """
    Translate actual runtime tool calls into human-readable
    evidence provenance.
    """

    used = set(tools_used)
    items: list[str] = []

    if "get_v2_liquidity_position" in used:
        items.append(
            "13-week direct cash forecast"
        )

        if brief.uncertainty is not None:
            uncertainty_label = (
                "What-if uncertainty simulation"
                if is_temporary_what_if
                else "Baseline uncertainty simulation"
            )
            items.append(
                f"{uncertainty_label} "
                f"({brief.uncertainty.simulations:,} paths)"
            )
            items.append(
                "Management reserve and risk appetite"
            )

    if "get_v2_cash_evidence" in used:
        items.append(
            "Forecast evidence coverage"
        )

        if brief.cash_drivers:
            items.append(
                "Ranked cash drivers"
            )

    if "get_v2_recovery_evidence" in used:
        if brief.recovery is None:
            items.append(
                "Recovery evidence checked "
                "(no active recovery plan)"
            )
        else:
            items.append(
                "Recovery evaluation and probabilistic validation"
            )

    if "get_v2_actions_monitoring" in used:
        if brief.actions.total_actions > 0:
            items.append(
                "Cash Action Register"
            )
        else:
            items.append(
                "Cash Action Register checked "
                "(no active actions)"
            )

        if brief.monitoring is not None:
            items.append(
                "Monitoring triggers"
            )

    if "run_v2_what_if_scenario" in used:
        items.append(
            "Verified V2 what-if engine (temporary analysis)"
        )

    return tuple(items)


def _render_evidence_used(
    tools_used: tuple[str, ...],
    brief: LiquidityDecisionBrief,
    *,
    is_temporary_what_if: bool = False,
) -> None:
    items = evidence_items_for_tools(
        tools_used,
        brief,
    )

    if not items:
        return

    evidence_label = (
        "Verified evidence · Temporary what-if"
        if is_temporary_what_if
        else "Verified evidence"
    )

    with st.expander(
        evidence_label,
        expanded=False,
    ):
        st.caption(
            "Verified provenance from RiskPilot's agent runtime. "
            "This shows the financial evidence used by the answer, "
            "not private model reasoning."
        )

        for item in items:
            st.markdown(
                f"✓ **{item}**"
            )



def render_v2_copilot(
    brief: LiquidityDecisionBrief,
    *,
    baseline_scenario: V2DemoScenario | None = None,
    is_temporary_what_if: bool = False,
) -> None:
    """
    Render the V2 RiskPilot AI Decision Copilot.

    Financial values come exclusively from the supplied
    Liquidity Decision Brief.
    """

    _reset_stale_copilot(
        brief
    )

    st.markdown(
        '<div class="rp-section-label">'
        'AI decision support'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="rp-ai-heading">
            <div class="rp-ai-title">
                RiskPilot AI
                <span class="rp-ai-verified">
                    VERIFIED DECISION SUPPORT
                </span>
            </div>
            <div class="rp-ai-subtitle">
                Ask about liquidity, risk, recovery or a temporary
                what-if. Financial engines calculate; AI interprets
                verified evidence.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


    st.caption(
        "Grounded only in the current V2 13-week "
        "Liquidity Decision Brief."
    )

    suggestions = (
        suggested_questions_for_brief(
            brief
        )
    )

    columns = st.columns(
        len(suggestions)
    )

    for column, (
        label,
        question,
    ) in zip(
        columns,
        suggestions,
    ):
        with column:
            if st.button(
                label,
                use_container_width=True,
                key=(
                    "v2_ai_suggestion_"
                    + brief.brief_id
                    + "_"
                    + label
                ),
            ):
                st.session_state[
                    "riskpilot_v2_ai_question"
                ] = question
                st.rerun()

    question = st.text_input(
        "Ask RiskPilot",
        key="riskpilot_v2_ai_question",
        placeholder=(
            "Ask about liquidity risk, cash drivers, recovery, "
            "evidence or what management should do next..."
        ),
    )

    ask_col, _ = st.columns(
        [1, 5]
    )

    with ask_col:
        ask_clicked = st.button(
            "Ask RiskPilot",
            type="primary",
            use_container_width=True,
        )

    if ask_clicked:
        cleaned_question = (
            question.strip()
        )

        if not cleaned_question:
            st.warning(
                "Enter a question before asking RiskPilot."
            )

        else:
            with st.spinner(
                "RiskPilot is reviewing the "
                "verified liquidity evidence..."
            ):
                execution = execute_v2_copilot_request(
                    brief,
                    cleaned_question,
                    baseline_scenario=baseline_scenario,
                )

            if execution.succeeded:
                st.session_state[
                    "riskpilot_v2_ai_answer"
                ] = execution.answer

                st.session_state[
                    "riskpilot_v2_ai_tools"
                ] = execution.tools_used

                st.session_state[
                    "riskpilot_v2_ai_asked_question"
                ] = cleaned_question

                if execution.what_if_result is not None:
                    outcome = execution.what_if_result
                    st.session_state[V2_WHAT_IF_RESULT_KEY] = outcome
                    st.session_state[V2_WHAT_IF_BASELINE_KEY] = (
                        outcome.baseline_scenario_id
                    )
                    st.session_state["riskpilot_v2_ai_signature"] = (
                        _copilot_signature(outcome.command_center.brief)
                    )
                    st.rerun()

            else:
                # Never leave an older AI answer visible after
                # a newer request fails.
                st.session_state.pop(
                    "riskpilot_v2_ai_answer",
                    None,
                )
                st.session_state.pop(
                    "riskpilot_v2_ai_tools",
                    None,
                )
                st.session_state.pop(
                    "riskpilot_v2_ai_asked_question",
                    None,
                )

                if (
                    execution.error_kind
                    == "CONFIGURATION_OR_AUTH"
                ):
                    st.error(
                        "RiskPilot AI could not connect to the "
                        "configured model. Check the local "
                        "OPENAI_API_KEY setting and try again."
                    )

                elif (
                    execution.error_kind
                    == "TIMEOUT"
                ):
                    st.error(
                        "RiskPilot AI took too long to respond. "
                        "The verified financial results remain "
                        "available; try the question again."
                    )

                elif (
                    execution.error_kind
                    == "EMPTY_RESPONSE"
                ):
                    st.error(
                        "RiskPilot AI returned no usable answer. "
                        "The verified financial results remain "
                        "available."
                    )

                else:
                    st.error(
                        "RiskPilot AI could not complete this "
                        "request. The verified financial results "
                        "above remain available."
                    )

                if execution.technical_details:
                    with st.expander(
                        "Technical details"
                    ):
                        st.code(
                            execution.technical_details
                        )

    answer = st.session_state.get(
        "riskpilot_v2_ai_answer"
    )

    tools_used = tuple(
        st.session_state.get(
            "riskpilot_v2_ai_tools",
            (),
        )
    )

    asked_question = (
        st.session_state.get(
            "riskpilot_v2_ai_asked_question"
        )
    )

    if answer:
        st.markdown(
            "### RiskPilot response"
        )

        if asked_question:
            st.caption(
                "Question: "
                + asked_question
            )

        st.markdown(
            _safe_ai_markdown(
                answer
            )
        )

        _render_evidence_used(
            tools_used,
            brief,
            is_temporary_what_if=is_temporary_what_if,
        )
