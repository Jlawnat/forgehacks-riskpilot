from __future__ import annotations

from datetime import date, datetime, timezone
import csv
from io import StringIO
from io import BytesIO
from secrets import token_urlsafe
from threading import RLock
from time import monotonic

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, JSONResponse
from pydantic import BaseModel, Field

from src.ai.v2_context import V2CopilotContext
from src.ai.v2_copilot import run_v2_copilot
from src.api.verified_agent_workspace import build_verified_agent_workspace
from src.api.public_interactive import (current_public_owner, require_demo_upload,
                                        router as interactive_sample_router)
from src.core.command_center import build_command_center
from src.core.recovery_engine import RecoveryPlan, evaluate_recovery_plan
from src.core.v2_what_if import V2WhatIfRequest, run_v2_what_if
from src.core.weekly_recovery_validation import validate_weekly_recovery_plan
from src.api.premium_demo import (
    DEMO_ID, available_premium_scenarios, resolve_premium_scenario,
)
from src.ingestion.customer_cash import (
    build_customer_cash_events,
    build_customer_import_report,
    build_customer_scenario,
    customer_cash_template,
    parse_customer_cash_csv,
)


app = FastAPI(
    title="RiskPilot Premium Web API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Local development-only, in-memory customer analysis sessions.
# Session IDs are unpredictable capabilities; never reuse the company slug
# as authorization or expose customer scenarios in /api/scenarios.
_CUSTOMER_SESSIONS = {}
_CUSTOMER_LOCK = RLock()
_CUSTOMER_TTL_SECONDS = 3600
_CUSTOMER_MAX_SESSIONS = 25
_CUSTOMER_MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def _customer_levers(scenario):
    events = scenario.forecast_input.events
    def eligible(direction, category):
        return [event for event in events if
                event.source_type == "MODELLED" and
                getattr(event, "status", "ACTIVE") == "ACTIVE" and
                event.direction == direction and
                event.category == category]
    receipts = eligible("INFLOW", "residual sales receipts")
    costs = eligible("OUTFLOW", "variable operating costs")
    return {
        "modelled_revenue_events": len(receipts),
        "modelled_cost_events": len(costs),
        "modelled_revenue_amount": sum(float(e.amount) for e in receipts),
        "modelled_cost_amount": sum(float(e.amount) for e in costs),
        "receivable_timing_supported": False,
        "recovery_constraints_available": scenario.recovery_constraints is not None,
    }


def _save_customer_session(scenario, result):
    token = token_urlsafe(32)
    with _CUSTOMER_LOCK:
        now = monotonic()
        for key, entry in list(_CUSTOMER_SESSIONS.items()):
            if entry["expires_at"] <= now:
                del _CUSTOMER_SESSIONS[key]
        if len(_CUSTOMER_SESSIONS) >= _CUSTOMER_MAX_SESSIONS:
            oldest = min(_CUSTOMER_SESSIONS,
                         key=lambda key: _CUSTOMER_SESSIONS[key]["expires_at"])
            del _CUSTOMER_SESSIONS[oldest]
        _CUSTOMER_SESSIONS[token] = {
            "scenario": scenario,
            "result": result,
            "expires_at": now + _CUSTOMER_TTL_SECONDS,
            "capabilities": _customer_levers(scenario), "public_owner": current_public_owner(),
        }
    return token


def _load_customer_session(token):
    if not token:
        raise HTTPException(status_code=400, detail="Customer session ID is required.")
    with _CUSTOMER_LOCK:
        entry = _CUSTOMER_SESSIONS.get(token)
        if entry is None:
            raise HTTPException(status_code=404, detail=(
                "Customer analysis session not found. Re-import the cash CSV."
            ))
        if current_public_owner() is not None and entry.get("public_owner") != current_public_owner():
            raise HTTPException(status_code=404, detail="Customer session not found in this browser.")
        if entry["expires_at"] <= monotonic():
            del _CUSTOMER_SESSIONS[token]
            raise HTTPException(status_code=410, detail=(
                "Customer analysis session expired. Re-import the cash CSV."
            ))
        return entry


def _analysis_context(scenario_id, customer_session_id):
    if customer_session_id is not None:
        entry = _load_customer_session(customer_session_id)
        return entry["scenario"], entry["result"]
    return _command_center_result(scenario_id)


def _validate_customer_what_if(payload, entry):
    caps = entry["capabilities"]
    if (payload.revenue_change_pct is not None
            and payload.revenue_change_pct != 0
            and not caps["modelled_revenue_events"]):
        raise HTTPException(status_code=422, detail=(
            "No eligible MODELLED 'residual sales receipts' cash events exist "
            "in the selected forecast. Revenue changes cannot alter committed evidence. "
            "Add supported modelled sales events, or set revenue change to 0%."
        ))
    if (payload.cost_change_pct is not None
            and payload.cost_change_pct != 0
            and not caps["modelled_cost_events"]):
        raise HTTPException(status_code=422, detail=(
            "No eligible MODELLED 'variable operating costs' cash events exist "
            "in the selected forecast. Cost changes cannot alter committed evidence. "
            "Add supported modelled cost events, or set cost change to 0%."
        ))


CREATED_AT = datetime(
    2026,
    10,
    8,
    0,
    0,
    tzinfo=timezone.utc,
)


def _money(value):
    if value is None:
        return None
    return float(value)


def _command_center_result(
    scenario_id: str,
):
    try:
        scenario = resolve_premium_scenario(
            scenario_id
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    result = build_command_center(
        scenario,
        created_at=CREATED_AT,
        simulations=2000,
        seed=42,
    )

    return scenario, result


def _summary(
    scenario,
    result,
):
    brief = result.brief
    position = brief.position
    uncertainty = brief.uncertainty

    weeks = [
        {
            "week": int(week.week_number),
            "closing_cash": float(
                week.closing_cash
            ),
        }
        for week in result.snapshot.forecast.weeks
    ]

    quantiles = [
        {
            "week": index + 1,
            "p10": float(point.p10_cash),
            "p50": float(point.p50_cash),
            "p90": float(point.p90_cash),
        }
        for index, point in enumerate(
            result.simulation.cash_path_quantiles
        )
    ]

    cash_drivers = [
        {
            "event_id": driver.event_id,
            "category": driver.category,
            "source_type": driver.source_type,
            "direction": driver.direction,
            "week": driver.week_number,
            "amount": float(
                driver.signed_cash_effect
            ),
            "source_amount": float(
                driver.gross_amount
            ),
        }
        for driver in brief.cash_drivers[:8]
    ]

    events = [
        {
            "event_id": event.event_id,
            "date": (
                event.effective_cash_date
                .isoformat()
            ),
            "amount": float(event.amount),
            "direction": event.direction,
            "category": event.category,
            "source_type": event.source_type,
            "source_reference": (
                event.source_reference
            ),
        }
        for event in scenario.forecast_input.events
    ]

    sources = {}
    for event in events:
        ref = (
            event["source_reference"]
            or "RiskPilot source"
        )
        key = (
            ref,
            event["source_type"],
        )
        sources[key] = (
            sources.get(key, 0)
            + 1
        )

    source_rows = [
        {
            "name": ref,
            "type": source_type,
            "items": count,
        }
        for (
            ref,
            source_type,
        ), count in sources.items()
    ]

    recovery = (
        None
        if brief.recovery is None
        else brief.recovery.model_dump(
            mode="json"
        )
    )

    breach_week = (
        position.first_reserve_breach_week
    )

    risk_probability = (
        None
        if uncertainty is None
        else float(
            uncertainty
            .reserve_breach_probability
        )
    )

    appetite = float(
        scenario
        .max_reserve_breach_probability
    )

    if breach_week is not None:
        insight_title = (
            "Near-term liquidity action is required"
        )
        insight_tone = "critical"
        next_step = (
            f"Review recovery actions before Week "
            f"{breach_week}."
        )
    elif (
        risk_probability is not None
        and risk_probability > appetite
    ):
        insight_title = (
            "Liquidity risk exceeds management appetite"
        )
        insight_tone = "warning"
        next_step = (
            "Review downside protection and "
            "liquidity buffer options."
        )
    else:
        insight_title = (
            "Liquidity remains within management appetite"
        )
        insight_tone = "healthy"
        next_step = (
            "Continue monitoring the 13-week "
            "cash position."
        )

    return {
        "scenario": {
            "id": scenario.scenario_id,
            "name": scenario.name,
            "description": scenario.description,
            "start_date": (
                scenario.forecast_input
                .start_date.isoformat()
            ),
            "opening_cash": float(
                scenario.forecast_input
                .opening_cash
            ),
            "reserve": float(
                scenario.management_reserve
            ),
            "risk_appetite": appetite,
            "is_public": scenario.scenario_id == "public_sec_cenveo",
            "is_synthetic": scenario.scenario_id == DEMO_ID,
            "what_if_capabilities": _customer_levers(scenario),
        },
        "position": {
            "current_cash": float(
                position.current_cash
            ),
            "minimum_cash": float(
                position.minimum_closing_cash
            ),
            "minimum_cash_week": int(
                position.minimum_closing_cash_week
            ),
            "minimum_headroom": float(
                position.minimum_headroom
            ),
            "first_breach_week": (
                None
                if breach_week is None
                else int(breach_week)
            ),
            "closing_cash": float(
                position.closing_cash_13_week
            ),
            "evidence_coverage": (
                None
                if (
                    position
                    .evidence_coverage_ratio
                    is None
                )
                else float(
                    position
                    .evidence_coverage_ratio
                )
            ),
            "committed_amount": float(
                position.committed_evidence_amount
            ),
            "modelled_amount": float(
                position.modelled_residual_amount
            ),
            "assumption_amount": float(
                position
                .management_assumption_amount
            ),
        },
        "risk": {
            "probability": (
                risk_probability
            ),
            "risk_appetite": appetite,
            "within_appetite": (
                None
                if uncertainty is None
                else bool(
                    uncertainty
                    .within_risk_appetite
                )
            ),
            "simulations": (
                0
                if uncertainty is None
                else int(
                    uncertainty.simulations
                )
            ),
            "buffer": (
                0.0
                if uncertainty is None
                else float(
                    uncertainty
                    .liquidity_buffer_at_confidence
                )
            ),
        },
        "weeks": weeks,
        "quantiles": quantiles,
        "cash_drivers": cash_drivers,
        "events": events,
        "sources": source_rows,
        "recovery": recovery,
        "insight": {
            "title": insight_title,
            "tone": insight_tone,
            "next_step": next_step,
        },
    }


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "product": "RiskPilot",
    }


@app.get("/api/demo/harborview-cash.csv")
def synthetic_demo_csv():
    """Provide an openly labelled fictional cash-event file for customers to try."""
    demo = resolve_premium_scenario(DEMO_ID)
    columns = (
        "event_id", "date", "amount", "direction", "category",
        "source_type", "status", "description", "source_reference",
        "due_date", "expected_cash_date",
    )
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    for event in demo.forecast_input.events:
        row = event.model_dump(mode="json")
        writer.writerow({k: row.get(k, "") or "" for k in columns})
    return PlainTextResponse(output.getvalue(), media_type="text/csv", headers={
        "Content-Disposition": 'attachment; filename="RiskPilot_Harborview_Synthetic_Cash_Demo.csv"',
        "Cache-Control": "no-store",
    })


@app.get("/api/scenarios")
def scenarios():
    return [
        {
            "id": scenario.scenario_id,
            "name": scenario.name,
            "description": (
                scenario.description
            ),
        }
        for scenario in (
            available_premium_scenarios()
        )
    ]


@app.get(
    "/api/command-center/{scenario_id}"
)
def command_center(
    scenario_id: str,
):
    scenario, result = (
        _command_center_result(
            scenario_id
        )
    )

    return _summary(
        scenario,
        result,
    )


class WhatIfPayload(BaseModel):
    scenario_id: str = "healthy"
    customer_session_id: str | None = None

    revenue_change_pct: float | None = (
        Field(
            default=-20.0,
            ge=-100.0,
            le=100.0,
        )
    )

    cost_change_pct: float | None = (
        Field(
            default=10.0,
            ge=-100.0,
            le=100.0,
        )
    )

    management_reserve: (
        float | None
    ) = None


@app.post("/api/what-if")
def what_if(
    payload: WhatIfPayload,
):
    if payload.customer_session_id is not None:
        entry = _load_customer_session(payload.customer_session_id)
        _validate_customer_what_if(payload, entry)
        scenario = entry["scenario"]
    else:
        try:
            scenario = resolve_premium_scenario(payload.scenario_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Apply the same eligible-event rule to public, synthetic and customer
    # scenarios. A request must never be marked verified if its claimed shock
    # cannot change any supported MODELLED cash event.
    _validate_customer_what_if(payload, {
        "capabilities": _customer_levers(scenario)
    })

    request = V2WhatIfRequest(
        revenue_change_pct=(
            payload.revenue_change_pct
        ),
        cost_change_pct=(
            payload.cost_change_pct
        ),
        management_reserve=(
            payload.management_reserve
        ),
    )

    outcome = run_v2_what_if(
        scenario,
        request,
        created_at=CREATED_AT,
        simulations=2000,
        seed=42,
    )

    return {
        "applied_changes": list(
            outcome.applied_changes
        ),
        "effect": {
            "revenue_events_adjusted": _customer_levers(scenario)["modelled_revenue_events"] if payload.revenue_change_pct else 0,
            "cost_events_adjusted": _customer_levers(scenario)["modelled_cost_events"] if payload.cost_change_pct else 0,
            "reserve_policy_adjusted": (payload.management_reserve is not None and payload.management_reserve != scenario.management_reserve),
            "neutral_recalculation": (not payload.revenue_change_pct and not payload.cost_change_pct and (payload.management_reserve is None or payload.management_reserve == scenario.management_reserve)),
        },
        "baseline_scenario_id": (
            outcome.baseline_scenario_id
        ),
        "result": _summary(
            outcome.scenario,
            outcome.command_center,
        ),
    }


class AgentPayload(BaseModel):
    scenario_id: str = "healthy"
    customer_session_id: str | None = None
    question: str = Field(min_length=1, max_length=2000)


@app.post("/api/agent")
def agent(
    payload: AgentPayload,
):
    scenario, result = _analysis_context(
        payload.scenario_id, payload.customer_session_id
    )

    context = V2CopilotContext(
        liquidity_brief=result.brief,
        baseline_scenario=scenario,
        what_if_created_at=CREATED_AT,
        what_if_simulations=2000,
        what_if_seed=42,
    )

    try:
        response = run_v2_copilot(
            context,
            payload.question,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                type(exc).__name__
                + ": "
                + str(exc)
            ),
        ) from exc

    # AI tools share the frozen V2 engine and can produce a temporary overlay.
    # Do not present an unchanged forecast as an applied operating shock when
    # the current cash evidence lacks eligible MODELLED event categories.
    if getattr(context, "what_if_request", None) is not None:
        attempted = context.what_if_request
        caps = _customer_levers(scenario)
        if attempted.revenue_change_pct and not caps["modelled_revenue_events"]:
            raise HTTPException(status_code=422, detail=(
                "The AI requested a revenue shock but the current forecast has "
                "no eligible MODELLED residual sales receipts. No verified revenue shock was applied."
            ))
        if attempted.cost_change_pct and not caps["modelled_cost_events"]:
            raise HTTPException(status_code=422, detail=(
                "The AI requested an operating cost shock but the current forecast has "
                "no eligible MODELLED variable operating costs. No verified cost shock was applied."
            ))

    active_result = result
    active_scenario = scenario

    if context.what_if_result is not None:
        active_result = (
            context
            .what_if_result
            .command_center
        )

        active_scenario = (
            context
            .what_if_result
            .scenario
        )

    return {
        "answer": response.answer,
        "tools_used": list(
            response.tools_used
        ),
        "temporary_what_if": (
            context.what_if_result
            is not None
        ),
        "result": _summary(
            active_scenario,
            active_result,
        ),
    }


@app.get("/api/agent/verified-workspace/{scenario_id}")
def verified_agent_workspace(
    scenario_id: str,
    customer_session_id: str | None = None,
):
    """Return read-only engine snapshots without invoking or simulating AI."""
    scenario, result = _analysis_context(scenario_id, customer_session_id)
    context = V2CopilotContext(
        liquidity_brief=result.brief,
        baseline_scenario=scenario,
    )
    payload = build_verified_agent_workspace(
        context,
        scenario_name=scenario.name,
        imported=customer_session_id is not None,
    )
    return JSONResponse(
        content=jsonable_encoder(payload),
        headers={"Cache-Control": "no-store"},
    )


@app.get(
    "/api/recovery-options/{scenario_id}"
)
def recovery_options(
    scenario_id: str,
):
    scenario, baseline = (
        _command_center_result(
            scenario_id
        )
    )

    constraints = (
        scenario.recovery_constraints
    )

    if constraints is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Selected scenario has no "
                "recovery constraints."
            ),
        )

    max_external = float(
        constraints
        .external_liquidity
        .max_amount
    )

    current_plan = (
        scenario.recovery_plan
        or RecoveryPlan()
    )

    options = [
        (
            "Balanced",
            current_plan,
            "Recommended",
        ),
        (
            "Lowest Funding",
            RecoveryPlan(
                external_liquidity=0.0
            ),
            "Minimise external liquidity",
        ),
        (
            "Lowest Operational Disruption",
            RecoveryPlan(
                external_liquidity=max_external
            ),
            "Maximise funding support",
        ),
    ]

    payload = []

    for (
        name,
        plan,
        subtitle,
    ) in options:
        evaluation = (
            evaluate_recovery_plan(
                scenario.forecast_input,
                constraints,
                plan,
                management_reserve=(
                    scenario
                    .management_reserve
                ),
            )
        )

        validation = (
            validate_weekly_recovery_plan(
                scenario.forecast_input,
                constraints,
                plan,
                scenario.uncertainty_profile,
                management_reserve=(
                    scenario
                    .management_reserve
                ),
                max_reserve_breach_probability=(
                    scenario
                    .max_reserve_breach_probability
                ),
                simulations=1000,
                seed=42,
            )
        )

        payload.append(
            {
                "name": name,
                "subtitle": subtitle,
                "plan": (
                    plan.model_dump(
                        mode="json"
                    )
                ),
                "evaluation": (
                    evaluation.model_dump(
                        mode="json"
                    )
                ),
                "validation": (
                    validation.model_dump(
                        mode="json"
                    )
                ),
            }
        )

    return {
        "scenario": _summary(
            scenario,
            baseline,
        ),
        "options": payload,
    }


