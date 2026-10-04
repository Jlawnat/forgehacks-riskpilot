from __future__ import annotations

from dataclasses import dataclass
import os

from dotenv import load_dotenv

from agents import Agent, Runner

from src.ai.context import (
    RiskAnalystContext,
)
from src.ai.tools import (
    get_business_health,
    get_forecast_outlook,
    get_liquidity_risk,
    run_reverse_stress,
    run_stress_test,
)


@dataclass(frozen=True)
class RiskAnalystResponse:
    answer: str
    tools_used: tuple[str, ...]


INSTRUCTIONS = """
You are RiskPilot's AI Risk Analyst.

Your role is to explain and synthesize outputs from RiskPilot's
verified quantitative engines.

STRICT GROUNDING RULES

1. For any claim about this business's financial values, forecasts,
   probabilities, risk levels, scenario results or thresholds, use
   the appropriate RiskPilot tool first.

2. Do not calculate, estimate, interpolate or invent financial
   numbers yourself.

3. Numbers returned by RiskPilot tools are authoritative for the
   current analysis. Do not silently modify them.

4. Clearly distinguish:
   - historical metrics,
   - deterministic forecasts/scenarios,
   - probabilistic simulation results,
   - management policy thresholds.

5. Do not describe a deterministic result as a probability.

6. If probabilistic results rely on a small residual sample, mention
   that limitation when it materially affects the conclusion.

7. Do not provide accounting, tax, legal or investment advice.
   Frame recommendations as management decision-support.

8. If the available tools do not provide evidence for a requested
   numerical claim, say that RiskPilot has not calculated it.

9. Be concise and management-oriented. Lead with the decision-relevant
   conclusion, then explain the quantitative evidence.

10. End business-specific answers with a short line:
    "Evidence used: ..."
    naming the RiskPilot tools you used.
""".strip()


def build_risk_analyst() -> Agent[
    RiskAnalystContext
]:
    load_dotenv()

    model = os.getenv(
        "RISKPILOT_AI_MODEL",
        "gpt-5.6-luna",
    )

    return Agent[
        RiskAnalystContext
    ](
        name="RiskPilot AI Risk Analyst",
        model=model,
        instructions=INSTRUCTIONS,
        tools=[
            get_business_health,
            get_forecast_outlook,
            get_liquidity_risk,
            run_stress_test,
            run_reverse_stress,
        ],
    )


def run_risk_analyst(
    context: RiskAnalystContext,
    question: str,
) -> RiskAnalystResponse:
    context.tool_calls.clear()

    agent = build_risk_analyst()

    result = Runner.run_sync(
        agent,
        question,
        context=context,
    )

    return RiskAnalystResponse(
        answer=str(
            result.final_output
        ),
        tools_used=tuple(
            context.tool_calls
        ),
    )
