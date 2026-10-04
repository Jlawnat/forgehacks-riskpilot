from __future__ import annotations

from dataclasses import dataclass, field

from src.core.liquidity_brief import (
    LiquidityDecisionBrief,
)


@dataclass
class V2CopilotContext:
    """
    Dedicated context for the RiskPilot V2 AI Decision Copilot.

    This context intentionally contains no legacy monthly dataframe,
    ForecastContext, metrics, risks or RiskPolicy.

    The V2 Liquidity Decision Brief is the authoritative financial
    evidence supplied to the Copilot.
    """

    liquidity_brief: LiquidityDecisionBrief | None

    tool_calls: list[str] = field(
        default_factory=list
    )

    def record_tool(
        self,
        name: str,
    ) -> None:
        self.tool_calls.append(name)
