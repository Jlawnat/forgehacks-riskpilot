"""Premium React adapters for existing RiskPilot engines.

No pricing, cash-flow, forecast, simulation, AI, or recovery equations live here.
Legacy monthly analysis and V2 13-week direct cash are strictly separate.
In-memory sessions are local-development only and expire after one hour.
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from secrets import token_urlsafe
from threading import RLock
from time import monotonic

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from src.core.forecast_monitoring import create_forecast_snapshot, compare_forecast_snapshots
from src.api.public_interactive import (current_public_owner, history_storage_key, require_demo_upload)
from src.core.recovery_optimizer import RecoverySearchConfig, optimize_recovery
from src.core.recovery_constraints import (
    RevenueImprovementConstraint, CostReductionConstraint,
    ReceivableAccelerationConstraint, ExternalLiquidityConstraint, RecoveryConstraintSet,
)
from src.core.weekly_recovery_validation import validate_weekly_recovery_plan
from src.core.recovery_engine import RecoveryPlan, evaluate_recovery_plan
from src.reporting.management_brief_pdf import build_management_brief_pdf

router = APIRouter(prefix="/api")
_LOCK = RLock()
_MONTHLY = {}
_HISTORY = {}
_TTL = 3600
_MAX_UPLOAD = 5 * 1024 * 1024


def _api():
    from src.api import premium_web
    return premium_web


def _get_context(scenario_id: str, customer_session_id: str | None):
    return _api()._analysis_context(scenario_id, customer_session_id)


def _payload(data):
    return jsonable_encoder(data)


def _monthly_session(token: str):
    with _LOCK:
        session = _MONTHLY.get(token)
        if session is None or session["expires_at"] <= monotonic():
            _MONTHLY.pop(token, None)
            raise HTTPException(404, "Monthly data session unavailable. Upload a monthly CSV again.")
        if current_public_owner() is not None and session.get("public_owner") != current_public_owner():
            raise HTTPException(404, "Monthly session unavailable in this browser.")
        return session


@router.post("/legacy/monthly/import")
async def import_monthly(file: UploadFile = File(...), horizon: int = Form(3), reserve: float = Form(0), appetite: float = Form(0.05)):
    """Load a separate monthly dataset; never relabel weekly cash events as monthly."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(422, "Upload a monthly business CSV, not a 13-week cash-events file.")
    raw = await file.read(_MAX_UPLOAD + 1)
    if not raw or len(raw) > _MAX_UPLOAD:
        raise HTTPException(413, "Monthly CSV must be non-empty and under 5 MB.")
    require_demo_upload(raw, file.filename, purpose="monthly")
    if not (1 <= horizon <= 12 and reserve >= 0 and 0 <= appetite <= 1):
        raise HTTPException(422, "Invalid monthly forecast horizon or risk policy.")
    from src.ingestion.loader import normalize_business_dataframe
    from src.ingestion.validator import validate_business_data
    from src.core.risk_policy import RiskPolicy
    from src.ai.context import build_risk_analyst_context
    try:
        frame, report = validate_business_data(normalize_business_dataframe(pd.read_csv(BytesIO(raw))))
        if len(frame) < 6:
            raise ValueError("Monthly analysis needs at least 6 observations.")
        intervals = frame.date.diff().dropna().dt.days
        if intervals.empty or not intervals.between(27, 32).all():
            raise ValueError("Expected one observation per month; weekly cash-event CSVs are not compatible.")
        policy = RiskPolicy(minimum_cash_reserve=reserve, max_shortfall_probability=appetite)
        context = build_risk_analyst_context(frame, policy, horizon=horizon)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    token = token_urlsafe(32)
    with _LOCK:
        if len(_MONTHLY) >= 20:
            oldest = min(_MONTHLY, key=lambda k: _MONTHLY[k]["expires_at"])
            del _MONTHLY[oldest]
        _MONTHLY[token] = {"frame": frame, "policy": policy, "context": context,
                           "report": report, "public_owner": current_public_owner(), "expires_at": monotonic() + _TTL}
    return {"monthly_session_id": token, "scope": "legacy_monthly_not_v2_weekly",
            "periods": len(frame), "forecast_horizon_months": horizon, "data_quality": _payload(report)}


