import React, { useEffect, useState } from "react";
import AiMarkdown from "./AiMarkdown.jsx";
import { buildRecoveryComparison } from "./recoveryComparison.js";
import { compareReceivableTiming, reverseBreakpoint, MONTHLY_REVERSE_LIMITS } from "./monthlyEvidence.js";

const API = "/api";
const currency = value => value === null || value === undefined ? "—" : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value);
const percent = value => value == null ? "—" : `${(Number(value) * 100).toFixed(1)}%`;
const number = value => value == null ? "—" : Number(value).toLocaleString("en-US", { maximumFractionDigits: 2 });
const readable = value => typeof value === "object" ? JSON.stringify(value, null, 2) : String(value ?? "—");
const planAction = (value, unit, constraint) => {
  if (!constraint?.enabled) return "Not available";
  if (Number(value || 0) === 0) return "Not used";
  return unit === "$" ? currency(value) : `${number(value)}${unit}`;
};
const riskDescription = (validation) => {
  const p = Number(validation?.reserve_breach_probability);
  const simulations = number(validation?.simulations);
  if (!Number.isFinite(p) || !validation?.simulations) return "Simulation evidence is unavailable.";
  if (p === 0) return `No reserve breach was observed in ${simulations} simulated paths. Real-world risk is not necessarily zero.`;
  if (p === 1) return `Every one of the ${simulations} simulated paths breached the reserve. This is not a guarantee of future outcomes.`;
  return `Estimate from ${simulations} simulated paths. This probability is modelled, not a guarantee.`;
};
const riskEligible = row => Boolean(row?.validation?.within_risk_appetite && row?.candidate?.evaluation?.feasible);
const sortedRecoveryPlans = plans => [...plans].sort((left, right) =>
  Number(riskEligible(right)) - Number(riskEligible(left)) ||
  Number(Boolean(right?.candidate?.evaluation?.feasible)) - Number(Boolean(left?.candidate?.evaluation?.feasible)) ||
  Number(left?.validation?.reserve_breach_probability ?? 1) - Number(right?.validation?.reserve_breach_probability ?? 1)
);


async function callApi(path, options = {}) {
  const response = await fetch(`${API}${path}`, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = body.detail;
    throw new Error(typeof error === "string" ? error : Array.isArray(error) ? error.map(item => item.msg).join("; ") : "Analysis request failed.");
  }
  return body;
}
const jsonPost = (path, payload) => callApi(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });

function Detail({ title = "Advanced diagnostics · verified JSON", value }) {
  return <details className="restoration-details advanced-diagnostics"><summary>{title}</summary><p>Technical provenance for audit and verification. Financial values are outputs of the existing engine.</p><pre>{JSON.stringify(value, null, 2)}</pre></details>;
}
function Metric({ label, value, note }) {
  return <div className="restore-metric"><small>{label}</small><strong>{value}</strong>{note && <span>{note}</span>}</div>;
}
function Module({ eyebrow, title, children, note }) {
  return <section className="restore-workspace premium-workspace"><div className="restore-heading"><div><small>{eyebrow}</small><h3>{title}</h3></div><span className="restore-scope">Verified engine results</span></div>{note && <p className="restore-description">{note}</p>}{children}</section>;
}
function Field({ label, value, onChange, min, max, step = 1, type = "number", disabled = false }) {
  return <label className="restore-field"><span>{label}</span><input type={type} value={value} min={min} max={max} step={step} disabled={disabled} onChange={event => onChange(type === "number" ? Number(event.target.value) : event.target.value)} /></label>;
}