@app.get(
    "/api/customer/template",
    response_class=PlainTextResponse,
)
def customer_template(
    forecast_start: str,
):
    try:
        parsed = date.fromisoformat(
            forecast_start
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid forecast_start",
        ) from exc

    return customer_cash_template(
        forecast_start=parsed
    )


@app.post("/api/customer/import")
async def customer_import(
    file: UploadFile = File(...),
    company_name: str = Form(...),
    forecast_start: str = Form(...),
    opening_cash: float = Form(...),
    management_reserve: float = Form(...),
    max_breach_probability: float = Form(...),
    uncertainty_profile: str = Form("Standard"),
):
    try:
        start = date.fromisoformat(
            forecast_start
        )

        content = await file.read(_CUSTOMER_MAX_UPLOAD_BYTES + 1)
        if len(content) > _CUSTOMER_MAX_UPLOAD_BYTES:
            raise ValueError("CSV exceeds 5 MB limit for this local demo.")
        require_demo_upload(content, file.filename, purpose="customer")

        dataframe = (
            parse_customer_cash_csv(
                content
            )
        )

        events = (
            build_customer_cash_events(
                dataframe,
                upload_reference=(
                    file.filename
                    or "customer-upload.csv"
                ),
            )
        )

        report = (
            build_customer_import_report(
                events,
                forecast_start=start,
            )
        )

        scenario = (
            build_customer_scenario(
                company_name=company_name,
                forecast_start=start,
                opening_cash=opening_cash,
                management_reserve=(
                    management_reserve
                ),
                max_breach_probability=(
                    max_breach_probability
                ),
                uncertainty_profile_name=(
                    uncertainty_profile
                ),
                events=events,
            )
        )

        result = build_command_center(
            scenario,
            created_at=CREATED_AT,
            simulations=2000,
            seed=42,
        )

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    customer_session_id = _save_customer_session(scenario, result)
    return {
        "customer_session_id": customer_session_id,
        "session_expires_in_seconds": _CUSTOMER_TTL_SECONDS,
        "capabilities": _customer_levers(scenario),
        "report": report.model_dump(
            mode="json"
        ),
        "result": _summary(
            scenario,
            result,
        ),
    }