class MonthlyRequest(BaseModel):
    monthly_session_id: str
    revenue_change_pct: float = Field(0, ge=-100, le=200)
    cost_change_pct: float = Field(0, ge=-100, le=200)
    receivable_delay_days: int = Field(0, ge=0, le=180)
    horizon_months: int = Field(3, ge=1, le=12)


@router.post("/legacy/monthly/stress")
def monthly_stress(payload: MonthlyRequest):
    from src.scenarios.engine import ScenarioInput, prepare_scenario_context, run_scenario_from_context
    from src.scenarios.decomposition import decompose_scenario_from_context
    session = _monthly_session(payload.monthly_session_id)
    scenario = ScenarioInput(revenue_change=payload.revenue_change_pct / 100,
                             cost_change=payload.cost_change_pct / 100,
                             receivable_delay_days=payload.receivable_delay_days,
                             horizon=payload.horizon_months)
    try:
        context = prepare_scenario_context(session["frame"], payload.horizon_months)
        outcome = run_scenario_from_context(context, scenario)
        decomposition = decompose_scenario_from_context(context, scenario)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"scope": "legacy_monthly", "scenario": _payload(outcome), "decomposition": _payload(decomposition)}


class ReverseRequest(BaseModel):
    monthly_session_id: str
    target_min_cash: float = Field(0, ge=0)
    horizon_months: int = Field(3, ge=1, le=12)
    max_revenue_decline_pct: float = Field(30, ge=0, le=100)
    max_cost_increase_pct: float = Field(30, ge=0, le=200)
    max_receivable_delay_days: int = Field(90, ge=0, le=180)


@router.post("/legacy/monthly/reverse-stress")
def monthly_reverse_stress(payload: ReverseRequest):
    from src.scenarios.engine import prepare_scenario_context
    from src.scenarios.reverse_stress import ReverseStressConfig, reverse_stress_from_context
    session = _monthly_session(payload.monthly_session_id)
    config = ReverseStressConfig(target_min_cash=payload.target_min_cash, horizon=payload.horizon_months,
                                 max_revenue_decline=payload.max_revenue_decline_pct / 100,
                                 max_cost_increase=payload.max_cost_increase_pct / 100,
                                 max_receivable_delay_days=payload.max_receivable_delay_days,
                                 grid_step=0.05)
    try:
        context = prepare_scenario_context(session["frame"], payload.horizon_months)
        result = reverse_stress_from_context(context, config)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"scope": "legacy_monthly", "reverse_stress": _payload(result)}


class MonthlyQuestion(BaseModel):
    monthly_session_id: str
    question: str = Field(min_length=1, max_length=2000)


@router.post("/legacy/monthly/agent")
def monthly_agent(payload: MonthlyQuestion):
    from src.ai.analyst import run_risk_analyst
    session = _monthly_session(payload.monthly_session_id)
    try:
        response = run_risk_analyst(session["context"], payload.question)
    except Exception as exc:
        raise HTTPException(503, f"Legacy monthly AI unavailable: {type(exc).__name__}. Verify AI credentials and runtime.") from exc
    return {"scope": "legacy_monthly", "answer": response.answer, "tools_used": list(response.tools_used)}


class RecoveryRequest(BaseModel):
    scenario_id: str = "stressed_recoverable"
    customer_session_id: str | None = None
    max_revenue_improvement_pct: float = Field(20, ge=0, le=100)
    max_cost_reduction_pct: float = Field(15, ge=0, le=100)
    max_receivable_acceleration_days: int = Field(14, ge=0, le=90)
    max_external_liquidity: float = Field(100000, ge=0, le=50000000)
    apply_to_committed_receivables: bool = False


