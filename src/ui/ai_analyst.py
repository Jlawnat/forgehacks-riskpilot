from __future__ import annotations

import pandas as pd
import streamlit as st

from src.ai.analyst import run_risk_analyst
from src.ai.context import RiskAnalystContext
from src.core.context import ForecastContext
from src.core.risk_policy import RiskPolicy


TOOL_LABELS = {
    "get_business_health": (
        "Business health",
        "Current metrics, deterministic risk ratings and risk policy.",
    ),
    "get_forecast_outlook": (
        "Forecast outlook",
        "Validated revenue and operating-cost forecasts.",
    ),
    "get_liquidity_risk": (
        "Liquidity simulation",
        "Monte Carlo reserve-breach and negative-cash risk.",
    ),
    "run_stress_test": (
        "Stress test",
        "Deterministic scenario outcome and driver decomposition.",
    ),
    "run_reverse_stress": (
        "Reverse stress",
        "Management-reserve survival thresholds.",
    ),
    "get_recovery_options": (
        "Recovery optimiser",
        "Deterministic operating and funding alternatives.",
    ),
    "validate_recovery_options": (
        "Recovery validation",
        "Monte Carlo validation against management risk appetite.",
    ),
}


SUGGESTED_QUESTIONS = (
    (
        "Top 3-month risks",
        (
            "What are the most important risks facing this business "
            "over the next three months? Explain the current position, "
            "forecast and liquidity risk."
        ),
    ),
    (
        "Reserve vs insolvency",
        (
            "Explain the difference between this business's "
            "reserve-breach risk and probability of negative cash."
        ),
    ),
    (
        "Survival boundary",
        (
            "How much further deterioration can the business withstand "
            "before breaching the management cash reserve?"
        ),
    ),
    (
        "Run severe stress",
        (
            "Stress revenue by -15%, costs by +10% and delay "
            "receivables by 30 days. What happens and what drives "
            "the liquidity impact?"
        ),
    ),
    (
        "Recommend recovery",
        (
            "Assume revenue falls 15%, operating costs rise 10%, "
            "and receivables are delayed by 30 days over the next "
            "three months. What should management do? Compare the "
            "main recovery options and tell me whether the balanced "
            "plan is adequate after uncertainty is considered."
        ),
    ),
)


def _analysis_signature(
    forecast_context: ForecastContext,
    policy: RiskPolicy,
) -> str:
    return "|".join(
        [
            forecast_context.dataset_fingerprint,
            str(forecast_context.horizon),
            f"{policy.minimum_cash_reserve:.6f}",
            f"{policy.max_shortfall_probability:.6f}",
        ]
    )


def _reset_stale_response(
    signature: str,
) -> None:
    previous = st.session_state.get(
        "riskpilot_ai_signature"
    )

    if previous == signature:
        return

    st.session_state[
        "riskpilot_ai_signature"
    ] = signature

    st.session_state.pop(
        "riskpilot_ai_answer",
        None,
    )
    st.session_state.pop(
        "riskpilot_ai_tools",
        None,
    )
    st.session_state.pop(
        "riskpilot_ai_asked_question",
        None,
    )


def _render_tool_trace(
    tools_used: tuple[str, ...],
    paired_residuals: int,
) -> None:
    if not tools_used:
        return

    st.markdown("#### Verified RiskPilot evidence")

    st.caption(
        "This trace comes directly from the Python agent runtime, "
        "not from the language model's written answer."
    )

    for index, tool_name in enumerate(
        tools_used,
        start=1,
    ):
        label, description = TOOL_LABELS.get(
            tool_name,
            (
                tool_name,
                "RiskPilot quantitative engine.",
            ),
        )

        st.markdown(
            f"**{index}. {label}**  \n"
            f"`{tool_name}` — {description}"
        )

    probabilistic_tools = {
        "get_liquidity_risk",
        "validate_recovery_options",
    }

    if (
        probabilistic_tools.intersection(
            tools_used
        )
        and paired_residuals < 30
    ):
        st.warning(
            "Probabilistic results currently use "
            f"{paired_residuals} paired historical forecast errors. "
            "Treat probabilities as decision-support estimates "
            "rather than production-grade certainty."
        )