# Feature parity: use the existing customer column-mapping and multi-source
# ingestion services. All mapped imports pass through the same cash-event,
# evidence-validation and financial engines as a template CSV import.
from src.api.customer_import_mapping import (
    MAX_SOURCE_FILES,
    MAX_TOTAL_BYTES,
    map_table,
    merge_tables,
    parse_source_specs,
    parse_spec,
    read_table,
    table_preview,
)


def _complete_mapped_customer_import(
    dataframe, *, company_name: str, forecast_start: str,
    opening_cash: float, management_reserve: float,
    max_breach_probability: float, uncertainty_profile: str,
    upload_reference: str,
):
    try:
        start = date.fromisoformat(forecast_start)
        events = build_customer_cash_events(dataframe, upload_reference=upload_reference)
        report = build_customer_import_report(events, forecast_start=start)
        scenario = build_customer_scenario(
            company_name=company_name,
            forecast_start=start,
            opening_cash=opening_cash,
            management_reserve=management_reserve,
            max_breach_probability=max_breach_probability,
            uncertainty_profile_name=uncertainty_profile,
            events=events,
        )
        result = build_command_center(
            scenario, created_at=CREATED_AT, simulations=2000, seed=42,
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    token = _save_customer_session(scenario, result)
    return {
        "customer_session_id": token,
        "session_expires_in_seconds": _CUSTOMER_TTL_SECONDS,
        "capabilities": _customer_levers(scenario),
        "report": report.model_dump(mode="json"),
        "result": _summary(scenario, result),
    }


@app.post("/api/customer/mapping/preview")
async def customer_mapping_preview(
    file: UploadFile = File(...), sheet_name: str = Form(""),
):
    frame, sheets, selected_sheet, _ = await read_table(file, sheet_name or None)
    return table_preview(frame, sheets, selected_sheet)


@app.post("/api/customer/mapping/import")
async def customer_mapping_import(
    file: UploadFile = File(...),
    mapping_json: str = Form(...),
    sheet_name: str = Form(""),
    company_name: str = Form(...),
    forecast_start: str = Form(...),
    opening_cash: float = Form(...),
    management_reserve: float = Form(...),
    max_breach_probability: float = Form(...),
    uncertainty_profile: str = Form("Standard"),
):
    frame, _, _, _ = await read_table(file, sheet_name or None)
    mapped = map_table(frame, parse_spec(mapping_json), prefix="mapped-cash",
                       source_filename=file.filename)
    return _complete_mapped_customer_import(
        mapped, company_name=company_name, forecast_start=forecast_start,
        opening_cash=opening_cash, management_reserve=management_reserve,
        max_breach_probability=max_breach_probability,
        uncertainty_profile=uncertainty_profile,
        upload_reference=file.filename or "mapped-upload",
    )


@app.post("/api/customer/multi/import")
async def customer_multi_import(
    files: list[UploadFile] = File(...),
    sources_json: str = Form(...),
    company_name: str = Form(...),
    forecast_start: str = Form(...),
    opening_cash: float = Form(...),
    management_reserve: float = Form(...),
    max_breach_probability: float = Form(...),
    uncertainty_profile: str = Form("Standard"),
):
    if not (1 <= len(files) <= MAX_SOURCE_FILES):
        raise HTTPException(status_code=422, detail="Upload between 1 and 5 finance source files.")
    specs = parse_source_specs(sources_json, len(files))
    frames, total_bytes = [], 0
    for index, (file, item) in enumerate(zip(files, specs)):
        frame, _, _, count = await read_table(file, item.get("sheet_name") or None)
        total_bytes += count
        if total_bytes > MAX_TOTAL_BYTES:
            raise HTTPException(status_code=413, detail="Combined upload must not exceed 15 MB.")
        spec = parse_spec(item["mapping"])
        standardized = map_table(frame, spec, prefix=f"source-{index+1}",
                                 source_filename=file.filename)
        frames.append((file.filename or f"source-{index+1}", standardized))
    combined = merge_tables(frames)
    return _complete_mapped_customer_import(
        combined, company_name=company_name, forecast_start=forecast_start,
        opening_cash=opening_cash, management_reserve=management_reserve,
        max_breach_probability=max_breach_probability,
        uncertainty_profile=uncertainty_profile,
        upload_reference="multi-source-finance-import",
    )

# Additional premium workspaces reuse existing RiskPilot calculation engines.
from src.api.premium_restoration import router as restoration_router
app.include_router(restoration_router)
app.include_router(interactive_sample_router)
