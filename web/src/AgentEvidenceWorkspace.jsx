import React, { useEffect, useState } from "react";

const SECTIONS = [
  { id: "position", title: "Liquidity position", question: "Explain our liquidity position, minimum headroom and reserve-breach risk using verified figures." },
  { id: "evidence", title: "Cash evidence", question: "Which cash drivers and evidence classifications most influence our 13-week position?" },
  { id: "recovery", title: "Recovery adequacy", question: "Evaluate the available recovery evidence. Distinguish current-plan feasibility from any conditional extra liquidity buffer." },
  { id: "monitoring", title: "Actions & monitoring", question: "Which management actions and monitoring triggers should we prioritise, based only on the verified evidence?" },
];

const dollars = value => value === null || value === undefined ? "—" : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value);
const percentage = value => value === null || value === undefined ? "—" : `${(Number(value) * 100).toFixed(1)}%`;
const present = value => value === null || value === undefined ? "Not available" : typeof value === "boolean" ? (value ? "Yes" : "No") : typeof value === "object" ? JSON.stringify(value) : String(value);

function NumberCard({ label, value, note }) {
  return <div className="evidence-number-card"><small>{label}</small><b>{value}</b>{note && <span>{note}</span>}</div>;
}

function PairRows({ object, labels = {} }) {
  if (!object || typeof object !== "object") return <p className="muted-note">No evidence returned for this field.</p>;
  return <div className="evidence-pair-list">{Object.entries(object).map(([key, value]) => (
    <div key={key}><span>{labels[key] || key.replace(/_/g, " ")}</span><strong>{present(value)}</strong></div>
  ))}</div>;
}

function EvidenceContent({ section }) {
  const evidence = section?.evidence;
  if (!evidence?.available) return <p className="muted-note">No verified evidence is available for this section.</p>;
  if (section.id === "position") {
    const pos = evidence.position || {};
    const uncertainty = evidence.baseline_uncertainty;
    return <>
      <div className="evidence-number-grid">
        <NumberCard label="Current cash" value={dollars(pos.current_cash)} />
        <NumberCard label="Management reserve" value={dollars(pos.management_reserve)} />
        <NumberCard label="Minimum closing cash" value={dollars(pos.minimum_closing_cash)} note={`Week ${pos.minimum_closing_cash_week ?? "—"}`} />
        <NumberCard label="Minimum headroom" value={dollars(pos.minimum_headroom)} />
      </div>
      <h4>Baseline risk before recovery</h4>
      {uncertainty ? <div className="evidence-number-grid">
        <NumberCard label="Reserve-breach probability" value={percentage(uncertainty.reserve_breach_probability)} />
        <NumberCard label="Management appetite" value={percentage(uncertainty.maximum_acceptable_breach_probability)} />
        <NumberCard label="Liquidity buffer at confidence" value={dollars(uncertainty.liquidity_buffer_at_confidence)} />
        <NumberCard label="Simulated paths" value={present(uncertainty.simulations)} />
      </div> : <p className="muted-note">Baseline probabilistic evidence is unavailable.</p>}
      <p className="evidence-precision-note">Do not confuse baseline probability with recovery validation or evidence coverage.</p>
    </>;
  }
  if (section.id === "evidence") {
    const quality = evidence.evidence_quality || {};
    return <>
      <div className="evidence-number-grid">
        <NumberCard label="Committed evidence" value={dollars(quality.committed_evidence_amount)} />
        <NumberCard label="Modelled evidence" value={dollars(quality.modelled_residual_amount)} />
        <NumberCard label="Management assumptions" value={dollars(quality.management_assumption_amount)} />
        <NumberCard label="Evidence coverage" value={percentage(quality.evidence_coverage_ratio)} note="Quality ratio, not probability" />
      </div>
      <h4>Engine-ranked cash drivers</h4>
      <div className="evidence-table-scroller"><table className="data-table"><thead><tr><th>Event</th><th>Category</th><th>Evidence</th><th>Week</th><th>Signed cash effect</th></tr></thead>
      <tbody>{(evidence.cash_drivers || []).map((item, index) => <tr key={`${item.event_id}-${index}`}>
        <td>{item.event_id}</td><td>{item.category}</td><td>{item.source_type}</td><td>{item.week_number ?? item.week ?? "—"}</td><td>{dollars(item.signed_cash_effect)}</td>
      </tr>)}</tbody></table></div>
    </>;
  }
  if (section.id === "recovery") {
    const rec = evidence.recovery;
    if (!rec) return <p className="evidence-precision-note">This 13-week brief has no current recovery plan. No post-recovery outcome should be inferred.</p>;
    const plan = rec.current_recovery_plan || {};
    const extra = rec.additional_liquidity_requirement || {};
    return <>
      <h4>Current recovery plan — engine result</h4>
      <div className="evidence-number-grid">
        <NumberCard label="External liquidity" value={dollars(plan.external_liquidity)} />
        <NumberCard label="Resulting minimum cash" value={dollars(plan.resulting_min_cash)} />
        <NumberCard label="Post-recovery breach probability" value={percentage(plan.reserve_breach_probability)} />
        <NumberCard label="Within appetite" value={present(plan.within_risk_appetite)} />
      </div>
      <details className="evidence-raw"><summary>Full recovery-plan attributes</summary><PairRows object={plan} /></details>
      <h4>Conditional additional liquidity</h4>
      <p className="evidence-precision-note">Additional funding is a separate conditional scenario, not proof that the current plan succeeds.</p>
      <div className="evidence-number-grid">
        <NumberCard label="Additional upfront buffer" value={dollars(extra.additional_upfront_buffer_at_confidence)} />
        <NumberCard label="Breach probability with additional buffer" value={percentage(extra.breach_probability_with_additional_buffer)} />
      </div>
    </>;
  }
  return <>
    <h4>Verified management actions</h4>
    <PairRows object={evidence.actions} />
    <h4>Monitoring triggers</h4>
    <PairRows object={evidence.monitoring} />
    <p className="evidence-precision-note">Expected cash impact is not realised cash benefit.</p>
  </>;
}