export function LegacyMonthlyWorkspace() {
  const [file, setFile] = useState(null);
  const [session, setSession] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [horizon, setHorizon] = useState(3);
  const [reserve, setReserve] = useState(50000);
  const [revenue, setRevenue] = useState(-20);
  const [cost, setCost] = useState(10);
  const [delay, setDelay] = useState(14);
  const [stress, setStress] = useState(null);
  const [timingReference, setTimingReference] = useState(null);
  const [timingWarning, setTimingWarning] = useState("");
  const [reverse, setReverse] = useState(null);
  const [question, setQuestion] = useState("What do the monthly forecasts and stress tests imply for management?");
  const [answer, setAnswer] = useState(null);
  const invalidateMonthlySession = () => {
    setSession(null); setStress(null); setReverse(null); setAnswer(null);
    setSession(null); setStress(null); setTimingReference(null); setTimingWarning("");
    setReverse(null); setAnswer(null); setError("");
  };
  const updateHorizon = value => { setHorizon(value); invalidateMonthlySession(); };
  const updateReserve = value => { setReserve(value); invalidateMonthlySession(); };
  const updateMonthlyShock = (name, value) => {
    ({ revenue: setRevenue, cost: setCost, delay: setDelay })[name](value);
    setStress(null); setTimingReference(null); setTimingWarning(""); setAnswer(null);
  };
  const run = async (name, fn) => {
    if (busy) return;
    setBusy(name); setError("");
    try { await fn(); } catch (err) { setError(err.message); }
    finally { setBusy(""); }
  };
  const requireId = () => session?.monthly_session_id;
  const params = () => ({ monthly_session_id: requireId(), revenue_change_pct: revenue, cost_change_pct: cost, receivable_delay_days: delay, horizon_months: horizon });
  const canLoad = Boolean(file && Number.isInteger(horizon) && horizon >= 1 && horizon <= 12 && Number.isFinite(reserve) && reserve >= 0);
  const canStress = Number.isFinite(revenue) && revenue >= -100 && revenue <= 200 && Number.isFinite(cost) && cost >= -100 && cost <= 200 && Number.isInteger(delay) && delay >= 0 && delay <= 180;
  const upload = () => run("upload", async () => {
    if (!canLoad) throw new Error("Choose a monthly CSV and enter a valid 1–12 month horizon and non-negative reserve.");
    const data = new FormData(); data.append("file", file); data.append("horizon", String(horizon)); data.append("reserve", String(reserve)); data.append("appetite", "0.05");
    const result = await callApi("/legacy/monthly/import", { method: "POST", body: data });
    setSession(result); setStress(null); setTimingReference(null); setTimingWarning(""); setReverse(null); setAnswer(null);
  });
  const runStress = () => run("stress", async () => {
    if (!canStress) throw new Error("Use valid shocks: revenue/cost -100% to +200%, receivable delay 0–180 whole days.");
    setStress(null); setTimingReference(null); setTimingWarning(""); setAnswer(null);
    const input = params();
    const result = await jsonPost("/legacy/monthly/stress", input);
    setStress(result);
    // A second, engine-calculated scenario holds revenue/cost fixed and removes
    // only the receivable delay. It supports a conditional cash-timing comparison,
    // not a claim that the original decomposition is additive at the minimum.
    if (input.receivable_delay_days > 0) {
      try {
        const reference = await jsonPost("/legacy/monthly/stress", { ...input, receivable_delay_days: 0 });
        setTimingReference(reference);
      } catch (err) {
        setTimingWarning(`The no-delay reference could not be verified: ${err.message}`);
      }
    }
  });
  const timing = stress && timingReference ? compareReceivableTiming(stress, timingReference) : null;
  const reverseLimits = MONTHLY_REVERSE_LIMITS;
  const r = reverse?.reverse_stress;
  return <Module eyebrow="MONTHLY BUSINESS INTELLIGENCE · SEPARATE MODEL" title="Advanced AI Analyst & Stress Lab"
      note="Independent monthly forecasting model. It does not convert 13-week cash events into monthly data or replace the V2 cash forecast.">
    <div className="restore-controls"><label className="restore-field"><span>Monthly business CSV (date, revenue, operating_cost, cash_balance, receivables)</span>
      <input type="file" accept=".csv" disabled={!!busy} onChange={e => { setFile(e.target.files?.[0] || null); invalidateMonthlySession(); }} />
      <a className="sample-data-link" href="/RiskPilot_Harborview_Synthetic_Monthly.csv" download="RiskPilot_Harborview_Synthetic_Monthly.csv">Download independent synthetic monthly demo CSV</a></label>
      <Field label="Monthly forecast horizon (1–12)" value={horizon} onChange={updateHorizon} disabled={!!busy} min={1} max={12}/>
      <Field label="Minimum cash reserve (USD)" value={reserve} onChange={updateReserve} disabled={!!busy} min={0}/>
      <button className="restore-button" disabled={!!busy || !canLoad} onClick={upload}>{busy === "upload" ? "Loading monthly forecast…" : "Load monthly analysis"}</button>
    </div>
    <p className="restore-model-policy">Monthly policy: <strong>5.0% maximum reserve-breach probability</strong> (monthly model setting). The 13-week model has its own independent risk appetite. Cash reserve and forecast horizon above belong only to the monthly model.</p>
    {file && !session && <p className="restore-description" role="status">Load monthly analysis to establish the selected horizon and reserve policy. Changing these inputs requires a new validated session.</p>}
    {session && <><p className="restore-status">Monthly dataset validated · {session.periods} observations · independent {session.forecast_horizon_months}-month forecast</p>
      <div className="restore-controls"><Field label="Revenue shock (%)" value={revenue} onChange={v => updateMonthlyShock("revenue", v)} disabled={!!busy} min={-100} max={200}/>
        <Field label="Operating cost shock (%)" value={cost} onChange={v => updateMonthlyShock("cost", v)} disabled={!!busy} min={-100} max={200}/>
        <Field label="Receivable delay (days)" value={delay} onChange={v => updateMonthlyShock("delay", v)} disabled={!!busy} min={0} max={180}/>
        <button className="restore-button" disabled={!!busy || !canStress} onClick={runStress}>{busy === "stress" ? "Calculating verified scenarios…" : "Run monthly stress & decomposition"}</button>
        <button className="restore-button outline" disabled={!!busy} onClick={() => run("reverse", async () => {
          setReverse(null); setAnswer(null);
          setReverse(await jsonPost("/legacy/monthly/reverse-stress", { monthly_session_id: requireId(), target_min_cash: reserve, horizon_months: horizon,
            max_revenue_decline_pct: reverseLimits.revenuePct, max_cost_increase_pct: reverseLimits.costPct, max_receivable_delay_days: reverseLimits.delayDays }));
        })}>{busy === "reverse" ? "Calculating…" : "Run reverse stress boundary"}</button>
      </div>
      {stress && <div className="restore-results"><h4>Monthly Stress Result</h4><div className="restore-metrics">
        <Metric label="Baseline minimum cash" value={currency(stress.scenario?.baseline_min_cash)}/><Metric label="Stressed minimum cash" value={currency(stress.scenario?.stressed_min_cash)}/>
        <Metric label="End-cash impact" value={currency(stress.scenario?.end_cash_impact)}/><Metric label="Largest baseline-to-stress gap" value={currency(stress.scenario?.peak_liquidity_gap)} note={`Month ${stress.scenario?.peak_liquidity_gap_period ?? "unknown"} · not the reserve shortfall`}/>
      </div>
      <h4>Engine shock decomposition</h4>
      <p className="restore-description">End-cash impact is measured at the forecast horizon. Engine peak contributions are measured at the combined scenario's largest gap period, not at each driver's own worst cash point and not at the scenario minimum.</p>
      <div className="restore-table"><table><thead><tr><th>Driver</th><th>End-cash impact</th><th>Contribution at combined peak-gap month</th></tr></thead><tbody>{(stress.decomposition?.drivers || []).map((d, i) => <tr key={i}><td>{({revenue_shock: "Revenue shock", cost_shock: "Operating cost shock", receivable_delay: "Receivable timing shift"})[d.driver] || d.driver}</td><td>{currency(d.end_cash_impact)}</td><td>{currency(d.peak_liquidity_impact)}</td></tr>)}</tbody></table></div>
      {Number(delay) > 0 && <section className="monthly-timing-evidence"><h4>Receivables Timing Impact · Engine-Verified Comparison</h4>
        <p className="restore-description">Both scenarios use the same uploaded monthly data, revenue shock, cost shock and horizon. Only receivable delay changes: {delay} days versus 0 days. This is a controlled scenario difference, not an isolated-driver attribution.</p>
        {timing ? <><div className="restore-metrics">
          <Metric label="Minimum cash · no delay" value={currency(timing.referenceMinimumCash)}/>
          <Metric label={`Minimum cash · ${delay}-day delay`} value={currency(timing.delayedMinimumCash)}/>
          <Metric label="Change in minimum cash" value={currency(timing.minimumCashDifference)} note="Delayed scenario minus no-delay scenario"/>
          <Metric label="Change in end cash" value={currency(timing.endCashDifference)}/>
        </div><details className="restoration-details"><summary>View month-by-month cash timing differences</summary><div className="restore-table"><table><thead><tr><th>Month</th><th>No-delay stressed cash</th><th>Delayed stressed cash</th><th>Difference</th></tr></thead><tbody>{timing.trajectory.map(row => <tr key={row.period}><td>{row.period}</td><td>{currency(row.noDelayCash)}</td><td>{currency(row.delayedCash)}</td><td>{currency(row.cashDifference)}</td></tr>)}</tbody></table></div></details></> : <p role="status" className="restore-description">{timingWarning || "Calculating independent no-delay comparison…"}</p>}
        <p className="restore-description">A receivable timing change can lower cash during the horizon while having no effect on end cash if the delayed money is collected before the horizon ends.</p>
      </section>}
      <Detail value={stress}/></div>}
      {r && <div className="restore-results"><h4>Reverse Stress Boundary · Monthly</h4>
        <p className="restore-description">Individual breakpoints test up to 30% revenue decline, 30% cost increase and 90 days of receivable delay. A breakpoint that is not reached within those ranges is not proof that the business can withstand unlimited stress.</p>
        <div className="restore-metrics">
          <Metric label="Baseline minimum cash" value={currency(r.baseline_min_cash)}/>
          <Metric label="Revenue failure breakpoint" value={reverseBreakpoint(r.revenue_decline_breakpoint, reverseLimits.revenuePct, "%", r.baseline_breached)}/>
          <Metric label="Cost failure breakpoint" value={reverseBreakpoint(r.cost_increase_breakpoint, reverseLimits.costPct, "%", r.baseline_breached)}/>
          <Metric label="Delay failure breakpoint" value={reverseBreakpoint(r.receivable_delay_breakpoint_days, reverseLimits.delayDays, "days", r.baseline_breached)}/>
        </div>
        {r.nearest_combined_failure ? <p className="restore-status">The model identified a combined-shock failure within the configured search grid. Review Advanced Diagnostics for the exact engine result.</p> : <p className="restore-model-policy">No combined-shock failure was identified in the configured grid; this does not guarantee safety outside the search range.</p>}
        <Detail value={reverse}/></div>}
      <div className="restore-results"><h4>Ask the original RiskPilot AI Risk Analyst</h4>
        <textarea className="restore-question" rows={3} disabled={!!busy} value={question} onChange={e => { setQuestion(e.target.value); setAnswer(null); }} placeholder="Ask a free-form management question about the uploaded monthly data." />
        <button className="restore-button" disabled={!!busy || !question.trim()} onClick={() => run("agent", async () => {
          setAnswer(null);
          setAnswer(await jsonPost("/legacy/monthly/agent", { monthly_session_id: requireId(), question }));
        })}>{busy === "agent" ? "Running monthly AI analyst…" : "Run verified monthly AI analysis"}</button>
        {answer && <><div className="restore-answer"><AiMarkdown text={answer.answer}/></div><div className="monthly-ai-provenance"><strong>AI tool provenance · reported by runtime</strong>
          {Array.isArray(answer.tools_used) && answer.tools_used.length > 0 ? <ol>{answer.tools_used.map((tool, index) => <li key={`${tool}-${index}`}><span className="monthly-tool-step">{index + 1}</span><span>{tool}</span><span className="monthly-provenance-note">Tool invoked in this request</span></li>)}</ol> : <p>No finance-tool calls were reported for this request. Do not treat the response as tool-verified without additional evidence.</p>}
          <small>Only runtime-reported calls are shown. This is not private model reasoning and does not imply each numerical statement was independently verified.</small>
        </div></>}
      </div>
    </>}
    {error && <div className="restore-error" role="alert">{error}</div>}
  </Module>;
}