def render_ai_risk_analyst(
    dataframe: pd.DataFrame,
    policy: RiskPolicy,
    forecast_context: ForecastContext,
    metrics,
    risks,
) -> None:
    st.subheader("AI Risk Analyst")

    st.markdown(
        """
        Ask management-level questions about the current business,
        forecasts, liquidity risk, stress scenarios, survival
        thresholds and recovery options.

        **RiskPilot's quantitative engines calculate the numbers.**
        The AI Analyst selects the appropriate engines and explains
        their verified outputs.
        """
    )

    signature = _analysis_signature(
        forecast_context,
        policy,
    )

    _reset_stale_response(
        signature
    )

    st.markdown("#### Suggested questions")

    first_row = st.columns(3)

    for column, (
        label,
        question,
    ) in zip(
        first_row,
        SUGGESTED_QUESTIONS[:3],
    ):
        with column:
            if st.button(
                label,
                use_container_width=True,
                key=f"ai_suggestion_{label}",
            ):
                st.session_state[
                    "riskpilot_ai_question"
                ] = question
                st.rerun()

    second_row = st.columns(2)

    for column, (
        label,
        question,
    ) in zip(
        second_row,
        SUGGESTED_QUESTIONS[3:],
    ):
        with column:
            if st.button(
                label,
                use_container_width=True,
                key=f"ai_suggestion_{label}",
            ):
                st.session_state[
                    "riskpilot_ai_question"
                ] = question
                st.rerun()

    question = st.text_area(
        "Ask RiskPilot",
        key="riskpilot_ai_question",
        height=120,
        placeholder=(
            "Example: How much deterioration can we withstand "
            "before breaching our cash reserve?"
        ),
    )

    ask_col, clear_col, _ = st.columns(
        [1, 1, 4]
    )

    with ask_col:
        ask_clicked = st.button(
            "Ask RiskPilot",
            type="primary",
            use_container_width=True,
        )

    with clear_col:
        clear_clicked = st.button(
            "Clear",
            use_container_width=True,
        )

    if clear_clicked:
        st.session_state[
            "riskpilot_ai_question"
        ] = ""

        st.session_state.pop(
            "riskpilot_ai_answer",
            None,
        )
        st.session_state.pop(
            "riskpilot_ai_tools",
            None,
        )
        st.session_state.pop(
            "riskpilot_ai_asked_question",
            None,
        )

        st.rerun()

    if ask_clicked:
        cleaned_question = question.strip()

        if not cleaned_question:
            st.warning(
                "Enter a question before asking RiskPilot."
            )
        else:
            analyst_context = RiskAnalystContext(
                dataframe=dataframe.copy(),
                policy=policy,
                forecast=forecast_context,
                metrics=metrics,
                risks=risks,
            )

            try:
                with st.spinner(
                    "RiskPilot is running the required "
                    "risk engines..."
                ):
                    response = run_risk_analyst(
                        analyst_context,
                        cleaned_question,
                    )

                st.session_state[
                    "riskpilot_ai_answer"
                ] = response.answer

                st.session_state[
                    "riskpilot_ai_tools"
                ] = response.tools_used

                st.session_state[
                    "riskpilot_ai_asked_question"
                ] = cleaned_question

            except Exception as exc:
                message = str(exc)

                if "api" in message.lower() or "key" in message.lower():
                    st.error(
                        "The AI Analyst could not connect to the "
                        "configured OpenAI API. Check the local "
                        "OPENAI_API_KEY setting and try again."
                    )
                else:
                    st.error(
                        "The AI Analyst could not complete this "
                        "request."
                    )

                with st.expander(
                    "Technical details"
                ):
                    st.code(
                        type(exc).__name__
                        + ": "
                        + message
                    )

    answer = st.session_state.get(
        "riskpilot_ai_answer"
    )

    tools_used = tuple(
        st.session_state.get(
            "riskpilot_ai_tools",
            (),
        )
    )

    asked_question = st.session_state.get(
        "riskpilot_ai_asked_question"
    )

    if answer:
        st.divider()

        if asked_question:
            st.caption(
                "Question: "
                + asked_question
            )

        st.markdown("### RiskPilot assessment")
        st.markdown(answer)

        _render_tool_trace(
            tools_used,
            paired_residuals=len(
                forecast_context.paired_residuals
            ),
        )

        st.caption(
            "AI explanations are grounded in RiskPilot's "
            "deterministic and probabilistic engines. "
            "Decision-support prototype only."
        )