def _customer_constraints(scenario, payload):
    """Only explicitly scoped, compatible active event IDs are eligible."""
    date_from = scenario.forecast_input.start_date
    events = scenario.forecast_input.events
    def selected(source, direction, category=None):
        return tuple(event.event_id for event in events if event.status == "ACTIVE"
                     and event.source_type == source and event.direction == direction
                     and (category is None or event.category == category))
    rev = selected("MODELLED", "INFLOW", "residual sales receipts")
    cost = selected("MODELLED", "OUTFLOW", "variable operating costs")
    ar = tuple(event.event_id for event in events if event.status == "ACTIVE"
               and event.source_type == "COMMITTED" and event.direction == "INFLOW"
               and event.category.lower().strip() in {"customer receipts", "accounts receivable"})
    if not payload.apply_to_committed_receivables:
        ar = ()
    return RecoveryConstraintSet(
        revenue_improvement=RevenueImprovementConstraint(available_from=date_from,
              enabled=bool(rev and payload.max_revenue_improvement_pct),
              max_improvement_pct=payload.max_revenue_improvement_pct if rev else 0,
              eligible_event_ids=rev),
        cost_reduction=CostReductionConstraint(available_from=date_from,
              enabled=bool(cost and payload.max_cost_reduction_pct),
              max_reduction_pct=payload.max_cost_reduction_pct if cost else 0,
              eligible_event_ids=cost),
        receivable_acceleration=ReceivableAccelerationConstraint(available_from=date_from,
              enabled=bool(ar and payload.max_receivable_acceleration_days),
              max_acceleration_days=payload.max_receivable_acceleration_days if ar else 0,
              eligible_event_ids=ar),
        external_liquidity=ExternalLiquidityConstraint(available_from=date_from,
              enabled=payload.max_external_liquidity > 0,
              max_amount=payload.max_external_liquidity))


@router.post("/recovery/optimise")
def recovery_optimise(payload: RecoveryRequest):
    scenario, _ = _get_context(payload.scenario_id, payload.customer_session_id)
    # Demo constraints are the immutable validated source of available actions.
    # Customer constraints must be explicitly provided through management inputs.
    constraints = (scenario.recovery_constraints if payload.customer_session_id is None
                   else _customer_constraints(scenario, payload))
    if constraints is None:
        raise HTTPException(422, "No recovery constraints for this demo. Choose a stressed recovery scenario.")
    try:
        search = optimize_recovery(scenario.forecast_input, constraints,
                                   management_reserve=scenario.management_reserve,
                                   config=RecoverySearchConfig(revenue_step_pct=5, cost_step_pct=5,
                                                               receivable_step_days=7))
        choices = (("Recommended", search.recommended),
                   ("Lowest funding", search.lowest_external_liquidity),
                   ("Lowest operational disruption", search.lowest_operational_disruption),
                   ("Best effort", search.best_effort))
        validated = []
        seen = {}
        for name, candidate in choices:
            if candidate is None:
                continue
            key = candidate.plan.model_dump_json()
            if key in seen:
                seen[key]["also_selected_for"].append(name)
                continue
            validation = validate_weekly_recovery_plan(
                scenario.forecast_input, constraints, candidate.plan,
                scenario.uncertainty_profile, management_reserve=scenario.management_reserve,
                max_reserve_breach_probability=scenario.max_reserve_breach_probability,
                simulations=1000, seed=42)
            row = {"name": name, "also_selected_for": [],
                   "candidate": _payload(candidate), "validation": _payload(validation)}
            validated.append(row)
            seen[key] = row
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"scope": "v2_13_week", "scenario_name": scenario.name,
            "constraints": _payload(constraints), "search": _payload(search),
            "shortlist": validated,
            "unique_plan_count": len(validated),
            "duplicate_objectives": sum(len(row["also_selected_for"]) for row in validated),
            "notice": (
                "Search feasibility is deterministic; each unique plan has a separate probabilistic validation. "
                "Different objectives can select the same underlying plan under binding constraints. "
                "A deterministic feasible outcome is not automatically within probabilistic risk appetite."
            )}


class CustomRecoveryRequest(RecoveryRequest):
    """Customer-selected intervention; engine validates hard constraints."""

    revenue_improvement_pct: float = Field(0, ge=0, le=100)
    cost_reduction_pct: float = Field(0, ge=0, le=100)
    receivable_acceleration_days: int = Field(0, ge=0, le=90)
    external_liquidity: float = Field(0, ge=0, le=50000000)


