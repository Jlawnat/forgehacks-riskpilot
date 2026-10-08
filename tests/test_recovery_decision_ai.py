"""No-paid-model contract tests for engine-revalidated AI decision synthesis."""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from src.api import premium_restoration as restoration
from src.api import recovery_decision_ai as ai


def _plan(revenue=30, costs=25, collections=7, funding=0):
    return {
        "revenue_improvement_pct": revenue,
        "cost_reduction_pct": costs,
        "receivable_acceleration_days": collections,
        "external_liquidity": funding,
    }


def _optimised():
    return {"scenario_name": "Demo",
            "shortlist": [{"name": "Best effort", "candidate": {
                "plan": _plan(), "evaluation": {"resulting_min_cash": 70000, "feasible": True}},
                "validation": {"reserve_breach_probability": 0.0,
                               "within_risk_appetite": True,
                               "max_acceptable_breach_probability": 0.1,
                               "simulations": 1000}}]}


def _custom():
    return {"scenario_name": "Demo", "plan": _plan(15, 12.5, 3, 1000),
            "evaluation": {"resulting_min_cash": 67000, "feasible": True},
            "validation": {"reserve_breach_probability": 0.0,
                           "within_risk_appetite": True,
                           "max_acceptable_breach_probability": 0.1,
                           "simulations": 1000}}


def _payload(ref=None):
    return restoration.RecoveryDecisionInsightRequest(
        scenario_id="harborview_synthetic",
        reference_plan=ref or _plan(), question="Compare management actions.",
        revenue_improvement_pct=15, cost_reduction_pct=12.5,
        receivable_acceleration_days=3, external_liquidity=1000,
    )


def test_extracted_evidence_uses_only_revalidated_values():
    evidence = ai.verified_decision_evidence("Demo", "Best effort",
                                             _optimised()["shortlist"][0], _custom())
    assert evidence["custom_plan"]["resulting_minimum_cash"] == 67000
    assert evidence["optimised_reference"]["resulting_minimum_cash"] == 70000
    assert evidence["custom_plan"]["simulation_paths"] == 1000
    assert "finite simulation" in " ".join(evidence["grounding_rules"])


def test_reference_plan_must_be_in_fresh_shortlist(monkeypatch):
    monkeypatch.setattr(restoration, "recovery_optimise", lambda _: _optimised())
    called = []
    monkeypatch.setattr(restoration, "validate_custom_recovery", lambda _: called.append(True))
    with pytest.raises(HTTPException) as exc:
        restoration.generate_recovery_decision_insight(_payload(_plan(5, 0, 0, 0)))
    assert exc.value.status_code == 409
    assert not called


def test_ai_receives_only_fresh_engine_outputs(monkeypatch):
    monkeypatch.setattr(restoration, "recovery_optimise", lambda _: _optimised())
    monkeypatch.setattr(restoration, "validate_custom_recovery", lambda _: _custom())
    seen = []
    monkeypatch.setattr(ai, "generate_ai_decision_interpretation",
                        lambda evidence, question: (seen.append((evidence, question)) or "AI output from mock model"))
    output = restoration.generate_recovery_decision_insight(_payload())
    assert output["ai_generated"] is True
    assert output["answer"] == "AI output from mock model"
    assert output["verified_evidence"]["custom_plan"]["plan"]["external_liquidity"] == 1000
    assert output["verified_evidence"]["optimised_reference"]["plan"]["external_liquidity"] == 0
    assert seen[0][1] == "Compare management actions."
    assert len(output["verification_steps"]) == 4


def test_context_mismatch_aborts_before_ai(monkeypatch):
    monkeypatch.setattr(restoration, "recovery_optimise", lambda _: _optimised())
    row = _custom(); row["scenario_name"] = "Different"
    monkeypatch.setattr(restoration, "validate_custom_recovery", lambda _: row)
    with pytest.raises(HTTPException) as exc:
        restoration.generate_recovery_decision_insight(_payload())
    assert exc.value.status_code == 409


def test_unavailable_ai_does_not_fabricate_answer(monkeypatch):
    monkeypatch.setattr(restoration, "recovery_optimise", lambda _: _optimised())
    monkeypatch.setattr(restoration, "validate_custom_recovery", lambda _: _custom())
    def raise_ai(*args):
        raise RuntimeError("No credentials")
    monkeypatch.setattr(ai, "generate_ai_decision_interpretation", raise_ai)
    with pytest.raises(HTTPException) as exc:
        restoration.generate_recovery_decision_insight(_payload())
    assert exc.value.status_code == 503
    assert "AI interpretation unavailable" in exc.value.detail


def test_reference_matching_is_strict():
    assert restoration._matches_plan(_plan(), restoration.RecoveryReferencePlan(**_plan()))
    assert not restoration._matches_plan(_plan(), restoration.RecoveryReferencePlan(**_plan(0, 0, 0, 0)))
