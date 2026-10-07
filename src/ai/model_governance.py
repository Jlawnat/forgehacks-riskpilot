"""RiskPilot Agents-based supervisor with a closed, verified evidence contract.

AI selects explanation emphasis only. Python owns metrics, status and displayed claims.
No model-promotion function exists here.
"""
from __future__ import annotations
from dataclasses import dataclass
import json
import os
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict
from agents import RunContextWrapper
from src.forecasting.external_benchmark import MODEL_LABELS, PRODUCTION_MODEL

Outcome = Literal['KEEP PRODUCTION', 'REVIEW CHALLENGER', 'PROMOTION CANDIDATE', 'INSUFFICIENT EVIDENCE']
Claim = Literal['performance', 'stability', 'fit_quality', 'approval', 'scope', 'vintage']

class GovernanceInterpretation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    outcome: Outcome
    evidence_ids: list[Claim] = Field(min_length=2, max_length=6)

@dataclass
class GovernanceContext:
    evidence: dict
    tool_used: bool = False

@dataclass(frozen=True)
class GovernanceResponse:
    outcome: str
    summary: str
    mode: str
    evidence_ids: tuple[str, ...]


def statistical_eligibility(report: dict, candidate: str) -> bool:
    """Predeclared, conservative stability gates, required at BOTH horizons."""
    if candidate == PRODUCTION_MODEL:
        return False
    for horizon in (1, 3):
        row = next((r for r in report['aggregate'] if r['model'] == candidate and r['horizon'] == horizon), None)
        holt = next((r for r in report['aggregate'] if r['model'] == PRODUCTION_MODEL and r['horizon'] == horizon), None)
        if row is None or holt is None or row['mase'] is None or holt['mase'] is None:
            return False
        if not (row['windows'] >= 90 and row['series_count'] >= 3 and row['era_count'] >= 3
                and row['failed_windows'] == 0 and row['warning_windows'] == 0
                and holt['failed_windows'] == 0 and holt['warning_windows'] == 0
                and row['mae_improvement_vs_holt'] is not None and row['mae_improvement_vs_holt'] >= .05
                and row['rmse'] < holt['rmse'] and row['mase'] < holt['mase']
                and row['win_rate_vs_holt'] >= .55
                and len(row['series_wins_vs_holt']) >= 2 and len(row['era_wins_vs_holt']) >= 2):
            return False
    return True


def build_governance_evidence(report: dict) -> dict:
    primary = [r for r in report['aggregate'] if r['horizon'] == 3]
    valid = [r for r in primary if r['model'] != PRODUCTION_MODEL and r['mae'] is not None and r['mase'] is not None and r['failed_windows'] == 0]
    leader = min(valid, key=lambda r: (r['mase'] if r['mase'] is not None else float('inf'), r['model'])) if valid else None
    holt = next((r for r in primary if r['model'] == PRODUCTION_MODEL), None)
    sufficient = holt is not None and holt['mae'] is not None and leader is not None and holt['series_count'] >= 3 and holt['windows'] >= 90
    eligible = sufficient and statistical_eligibility(report, leader['model'])
    gates = report.get('gates', {})
    approved = gates.get('regression_tests') == 'PASS' and gates.get('downstream_financial_consistency') == 'APPROVED'
    if not sufficient:
        status = 'INSUFFICIENT EVIDENCE'
    elif eligible and approved:
        status = 'PROMOTION CANDIDATE'
    elif leader['mae'] < holt['mae'] or (leader['mase'] is not None and holt['mase'] is not None and leader['mase'] < holt['mase']):
        status = 'REVIEW CHALLENGER'
    else:
        status = 'KEEP PRODUCTION'
    claims = {
        'approval': f"Holt remains the frozen governance reference. Regression tests: {gates.get('regression_tests', 'NOT_ASSESSED')}. Downstream promotion review: {gates.get('downstream_financial_consistency', 'NOT_APPROVED')}. Explicit human approval is required; no production selector is changed.",
        'scope': 'These ABS industry indexes are an external monthly model benchmark, not the current business revenue history or 13-week cash evidence.',
        'vintage': 'Results use the final revised September 2025 vintage, including revised seasonal adjustments; they are not an as-published real-time backtest.',
    }
    if sufficient:
        claims['performance'] = f"{MODEL_LABELS[leader['model']]} leads the challengers by equal-weight industry MASE at the three-month horizon: MAE {leader['mae']:.4f} index points, RMSE {leader['rmse']:.4f}, MASE {leader['mase']:.4f}. MAE improvement versus Holt: {leader['mae_improvement_vs_holt']:.1%}."
        claims['stability'] = f"The challenger beats Holt in {leader['win_rate_vs_holt']:.1%} of {leader['windows']} validation windows, {len(leader['series_wins_vs_holt'])} of {leader['series_count']} industries and {len(leader['era_wins_vs_holt'])} of {leader['era_count']} time eras. Statistical stability gates across both horizons: {'PASS' if eligible else 'NOT MET'}."
        claims['fit_quality'] = f"Challenger failed fits: {leader['failed_windows']}; windows with fit warnings: {leader['warning_windows']}. Holt failed fits: {holt['failed_windows']}; warning windows: {holt['warning_windows']}."
    else:
        claims.update(performance='Evidence is incomplete; no reliable challenger comparison is available.',
                      stability='Cross-series and across-time stability has not been established.',
                      fit_quality='Review coverage and fit failures before making a model recommendation.')
    return {'schema_version': 1, 'scope': 'external_benchmark_only', 'production_model': PRODUCTION_MODEL,
            'candidate_model': leader['model'] if leader else None, 'metrics': report['aggregate'],
            'candidate_statistically_eligible': bool(eligible), 'gates': gates, 'outcome': status,
            'production_change_authorized': False, 'limitations': report['limitations'], 'verified_claims': claims}