@router.post("/recovery/validate-plan")
def validate_custom_recovery(payload: CustomRecoveryRequest):
    """Evaluate a manual recovery plan with existing 13-week financial engines.

    No new cash math is performed in this adapter. The authoritative engine
    enforces eligibility, dates and hard management action limits.
    """
    scenario, _ = _get_context(payload.scenario_id, payload.customer_session_id)
    constraints = (scenario.recovery_constraints if payload.customer_session_id is None
                   else _customer_constraints(scenario, payload))
    if constraints is None:
        raise HTTPException(422, "Recovery constraints are unavailable for this scenario.")
    try:
        plan = RecoveryPlan(
            revenue_improvement_pct=payload.revenue_improvement_pct,
            cost_reduction_pct=payload.cost_reduction_pct,
            receivable_acceleration_days=payload.receivable_acceleration_days,
            external_liquidity=payload.external_liquidity,
        )
        evaluation = evaluate_recovery_plan(
            scenario.forecast_input, constraints, plan,
            management_reserve=scenario.management_reserve,
        )
        validation = validate_weekly_recovery_plan(
            scenario.forecast_input, constraints, plan,
            scenario.uncertainty_profile,
            management_reserve=scenario.management_reserve,
            max_reserve_breach_probability=scenario.max_reserve_breach_probability,
            simulations=1000, seed=42,
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return {
        "scope": "v2_13_week",
        "scenario_name": scenario.name,
        "plan": _payload(plan),
        "constraints": _payload(constraints),
        "evaluation": _payload(evaluation),
        "validation": _payload(validation),
        "notice": "Manually selected plan. Engine-validated against verified constraints; probability is a simulation estimate, not a guarantee.",
    }


class SaveSnapshot(BaseModel):
    history_key: str = Field(min_length=20, max_length=100)
    scenario_id: str = "healthy"
    customer_session_id: str | None = None


def _history_bucket(key):
    with _LOCK:
        entry = _HISTORY.get(history_storage_key(key))
        if entry is None or entry["expires_at"] <= monotonic():
            _HISTORY.pop(history_storage_key(key), None)
            return []
        return list(entry["items"])


def _history_summary(snapshot):
    return {"snapshot_id": snapshot.snapshot_id, "created_at": snapshot.created_at.isoformat(),
            "basis": snapshot.forecast_basis_fingerprint,
            "start_date": snapshot.forecast_input.start_date.isoformat(),
            "minimum_cash": snapshot.decision_metrics.minimum_closing_cash,
            "closing_cash": snapshot.forecast.weeks[-1].closing_cash}


@router.post("/forecast/history/save")
def save_forecast_snapshot(payload: SaveSnapshot):
    scenario, _ = _get_context(payload.scenario_id, payload.customer_session_id)
    current = datetime.now(timezone.utc)
    snapshot = create_forecast_snapshot(scenario.forecast_input,
        snapshot_id=f"forecast-{token_urlsafe(12)}", created_at=current,
        management_reserve=scenario.management_reserve)
    with _LOCK:
        # Bound in-memory history state under anonymous reviewer traffic.
        if current_public_owner() is not None:
            now = monotonic()
            for old_key, item in list(_HISTORY.items()):
                if item["expires_at"] <= now:
                    _HISTORY.pop(old_key, None)
            current_key = history_storage_key(payload.history_key)
            if current_key not in _HISTORY and len(_HISTORY) >= 64:
                oldest = min(_HISTORY, key=lambda k: _HISTORY[k]["expires_at"])
                _HISTORY.pop(oldest, None)
        items = _history_bucket(payload.history_key)
        items.append(snapshot)
        _HISTORY[history_storage_key(payload.history_key)] = {"expires_at": monotonic() + _TTL, "items": items[-12:]}
    return {"saved": _history_summary(snapshot), "history": [_history_summary(s) for s in items[-12:]]}


@router.get("/forecast/history")
def list_history(history_key: str):
    return {"history": [_history_summary(s) for s in _history_bucket(history_key)]}


class CompareSnapshots(BaseModel):
    history_key: str
    prior_snapshot_id: str
    current_snapshot_id: str


@router.post("/forecast/history/compare")
def compare_history(payload: CompareSnapshots):
    snapshots = {s.snapshot_id: s for s in _history_bucket(payload.history_key)}
    if payload.prior_snapshot_id not in snapshots or payload.current_snapshot_id not in snapshots:
        raise HTTPException(404, "Snapshot unavailable in this local history session.")
    comparison = compare_forecast_snapshots(snapshots[payload.prior_snapshot_id], snapshots[payload.current_snapshot_id])
    return {"comparison": _payload(comparison)}


@router.get("/evidence/weeks/{scenario_id}")
def weekly_evidence(scenario_id: str, customer_session_id: str | None = None):
    scenario, result = _get_context(scenario_id, customer_session_id)
    events = {e.event_id: e for e in scenario.forecast_input.events}
    weeks = []
    for week in result.snapshot.forecast.weeks:
        rows = []
        for c in week.contributions:
            event = events.get(c.event_id)
            rows.append({"event_id": c.event_id, "category": event.category if event else "Unknown",
                         "source_type": c.source_type, "direction": c.direction,
                         "gross_amount": float(c.gross_amount), "included_amount": float(c.included_amount),
                         "signed_cash_effect": float(c.included_amount) if c.direction == "INFLOW" else -float(c.included_amount),
                         "effective_cash_date": c.effective_cash_date.isoformat(),
                         "source_reference": event.source_reference if event else ""})
        weeks.append({"week": week.week_number, "closing_cash": week.closing_cash, "events": rows})
    return JSONResponse(_payload({"scope": "v2_13_week", "weeks": weeks}), headers={"Cache-Control": "no-store"})


@router.get("/reports/{scenario_id}/management.pdf")
def management_pdf(scenario_id: str, customer_session_id: str | None = None):
    _, result = _get_context(scenario_id, customer_session_id)
    pdf = build_management_brief_pdf(result)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="riskpilot-management-brief.pdf"',
                             "Cache-Control": "no-store"})


