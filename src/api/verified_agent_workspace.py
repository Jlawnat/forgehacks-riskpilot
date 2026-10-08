"""Read-only V2 evidence adapters for the Premium agent investigation panel.

Every value comes from existing V2 financial evidence snapshots. This module
performs no financial calculations and never invokes the language model.
"""

from src.ai.v2_tools import (
    v2_actions_monitoring_snapshot,
    v2_cash_evidence_snapshot,
    v2_liquidity_position_snapshot,
    v2_recovery_evidence_snapshot,
)


_WORKSPACE_TOOLS = (
    ("position", "Liquidity position", "get_v2_liquidity_position", v2_liquidity_position_snapshot),
    ("evidence", "Cash evidence", "get_v2_cash_evidence", v2_cash_evidence_snapshot),
    ("recovery", "Recovery evidence", "get_v2_recovery_evidence", v2_recovery_evidence_snapshot),
    ("monitoring", "Actions and monitoring", "get_v2_actions_monitoring", v2_actions_monitoring_snapshot),
)


def build_verified_agent_workspace(context, *, scenario_name: str, imported: bool) -> dict:
    """Expose verified snapshots; do not count these reads as agent tool calls."""
    sections = []
    for key, title, tool_name, read_snapshot in _WORKSPACE_TOOLS:
        snapshot = read_snapshot(context)
        sections.append({
            "id": key,
            "title": title,
            "associated_agent_tool": tool_name,
            "available": snapshot.get("available", False),
            "evidence": snapshot,
        })
    return {
        "scenario_name": scenario_name,
        "source": "customer_upload" if imported else "demo_scenario",
        "scope": "13-week V2 liquidity decision brief",
        "kind": "read_only_verified_engine_evidence",
        "sections": sections,
        "limitations": [
            "These are existing financial engine evidence snapshots, not AI-generated figures.",
            "Browsing a snapshot is not an agent tool execution. The agent trace records actual agent tool calls separately.",
            "Legacy monthly forecasting and V2 weekly direct-cash results are distinct models.",
            "Any recovery probability must be interpreted according to its baseline or conditional post-recovery scope.",
        ],
    }