def deterministic_recommendation(evidence: dict) -> GovernanceResponse:
    ids = ('performance', 'stability', 'fit_quality', 'approval', 'scope', 'vintage')
    return GovernanceResponse(evidence['outcome'], '\n\n'.join(evidence['verified_claims'][key] for key in ids),
                              'Deterministic evidence summary', ids)


def validate_interpretation(evidence: dict, interpretation: GovernanceInterpretation, *, tool_used: bool) -> GovernanceResponse:
    if not tool_used or interpretation.outcome != evidence['outcome']:
        raise ValueError('AI must read the evidence tool and preserve its policy outcome.')
    # Approval/scope/vintage always remain visible, even if AI omits their IDs.
    ids = tuple(dict.fromkeys([*interpretation.evidence_ids, 'approval', 'scope', 'vintage']))
    return GovernanceResponse(evidence['outcome'], '\n\n'.join(evidence['verified_claims'][key] for key in ids),
                              'AI-supervised evidence explanation', ids)


def get_verified_governance_evidence(context) -> dict:
    context.tool_used = True
    return context.evidence


def run_governance_supervisor(evidence: dict) -> GovernanceResponse:
    from dotenv import load_dotenv
    load_dotenv()
    fallback = deterministic_recommendation(evidence)
    if not os.getenv('OPENAI_API_KEY'):
        return fallback
    try:
        from agents import Agent, Runner, RunContextWrapper, function_tool
        @function_tool
        def get_external_model_governance(ctx: RunContextWrapper[GovernanceContext]) -> str:
            """Read the verified external benchmark metrics, gates, policy outcome and claims."""
            return json.dumps(get_verified_governance_evidence(ctx.context), allow_nan=False)
        agent = Agent[GovernanceContext](
            name='RiskPilot AI Model Governance Supervisor',
            model=os.getenv('RISKPILOT_AI_MODEL', 'gpt-5.6-luna'),
            instructions=("Call get_external_model_governance first. Interpret the verified model comparison and prioritize the evidence IDs most useful to management. "
                          "Return the EXACT engine outcome and only allowed evidence IDs. Never calculate forecasts or invent metrics. "
                          "No free-form numerical text is permitted. Never promote or switch production; PROMOTION CANDIDATE only means eligible for explicit human review. "
                          "The external monthly benchmark is separate from company forecasts and V2 13-week cash evidence."),
            tools=[get_external_model_governance], output_type=GovernanceInterpretation)
        context = GovernanceContext(evidence=evidence)
        result = Runner.run_sync(agent, 'Explain the external forecasting evidence and promotion constraints.', context=context, max_turns=3)
        return validate_interpretation(evidence, result.final_output, tool_used=context.tool_used)
    except Exception:
        # Service/convergence/schema failures never expose a traceback or replace verified status.
        return fallback