@router.get("/reports/{scenario_id}/audit.json")
def audit_json(scenario_id: str, customer_session_id: str | None = None):
    scenario, result = _get_context(scenario_id, customer_session_id)
    return JSONResponse(_payload({"scope": "v2_13_week", "scenario": scenario.model_dump(mode="json"),
                                 "command_center": result.model_dump(mode="json")}),
                        headers={"Cache-Control": "no-store", "Content-Disposition": 'attachment; filename="riskpilot-audit.json"'})

@router.post("/forecast/history/actuals")
async def reconcile_forecast_actuals(
    file: UploadFile = File(...),
    history_key: str = Form(...),
    snapshot_id: str = Form(...),
    through_date: str = Form(...),
):
    """Compare linked observed cash against a saved forecast without inferred matches."""
    from datetime import date as date_type
    from src.core.forecast_monitoring import ActualCashObservation, compare_forecast_to_actual
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(422, "Upload a CSV containing actual cash observations.")
    raw = await file.read(2 * 1024 * 1024 + 1)
    if not raw or len(raw) > 2 * 1024 * 1024:
        raise HTTPException(413, "Actual cash CSV must be non-empty and under 2 MB.")
    require_demo_upload(raw, file.filename, purpose="actuals")
    snapshots = {s.snapshot_id: s for s in _history_bucket(history_key)}
    if snapshot_id not in snapshots:
        raise HTTPException(404, "The chosen forecast snapshot is unavailable.")
    try:
        observed = pd.read_csv(BytesIO(raw)).fillna("")
        required = {"actual_id", "date", "amount", "direction", "source_reference"}
        if not required <= set(observed.columns):
            raise ValueError("CSV must contain actual_id, date, amount, direction and source_reference. An optional forecast_event_id explicitly links a realised payment.")
        if len(observed) > 1000:
            raise ValueError("Actual cash CSV exceeds the 1,000 observation limit.")
        actuals = tuple(ActualCashObservation.model_validate({
            "actual_id": str(row["actual_id"]), "date": str(row["date"]),
            "amount": row["amount"], "direction": str(row["direction"]),
            "source_reference": str(row["source_reference"]),
            "forecast_event_id": str(row["forecast_event_id"]).strip() or None if "forecast_event_id" in observed.columns else None,
        }) for _, row in observed.iterrows())
        comparison = compare_forecast_to_actual(snapshots[snapshot_id], actuals,
                                                 through_date=date_type.fromisoformat(through_date))
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"scope": "v2_forecast_vs_observed_cash", "comparison": _payload(comparison),
            "matching_rule": "Only explicit forecast_event_id links may match realised cash to forecast events."}