export default function AgentEvidenceWorkspace({ scenarioId, customerSessionId, importedMode, toolsUsed = [], onAskQuestion }) {
  const [active, setActive] = useState("position");
  const [payload, setPayload] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (importedMode && !customerSessionId) { setPayload(null); setError("Customer session is unavailable. Re-import the finance data."); return; }
    const controller = new AbortController();
    setLoading(true); setError(""); setPayload(null);
    const params = new URLSearchParams();
    if (customerSessionId) params.set("customer_session_id", customerSessionId);
    const suffix = params.toString() ? `?${params.toString()}` : "";
    fetch(`/api/agent/verified-workspace/${encodeURIComponent(scenarioId)}${suffix}`, { signal: controller.signal, cache: "no-store" })
      .then(async response => { const body = await response.json(); if (!response.ok) throw new Error(body.detail || "Verified evidence is unavailable"); return body; })
      .then(body => { if (!controller.signal.aborted) setPayload(body); })
      .catch(err => { if (!controller.signal.aborted) setError(err.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [scenarioId, customerSessionId, importedMode, reloadKey]);

  const section = payload?.sections?.find(item => item.id === active);
  const selectedConfig = SECTIONS.find(item => item.id === active);
  return <section className="agent-evidence-workspace" aria-label="Verified engine evidence workbench">
    <div className="panel-title-row"><div><h3>◇ Verified Evidence Workspace</h3>
      <p>Inspect the actual 13-week engine evidence before asking AI to explain it. The evidence shown here is read-only.</p></div>
      <button type="button" className="quiet-button" disabled={loading} onClick={() => setReloadKey(n => n + 1)}>↻ Refresh evidence</button>
    </div>
    {payload && <div className="evidence-workspace-meta"><span>{payload.scenario_name}</span><span>{payload.source === "customer_upload" ? "Imported customer evidence" : "Demo scenario evidence"}</span><span>{payload.scope}</span></div>}
    <div className="evidence-workspace-tabs" role="tablist" aria-label="Financial evidence categories">
      {SECTIONS.map(item => <button key={item.id} type="button" role="tab" aria-selected={active === item.id} className={active === item.id ? "selected" : ""} onClick={() => setActive(item.id)}>{item.title}{toolsUsed.includes(payload?.sections?.find(s => s.id === item.id)?.associated_agent_tool) && <span className="evidence-tool-used" title="Called by the last AI run">✓ Used</span>}</button>)}
    </div>
    <div className="evidence-workspace-content" role="tabpanel">
      {loading && <p className="muted-note">Loading existing engine evidence…</p>}
      {error && <div className="error-box" role="alert">{error}</div>}
      {!loading && !error && section && <>
        <EvidenceContent section={section} />
        <div className="evidence-workspace-foot">
          <div><b>Associated tool</b><code>{section.associated_agent_tool}</code><small>Opening this panel does not count as an AI tool call.</small></div>
          <button type="button" className="run-button" onClick={() => onAskQuestion(selectedConfig.question)}>Ask AI about this evidence →</button>
        </div>
        <details className="evidence-raw"><summary>View complete verified tool evidence (JSON)</summary><pre>{JSON.stringify(section.evidence, null, 2)}</pre></details>
      </>}
    </div>
  </section>;
}