export function RecoveryOptimizerWorkspace({ scenarioId, importedMode, customerSessionId }) {
  const [params, setParams] = useState({ max_revenue_improvement_pct: 20, max_cost_reduction_pct: 15, max_receivable_acceleration_days: 14, max_external_liquidity: 100000, apply_to_committed_receivables: false });
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [manual, setManual] = useState({ revenue_improvement_pct: 0, cost_reduction_pct: 0, receivable_acceleration_days: 0, external_liquidity: 0 });
  const [manualPreset, setManualPreset] = useState("custom");
  const [manualResult, setManualResult] = useState(null);
  const [manualBusy, setManualBusy] = useState(false);
  const [manualError, setManualError] = useState("");
  const [selectedCompareIndex, setSelectedCompareIndex] = useState(0);
  const [aiQuestion, setAiQuestion] = useState("What trade-offs should management consider between these recovery plans, and what should we validate before acting?");
  const [aiInsight, setAiInsight] = useState(null);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiError, setAiError] = useState("");
  useEffect(() => { setResult(null); setError(""); setManualResult(null); setManualError(""); setManualPreset("custom"); setAiInsight(null); setAiError(""); }, [scenarioId, importedMode, customerSessionId]);
  const update = (name, value) => { setParams(old => ({ ...old, [name]: value })); setResult(null); setManualResult(null); setAiInsight(null); setAiError(""); };
  const changeManual = (field, value) => {
    setManual(prev => ({ ...prev, [field]: value }));
    setManualPreset("custom"); setManualResult(null); setManualError(""); setAiInsight(null); setAiError("");
  };
  const choosePreset = key => {
    if (!result?.constraints) return;
    const caps = result.constraints;
    const revenue = caps.revenue_improvement?.enabled ? Number(caps.revenue_improvement.max_improvement_pct) : 0;
    const costs = caps.cost_reduction?.enabled ? Number(caps.cost_reduction.max_reduction_pct) : 0;
    const collections = caps.receivable_acceleration?.enabled ? Number(caps.receivable_acceleration.max_acceleration_days) : 0;
    const funding = caps.external_liquidity?.enabled ? Number(caps.external_liquidity.max_amount) : 0;
    const factor = key === "balanced" ? 0.5 : 1;
    setManual({
      revenue_improvement_pct: ["revenue", "balanced"].includes(key) ? Number((revenue * factor).toFixed(2)) : 0,
      cost_reduction_pct: ["costs", "balanced"].includes(key) ? Number((costs * factor).toFixed(2)) : 0,
      receivable_acceleration_days: ["collections", "balanced"].includes(key) ? Math.floor(collections * factor) : 0,
      external_liquidity: ["funding", "balanced"].includes(key) ? Number((funding * factor).toFixed(2)) : 0,
    });
    setManualPreset(key); setManualResult(null); setManualError(""); setAiInsight(null); setAiError("");
  };
  const validateManual = async () => {
    setManualBusy(true); setManualError(""); setManualResult(null); setAiInsight(null); setAiError("");
    try {
      const response = await jsonPost("/recovery/validate-plan", {
        ...params, ...manual, scenario_id: scenarioId,
        customer_session_id: importedMode ? customerSessionId : null,
      });
      setManualResult(response);
    } catch (err) { setManualError(err.message); }
    finally { setManualBusy(false); }
  };

  const submit = async () => {
    setBusy(true); setError(""); setResult(null); setManualResult(null); setManualError(""); setAiInsight(null); setAiError("");
    try {
      const response = await jsonPost("/recovery/optimise", {
        ...params, scenario_id: scenarioId,
        customer_session_id: importedMode ? customerSessionId : null,
      });
      setResult(response);
      setSelectedCompareIndex(0);
      // Stage a balanced starting point only. Results always require validation.
      const caps = response.constraints || {};
      setManual({
        revenue_improvement_pct: caps.revenue_improvement?.enabled ? Number((Number(caps.revenue_improvement.max_improvement_pct) * 0.5).toFixed(2)) : 0,
        cost_reduction_pct: caps.cost_reduction?.enabled ? Number((Number(caps.cost_reduction.max_reduction_pct) * 0.5).toFixed(2)) : 0,
        receivable_acceleration_days: caps.receivable_acceleration?.enabled ? Math.floor(Number(caps.receivable_acceleration.max_acceleration_days) * 0.5) : 0,
        external_liquidity: caps.external_liquidity?.enabled ? Number((Number(caps.external_liquidity.max_amount) * 0.5).toFixed(2)) : 0,
      });
      setManualPreset("balanced");
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };
  const allowed = result?.constraints;
  const shortlist = sortedRecoveryPlans(result?.shortlist || []);
  const acceptable = shortlist.filter(riskEligible);
  const selectedOptimisedPlan = shortlist[selectedCompareIndex] || shortlist[0] || null;
  const recoveryComparison = manualResult && selectedOptimisedPlan
    ? buildRecoveryComparison(selectedOptimisedPlan, manualResult)
    : null;
  const evidenceFingerprint = JSON.stringify({
    scenarioId, customerSessionId, params, manualResult,
    reference: selectedOptimisedPlan?.candidate?.plan || null,
  });
  const generateAiInsight = async () => {
    if (!manualResult || !selectedOptimisedPlan || !aiQuestion.trim()) return;
    const requestFingerprint = evidenceFingerprint;
    setAiInsight(null); setAiError(""); setAiBusy(true);
    try {
      const response = await jsonPost("/recovery/decision-insight", {
        ...params, ...manual, scenario_id: scenarioId,
        customer_session_id: importedMode ? customerSessionId : null,
        reference_plan: selectedOptimisedPlan.candidate.plan,
        question: aiQuestion.trim(),
      });
      setAiInsight({ ...response, fingerprint: requestFingerprint });
    } catch (err) { setAiError(err.message || "AI insight unavailable."); }
    finally { setAiBusy(false); }
  };
  return <Module eyebrow="RECOVERY DECISION INTELLIGENCE · 13-WEEK MODEL" title="Management Recovery Optimiser"
    note={importedMode
      ? "Select realistic intervention limits. Cash evidence stays unchanged; only explicitly eligible actions are modelled."
      : "Optimisation uses the current scenario's frozen, verified recovery constraints. No demo operating limits are silently substituted."}>
    {importedMode ? <div className="restore-controls" aria-label="Management recovery constraints">
      <Field label="Maximum revenue improvement (%)" value={params.max_revenue_improvement_pct} onChange={v => update("max_revenue_improvement_pct", v)} min={0} max={100}/>
      <Field label="Maximum cost reduction (%)" value={params.max_cost_reduction_pct} onChange={v => update("max_cost_reduction_pct", v)} min={0} max={100}/>
      <Field label="Maximum collection acceleration (days)" value={params.max_receivable_acceleration_days} onChange={v => update("max_receivable_acceleration_days", v)} min={0} max={90}/>
      <Field label="Maximum funding available ($)" value={params.max_external_liquidity} onChange={v => update("max_external_liquidity", v)} min={0} max={50000000}/>
      <label className="restore-check"><input type="checkbox" checked={params.apply_to_committed_receivables} onChange={e => update("apply_to_committed_receivables", e.target.checked)}/> Authorise eligible committed receivable timing changes</label>
    </div> : <p className="restore-description">{scenarioId === "harborview_synthetic"
        ? "Synthetic walkthrough: modelled sales, modelled operating costs, eligible customer collections and external liquidity have non-zero constraints."
        : "The original scenario constraints may prohibit some operating levers. The optimiser does not invent eligibility."}</p>}
    <div className="restore-actions"><button type="button" className="restore-button" disabled={busy || (importedMode && !customerSessionId)} onClick={submit}>
      {busy ? "Searching verified recovery combinations…" : "Optimise & validate recovery plans"}
    </button></div>
    {error && <div className="restore-error" role="alert">{error}</div>}
    {result && <div className="restore-results" aria-live="polite">
      <div className="restore-metrics">
        <Metric label="Search candidates" value={number(result.search?.candidates_evaluated)}/>
        <Metric label="Unique shortlisted plans" value={number(result.unique_plan_count ?? shortlist.length)} note={result.duplicate_objectives ? `${result.duplicate_objectives} objective(s) returned an existing plan` : "Distinct plans only"}/>
        <Metric label="Deterministic status" value={result.search?.deterministic_status || "Unavailable"}/>
        <Metric label="Best attainable cash minimum" value={currency(result.search?.best_attainable_min_cash)}/>
      </div>
      {allowed && <div className="constraint-overview"><strong>Verified intervention limits</strong>
        <span>Revenue: {allowed.revenue_improvement?.enabled ? `${allowed.revenue_improvement.max_improvement_pct}%` : "Not enabled"}</span>
        <span>Costs: {allowed.cost_reduction?.enabled ? `${allowed.cost_reduction.max_reduction_pct}%` : "Not enabled"}</span>
        <span>Collections: {allowed.receivable_acceleration?.enabled ? `${allowed.receivable_acceleration.max_acceleration_days} days` : "Not enabled"}</span>
        <span>Funding: {allowed.external_liquidity?.enabled ? currency(allowed.external_liquidity.max_amount) : "Not enabled"}</span>
      </div>}
      <p className="restore-description">{result.notice}</p>
      <div className={acceptable.length ? "workflow-notice success" : "workflow-notice warning"} role="status">
        {acceptable.length
          ? `${acceptable.length} distinct shortlisted plan(s) meet the modelled management risk appetite. Validate assumptions before action.`
          : "No shortlisted plan currently meets the modelled risk appetite. Deterministic reserve feasibility alone is not sufficient."}
      </div>
      {shortlist.length === 1 && result.duplicate_objectives > 0 && <p className="restore-description">The search objectives converged to one identical recovery plan. It is intentionally shown once.</p>}
      <p className="restore-description">Plans are ordered by modelled management-risk eligibility first, not by the optimiser's deterministic search objective. Search labels remain visible for audit; they are not recommendations to proceed.</p>
      <div className="restore-option-grid">{shortlist.map((row, i) => {
        const plan = row.candidate?.plan || {};
        const evaluation = row.candidate?.evaluation || {};
        const validation = row.validation || {};
        return <article className="restore-option" key={`${plan.external_liquidity}-${plan.revenue_improvement_pct}-${plan.cost_reduction_pct}-${plan.receivable_acceleration_days}-${i}`}>
          <span className={riskEligible(row) ? "recovery-plan-status eligible" : "recovery-plan-status ineligible"}>{riskEligible(row) ? "Within modelled appetite" : "Exceeds risk appetite"}</span>
          <strong>{riskEligible(row) ? `Risk-eligible option · ${row.name}` : `${row.name} · deterministic objective only`}</strong>
          {row.also_selected_for?.length > 0 && <small>Also selected for: {row.also_selected_for.join(", ")}</small>}
          <div className="restore-plan-kpis"><Metric label="External funding" value={currency(plan.external_liquidity)}/><Metric label="Minimum cash" value={currency(evaluation.resulting_min_cash)}/></div>
          <p className="restore-plan-levers">Revenue improvement: <b>{planAction(plan.revenue_improvement_pct, "%", allowed?.revenue_improvement)}</b><br/>Cost reduction: <b>{planAction(plan.cost_reduction_pct, "%", allowed?.cost_reduction)}</b><br/>Collections accelerated: <b>{planAction(plan.receivable_acceleration_days, " days", allowed?.receivable_acceleration)}</b></p>
          <div className={validation.within_risk_appetite ? "restore-validation valid" : "restore-validation invalid"}>
            Simulated breach risk: <b>{percent(validation.reserve_breach_probability)}</b><br/>
            Within appetite: <b>{validation.within_risk_appetite ? "Yes" : "No"}</b><br/>
            <small>{riskDescription(validation)}</small>
          </div>
          <Detail title="Advanced plan diagnostics · JSON" value={row}/>
        </article>;
      })}</div>
      <section className="recovery-strategy-explorer" aria-label="Custom recovery strategy explorer">
        <div className="recovery-strategy-head"><div><h4>Recovery Strategy Explorer</h4>
          <p>Choose a management intervention mix, edit the proposed amounts, then validate it with the existing 13-week recovery engines. Presets stage inputs only and never manufacture results.</p></div>
        </div>
        <div className="recovery-strategy-presets" role="group" aria-label="Plan presets">
          {[["balanced", "Balanced"], ["revenue", "Revenue-led"], ["costs", "Cost-led"], ["collections", "Collections-led"], ["funding", "Funding-led"]].map(([key,label]) =>
            <button type="button" key={key} aria-pressed={manualPreset === key} className={manualPreset === key ? "active" : ""} onClick={() => choosePreset(key)}>{label}</button>)}
        </div>
        <div className="restore-controls">
          <Field label="Revenue improvement (%)" min={0} max={allowed?.revenue_improvement?.enabled ? allowed.revenue_improvement.max_improvement_pct : 0} step={1} value={manual.revenue_improvement_pct} disabled={!allowed?.revenue_improvement?.enabled} onChange={v => changeManual("revenue_improvement_pct", v)}/>
          <Field label="Cost reduction (%)" min={0} max={allowed?.cost_reduction?.enabled ? allowed.cost_reduction.max_reduction_pct : 0} step={1} value={manual.cost_reduction_pct} disabled={!allowed?.cost_reduction?.enabled} onChange={v => changeManual("cost_reduction_pct", v)}/>
          <Field label="Collections accelerated (days)" min={0} max={allowed?.receivable_acceleration?.enabled ? allowed.receivable_acceleration.max_acceleration_days : 0} value={manual.receivable_acceleration_days} disabled={!allowed?.receivable_acceleration?.enabled} onChange={v => changeManual("receivable_acceleration_days", v)}/>
          <Field label="External funding ($)" min={0} max={allowed?.external_liquidity?.enabled ? allowed.external_liquidity.max_amount : 0} value={manual.external_liquidity} disabled={!allowed?.external_liquidity?.enabled} onChange={v => changeManual("external_liquidity", v)}/>
        </div>
        <div className="restore-actions"><button type="button" className="restore-button" disabled={manualBusy || busy} onClick={validateManual}>
          {manualBusy ? "Validating selected recovery plan…" : "Validate custom recovery plan"}
        </button></div>
        {manualPreset !== "custom" && !manualResult && <p className="restore-description" role="status">{manualPreset === "balanced" ? "Balanced starting inputs" : `${manualPreset} strategy inputs`} are staged only. Select Validate custom recovery plan to request an engine result.</p>}
        {manualError && <div className="restore-error" role="alert">{manualError}</div>}
        {manualResult && <div className="recovery-manual-result" aria-live="polite">
          <span className={manualResult.validation?.within_risk_appetite && manualResult.evaluation?.feasible ? "recovery-plan-status eligible" : "recovery-plan-status ineligible"}>
            {manualResult.validation?.within_risk_appetite && manualResult.evaluation?.feasible ? "Within modelled appetite" : "Exceeds risk appetite"}
          </span>
          <div className="restore-plan-kpis"><Metric label="Minimum cash" value={currency(manualResult.evaluation?.resulting_min_cash)}/>
            <Metric label="Simulated breach probability" value={percent(manualResult.validation?.reserve_breach_probability)}/>
            <Metric label="Management risk appetite" value={percent(manualResult.validation?.max_acceptable_breach_probability)}/>
            <Metric label="Deterministic feasibility" value={manualResult.evaluation?.feasible ? "Yes" : "No"}/></div>
          <p className="restore-description">{riskDescription(manualResult.validation)} Custom interventions have been evaluated against the current scenario constraints without altering the baseline.</p>
          <Detail title="Advanced custom plan diagnostics · JSON" value={manualResult}/>
        </div>}
        {recoveryComparison && <section className="recovery-comparison" aria-label="Compare custom recovery against optimised strategies">
          <div className="recovery-comparison-heading">
            <div><h4>Custom plan vs optimised strategy</h4>
              <p>Compare the two verified plan outputs for the current scenario and constraint set. No financial forecast is recalculated in this table.</p></div>
            <label className="restore-field"><span>Optimised reference</span>
              <select value={selectedCompareIndex} onChange={e => { setSelectedCompareIndex(Number(e.target.value)); setAiInsight(null); setAiError(""); }}>
                {shortlist.map((row, i) => <option key={`${row.name}-${i}`} value={i}>{row.name}{riskEligible(row) ? " · within appetite" : " · exceeds appetite"}</option>)}
              </select>
            </label>
          </div>
          <div className="restore-table recovery-comparison-table"><table><thead><tr>
            <th>Decision measure</th><th>{selectedOptimisedPlan.name} · optimised</th><th>Custom · validated</th><th>Custom minus optimised</th>
          </tr></thead><tbody>
            {recoveryComparison.map(row => <tr key={row.key}><td>{row.label}</td>
              <td>{row.optimisedLabel}</td><td>{row.customLabel}</td><td>{row.deltaLabel}</td></tr>)}
          </tbody></table></div>
          <p className="restore-description">Differences compare separately validated model outputs, not realised cash savings. Probability differences are percentage points, not proof of causal risk reduction. Both results retain their original evidence and uncertainty assumptions.</p>
          <section className="recovery-ai-insight" aria-label="AI management decision insight">
            <div className="recovery-ai-insight-head">
              <div><small>RISK PILOT AI · VERIFIED FINANCIAL EVIDENCE</small>
                <h4>Management Decision Insight</h4>
                <p>Ask AI to interpret the trade-offs between your validated plan and the optimised reference. RiskPilot first revalidates both plans with the existing financial engines.</p></div>
              <span className="recovery-ai-scope">13-week · evidence-grounded</span>
            </div>
            <label className="recovery-ai-question"><span>Management question</span>
              <textarea rows={2} maxLength={500} disabled={aiBusy} value={aiQuestion} onChange={e => { setAiQuestion(e.target.value); setAiInsight(null); setAiError(""); }} />
            </label>
            <div className="recovery-ai-actions">
              <button type="button" className="restore-button" disabled={aiBusy || manualBusy || busy || !aiQuestion.trim()} onClick={generateAiInsight}>
                {aiBusy ? "Revalidating plans and generating AI insight…" : "✦ Generate AI Decision Insight →"}
              </button>
              <small>Actual AI generation requires configured credentials. No static or fabricated AI answer is shown.</small>
            </div>
            {aiError && <div className="restore-error" role="alert">{aiError}</div>}
            {aiBusy && <p className="restore-description" role="status">Step 1: Revalidate plan evidence → Step 2: Compare outcomes → Step 3: Ask AI to explain the decision trade-offs.</p>}
            {aiInsight?.fingerprint === evidenceFingerprint && <div className="recovery-ai-result" aria-live="polite">
              <div className="recovery-ai-result-title"><span>✦ AI-generated management interpretation</span><span className="recovery-ai-grounded">Engine-revalidated inputs</span></div>
              <AiMarkdown text={aiInsight.answer} />
              <div className="recovery-ai-trace" aria-label="Observed AI decision workflow">
                <strong>Verified execution path</strong>
                <ol>{(aiInsight.verification_steps || []).map((step, index) => <li key={index}><span aria-hidden="true">✓</span>{step}</li>)}</ol>
              </div>
              <p>Financial figures come from the existing Recovery Optimiser and Recovery Validation engines. AI interprets verified outputs; it does not calculate cash forecasts or probabilities.</p>
              <details className="restoration-details advanced-diagnostics"><summary>View verified evidence supplied to AI · JSON</summary><pre>{JSON.stringify(aiInsight.verified_evidence, null, 2)}</pre></details>
            </div>}
          </section>
        </section>}
      </section>
      <Detail title="Advanced search diagnostics · JSON" value={result}/>
    </div>}
  </Module>;
}