@router.get("/monitoring/{scenario_id}")
def management_monitoring(scenario_id: str, customer_session_id: str | None = None):
    scenario, result = _get_context(scenario_id, customer_session_id)
    brief = result.brief
    return {"scope": "v2_13_week", "scenario_name": scenario.name,
            "actions": _payload(brief.actions),
            "monitoring": None if brief.monitoring is None else _payload(brief.monitoring),
            "notice": "Actions and triggers are engine-issued. Expected impact is not realised benefit."}

class RecoveryReferencePlan(BaseModel):
    """Exact optimizer plan inputs to identify the selected comparison row."""
    revenue_improvement_pct: float = Field(ge=0, le=100)
    cost_reduction_pct: float = Field(ge=0, le=100)
    receivable_acceleration_days: int = Field(ge=0, le=90)
    external_liquidity: float = Field(ge=0, le=50000000)


class RecoveryDecisionInsightRequest(CustomRecoveryRequest):
    reference_plan: RecoveryReferencePlan
    question: str = Field(min_length=1, max_length=500)


def _matches_plan(reference: dict, target: RecoveryReferencePlan) -> bool:
    expected = target.model_dump()
    return all(abs(float(reference.get(key, float('nan'))) - float(value)) < 1e-7
               for key, value in expected.items())


@router.post("/recovery/decision-insight")
def generate_recovery_decision_insight(payload: RecoveryDecisionInsightRequest):
    """Revalidate both plans on the same scenario before requesting AI prose."""
    from src.api.recovery_decision_ai import (
        verified_decision_evidence, generate_ai_decision_interpretation,
    )
    # Never accept frontend financial outputs as verified evidence.
    baseline = RecoveryRequest.model_validate(payload.model_dump(exclude={
        "reference_plan", "question", "revenue_improvement_pct",
        "cost_reduction_pct", "receivable_acceleration_days", "external_liquidity",
    }))
    search = recovery_optimise(baseline)
    reference = next((row for row in search["shortlist"]
                      if _matches_plan(row["candidate"]["plan"], payload.reference_plan)), None)
    if reference is None:
        raise HTTPException(409, "Selected optimised plan is not available under the current scenario constraints. Run the optimiser again.")
    custom = validate_custom_recovery(payload)
    if custom["scenario_name"] != search["scenario_name"]:
        raise HTTPException(409, "Comparison plan contexts do not match. Re-run both plan analyses.")
    evidence = verified_decision_evidence(search["scenario_name"], reference["name"], reference, custom)
    try:
        answer = generate_ai_decision_interpretation(evidence, payload.question)
    except Exception as exc:
        raise HTTPException(503, "AI interpretation unavailable. Check configured AI credentials and model access, then retry.") from exc
    return {
        "scope": "v2_13_week", "ai_generated": True,
        "answer": answer, "verified_evidence": evidence,
        "verification_steps": [
            "Re-ran the recovery optimiser for the selected scenario",
            "Re-evaluated and probabilistically validated the custom plan",
            "Matched the selected reference plan against the fresh optimiser shortlist",
            "Generated AI interpretation from authoritative verified evidence",
        ],
        "notice": "AI interprets engine-confirmed outcomes; it does not calculate financial results or certify real-world risk.",
    }
