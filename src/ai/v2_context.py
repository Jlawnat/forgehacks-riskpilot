from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.core.liquidity_brief import (
    LiquidityDecisionBrief,
)
from src.core.v2_what_if import V2WhatIfRequest, V2WhatIfResult
from src.demo.v2_scenarios import V2DemoScenario


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

    baseline_scenario: V2DemoScenario | None = None
    what_if_created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    what_if_simulations: int = 2000
    what_if_seed: int = 42

    what_if_request: V2WhatIfRequest | None = None
    what_if_result: V2WhatIfResult | None = None

    tool_calls: list[str] = field(
        default_factory=list
    )

    def record_tool(
        self,
        name: str,
    ) -> None:
        self.tool_calls.append(name)