export function HistoryEvidenceWorkspace({ scenarioId, customerSessionId, importedMode, historyKey }) {
  const [history, setHistory] = useState([]), [prior, setPrior] = useState(""), [current, setCurrent] = useState(""), [comparison, setComparison] = useState(null);
  const [weekly, setWeekly] = useState(null), [selectedWeek, setSelectedWeek] = useState(1);
  const [busy, setBusy] = useState(""), [error, setError] = useState("");
  const [actualFile, setActualFile] = useState(null);
  const [actualSnapshot, setActualSnapshot] = useState("");
  const [actualThrough, setActualThrough] = useState(new Date().toISOString().slice(0, 10));
  const [actualResult, setActualResult] = useState(null);
  const [monitoring, setMonitoring] = useState(null);
  const session = customerSessionId ? `?customer_session_id=${encodeURIComponent(customerSessionId)}` : "";
  const refresh = async () => { const data = await callApi(`/forecast/history?history_key=${encodeURIComponent(historyKey)}`); setHistory(data.history || []); };
  useEffect(() => { refresh().catch(err => setError(err.message)); }, [historyKey]);
  useEffect(() => { setWeekly(null); setComparison(null); setError(""); }, [scenarioId, customerSessionId]);
  const run = async (name, cb) => { setBusy(name); setError(""); try { await cb(); } catch (err) { setError(err.message); } finally { setBusy(""); } };
  const save = () => run("save", async () => { const data = await jsonPost("/forecast/history/save", { history_key: historyKey, scenario_id: scenarioId, customer_session_id: customerSessionId || null }); setHistory(data.history || []); setComparison(null); });
  const compare = () => run("compare", async () => setComparison(await jsonPost("/forecast/history/compare", { history_key: historyKey, prior_snapshot_id: prior, current_snapshot_id: current })));
  const weeks = () => run("weeks", async () => setWeekly(await callApi(`/evidence/weeks/${encodeURIComponent(scenarioId)}${session}`)));
  const reviewMonitoring = () => run("monitoring", async () => setMonitoring(await callApi(`/monitoring/${encodeURIComponent(scenarioId)}${session}`)));
  const reconcile = () => run("actual", async () => {
    if (!actualFile || !actualSnapshot) throw new Error("Select a saved snapshot and actual cash CSV.");
    const form = new FormData();
    form.append("file", actualFile); form.append("history_key", historyKey);
    form.append("snapshot_id", actualSnapshot); form.append("through_date", actualThrough);
    setActualResult(await callApi("/forecast/history/actuals", { method: "POST", body: form }));
  });
  const download = async (format) => run(format, async () => {
    const response = await fetch(`${API}/reports/${encodeURIComponent(scenarioId)}/${format === "pdf" ? "management.pdf" : "audit.json"}${session}`, { cache: "no-store" });
    if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail || "Report export failed."); }
    const blob = await response.blob(), url = URL.createObjectURL(blob);
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = format === "pdf" ? "riskpilot-management-brief.pdf" : "riskpilot-verified-audit.json";
    document.body.appendChild(anchor); anchor.click(); anchor.remove(); URL.revokeObjectURL(url);
  });
  const activeWeek = weekly?.weeks?.find(item => Number(item.week) === Number(selectedWeek));
  return <Module eyebrow="FORECAST GOVERNANCE · 13-WEEK AUDIT" title="Forecast Monitoring, Evidence & Management Reports"
    note="Save independently calculated snapshots, compare changes in forecast evidence, inspect the weekly cash-event allocations and download the original RiskPilot management report. History is local, in-memory and expires after one hour.">
    <div className="restore-actions"><button className="restore-button" disabled={!!busy} onClick={save}>{busy === "save" ? "Saving…" : "Save current forecast snapshot"}</button>
      <button className="restore-button outline" disabled={!!busy} onClick={weeks}>{busy === "weeks" ? "Reading…" : "Inspect 13-week evidence"}</button>
      <button className="restore-button outline" disabled={!!busy} onClick={reviewMonitoring}>{busy === "monitoring" ? "Reading…" : "Review management monitoring"}</button>
      <button className="restore-button outline" disabled={!!busy} onClick={() => download("pdf")}>Download Management Brief PDF</button>
      <button className="restore-button outline" disabled={!!busy} onClick={() => download("json")}>Download Verified Audit JSON</button>
    </div>
    {history.length > 0 && <div className="restore-results"><h4>Saved forecast snapshots ({history.length})</h4><div className="restore-table"><table><thead><tr><th>Saved at</th><th>Forecast start</th><th>Minimum cash</th><th>Closing cash</th><th>Source basis</th></tr></thead><tbody>
      {history.map(item => <tr key={item.snapshot_id}><td>{new Date(item.created_at).toLocaleString()}</td><td>{item.start_date}</td><td>{currency(item.minimum_cash)}</td><td>{currency(item.closing_cash)}</td><td title={item.basis}>{item.basis.slice(0, 12)}…</td></tr>)}
    </tbody></table></div><div className="restore-controls"><label className="restore-field"><span>Prior snapshot</span><select value={prior} onChange={e => setPrior(e.target.value)}><option value="">Choose baseline</option>{history.map(x => <option key={x.snapshot_id} value={x.snapshot_id}>{new Date(x.created_at).toLocaleTimeString()} · {x.start_date}</option>)}</select></label>
      <label className="restore-field"><span>Current snapshot</span><select value={current} onChange={e => setCurrent(e.target.value)}><option value="">Choose comparison</option>{history.map(x => <option key={x.snapshot_id} value={x.snapshot_id}>{new Date(x.created_at).toLocaleTimeString()} · {x.start_date}</option>)}</select></label>
      <button className="restore-button" disabled={!!busy || !prior || !current || prior === current} onClick={compare}>Compare verified snapshots</button></div>
      {comparison && <><div className="restore-metrics"><Metric label="Minimum cash change" value={currency(comparison.comparison?.minimum_cash_change)}/><Metric label="Closing cash change" value={currency(comparison.comparison?.closing_cash_change)}/><Metric label="Opening cash change" value={currency(comparison.comparison?.opening_cash_change)}/><Metric label="Same forecast evidence" value={comparison.comparison?.same_forecast_basis ? "Yes" : "No"}/></div><Detail value={comparison}/></>}
    </div>}
    {monitoring && <div className="restore-results"><h4>Active actions & monitoring</h4>
      <p className="restore-description">{monitoring.notice}</p>
      <Detail title="Current actions and monitoring triggers" value={{ actions: monitoring.actions, monitoring: monitoring.monitoring }}/>
    </div>}
    {history.length > 0 && <div className="restore-results"><h4>Forecast vs Actual · Explicit evidence reconciliation</h4>
      <p className="restore-description">Upload an observed cash CSV with actual_id, date, amount, direction and source_reference. Include forecast_event_id only when a verified reference connects the actual to a planned event. Unlinked receipts are treated as new events.</p>
      <div className="restore-controls"><label className="restore-field"><span>Saved forecast to reconcile</span><select value={actualSnapshot} onChange={e => setActualSnapshot(e.target.value)}><option value="">Choose forecast</option>{history.map(x => <option key={x.snapshot_id} value={x.snapshot_id}>{x.start_date} · {x.snapshot_id.slice(0, 19)}</option>)}</select></label>
      <Field type="date" label="Compare observed cash through" value={actualThrough} onChange={setActualThrough}/>
      <label className="restore-field"><span>Actual cash evidence CSV</span><input type="file" accept=".csv" onChange={e => setActualFile(e.target.files?.[0] || null)} /></label>
      <button className="restore-button" disabled={!!busy || !actualSnapshot || !actualFile} onClick={reconcile}>Compare forecast with actual evidence</button></div>
      {actualResult && <><div className="restore-metrics"><Metric label="Actual inflows" value={currency(actualResult.comparison?.actual_inflows)}/><Metric label="Actual outflows" value={currency(actualResult.comparison?.actual_outflows)}/><Metric label="Actual net cash" value={currency(actualResult.comparison?.actual_net_cash)}/><Metric label="Evidence variances" value={number(actualResult.comparison?.variances?.length)}/></div><Detail title="Inspect timing, amounts and missing events" value={actualResult}/></>}
    </div>}
    {weekly && <div className="restore-results"><div className="restore-controls"><label className="restore-field"><span>Week of forecast</span><select value={selectedWeek} onChange={e => setSelectedWeek(Number(e.target.value))}>{weekly.weeks.map(x => <option key={x.week} value={x.week}>Week {x.week}</option>)}</select></label></div>
      <Metric label="Verified week closing cash" value={currency(activeWeek?.closing_cash)}/>
      <div className="restore-table"><table><thead><tr><th>Cash event</th><th>Evidence</th><th>Source</th><th>Date</th><th>Included cash effect</th></tr></thead><tbody>{(activeWeek?.events || []).map((e, i) => <tr key={`${e.event_id}-${i}`}><td>{e.event_id}<small>{e.category}</small></td><td>{e.source_type}</td><td>{e.source_reference || "—"}</td><td>{e.effective_cash_date}</td><td>{currency(e.signed_cash_effect)}</td></tr>)}</tbody></table></div>
      {activeWeek?.events?.length === 0 && <p>No events were allocated to this week.</p>}
    </div>}
    {error && <div className="restore-error" role="alert">{error}</div>}
  </Module>;
}
