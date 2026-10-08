import React, { useState } from "react";

const API = "/api";
const FIELDS = [
  ["date_column", "Cash date", true],
  ["amount_column", "Amount", true],
  ["direction_column", "Cash direction", false],
  ["category_column", "Category", false],
  ["source_type_column", "Evidence classification", false],
  ["status_column", "Status", false],
  ["description_column", "Description", false],
  ["source_reference_column", "Source reference", false],
  ["due_date_column", "Contractual due date", false],
  ["expected_cash_date_column", "Expected cash date", false],
];

const PROFILES = [
  { source_id: "ar", label: "Accounts Receivable", default_direction: "INFLOW", default_category: "customer receipts", default_source_type: "COMMITTED" },
  { source_id: "ap", label: "Accounts Payable", default_direction: "OUTFLOW", default_category: "supplier payments", default_source_type: "COMMITTED" },
  { source_id: "payroll", label: "Payroll", default_direction: "OUTFLOW", default_category: "payroll", default_source_type: "COMMITTED" },
  { source_id: "tax", label: "Tax / BAS / Super", default_direction: "OUTFLOW", default_category: "tax and statutory payments", default_source_type: "COMMITTED" },
  { source_id: "other", label: "Other / Modelled Cash", default_direction: null, default_category: "other cash movement", default_source_type: "MANAGEMENT_ASSUMPTION" },
];

function initialMapping(preview, profile = null) {
  const suggested = preview.suggested_mapping || {};
  return {
    ...Object.fromEntries(FIELDS.map(([field]) => [field, suggested[field] || null])),
    default_direction: profile?.default_direction || null,
    default_category: profile?.default_category || "other cash movement",
    default_source_type: profile?.default_source_type || "MANAGEMENT_ASSUMPTION",
  };
}

function errorText(data, fallback) {
  if (typeof data?.detail === "string") return data.detail;
  if (Array.isArray(data?.detail)) return data.detail.map(item => item.msg).join("; ");
  return fallback;
}

async function previewFile(file, sheet = "") {
  const body = new FormData();
  body.append("file", file);
  if (sheet) body.append("sheet_name", sheet);
  const response = await fetch(`${API}/customer/mapping/preview`, { method: "POST", body });
  const data = await response.json();
  if (!response.ok) throw new Error(errorText(data, "Could not preview uploaded file."));
  return data;
}

function MappingEditor({ preview, mapping, onChange }) {
  if (!preview || !mapping) return null;
  const update = (name, value) => onChange({ ...mapping, [name]: value });
  return (
    <div className="mapping-editor">
      <h4>Confirm column mapping</h4>
      <p>Required fields are marked *. Check evidence classification before importing; no source is automatically promoted to committed evidence.</p>
      <div className="mapping-fields">
        {FIELDS.map(([name, title, required]) => (
          <label key={name}>
            {title}{required ? " *" : ""}
            <select value={mapping[name] || ""} onChange={event => update(name, event.target.value || null)}>
              <option value="">{required ? "Choose a column" : "Not mapped"}</option>
              {preview.columns.map(column => <option key={column} value={column}>{column}</option>)}
            </select>
          </label>
        ))}
        <label>
          Default direction (when not mapped)
          <select value={mapping.default_direction || ""} onChange={event => update("default_direction", event.target.value || null)}>
            <option value="">Choose direction if needed</option>
            <option value="INFLOW">Cash inflow</option>
            <option value="OUTFLOW">Cash outflow</option>
          </select>
        </label>
        <label>
          Default evidence type (when not mapped)
          <select value={mapping.default_source_type} onChange={event => update("default_source_type", event.target.value)}>
            <option value="MANAGEMENT_ASSUMPTION">Management assumption</option>
            <option value="MODELLED">Modelled</option>
            <option value="COMMITTED">Committed (documented obligations only)</option>
          </select>
        </label>
        <label>
          Default category (when not mapped)
          <input value={mapping.default_category} onChange={event => update("default_category", event.target.value)} />
        </label>
      </div>
      <details className="mapping-preview">
        <summary>Preview first rows ({preview.row_count} total)</summary>
        <div className="mapping-table-scroll">
          <table>
            <thead><tr>{preview.columns.slice(0, 8).map(col => <th key={col}>{col}</th>)}</tr></thead>
            <tbody>{preview.preview_rows.slice(0, 5).map((row, i) => <tr key={i}>{preview.columns.slice(0, 8).map(col => <td key={col}>{row[col] == null ? "" : String(row[col])}</td>)}</tr>)}</tbody>
          </table>
        </div>
      </details>
    </div>
  );
}

function MappingFile({ file, preview, mapping, onFile, onSheet, onMapping, busy, title }) {
  return (
    <div className="mapping-source-card">
      <label className="mapping-file-input">
        {title}
        <input type="file" accept=".csv,.xlsx,.xlsm" disabled={busy} onChange={e => onFile(e.target.files?.[0] || null)} />
      </label>
      {file && <p className="mapping-file-name">Selected: {file.name}</p>}
      {preview && preview.sheets.length > 0 && (
        <label className="mapping-sheet-picker">Excel worksheet
          <select value={preview.selected_sheet} disabled={busy} onChange={e => onSheet(e.target.value)}>
            {preview.sheets.map(name => <option key={name} value={name}>{name}</option>)}
          </select>
        </label>
      )}
      <MappingEditor preview={preview} mapping={mapping} onChange={onMapping} />
    </div>
  );
}

export default function CustomerAdvancedImport({ method, company, startDate, openingCash, reserve, risk, uncertainty, onImported, setPage }) {
  const [single, setSingle] = useState({ file: null, preview: null, mapping: null });
  const [sources, setSources] = useState([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const withPreview = async (file, sheet = "") => {
    if (!file) return { file: null, preview: null, mapping: null };
    const preview = await previewFile(file, sheet);
    return { file, preview, mapping: initialMapping(preview) };
  };

  const chooseSingle = async file => {
    setSingle({ file, preview: null, mapping: null });
    if (!file) return;
    setBusy(true); setMessage("");
    try { setSingle(await withPreview(file)); }
    catch (error) { setMessage(error.message); }
    finally { setBusy(false); }
  };

  const selectSingleSheet = async sheet => {
    if (!single.file) return;
    setBusy(true); setMessage("");
    try { setSingle(await withPreview(single.file, sheet)); }
    catch (error) { setMessage(error.message); }
    finally { setBusy(false); }
  };

  const chooseMulti = async selectedFiles => {
    const files = Array.from(selectedFiles || []);
    if (!files.length) { setSources([]); return; }
    if (files.length > 5) { setMessage("You can upload up to five finance files per analysis."); return; }
    setBusy(true); setMessage(""); setSources([]);
    try {
      const results = await Promise.all(files.map(file => withPreview(file)));
      setSources(results.map(result => ({ ...result, source_id: "" })));
    } catch (error) { setMessage(error.message); }
    finally { setBusy(false); }
  };

  const replaceSource = (index, next) => {
    setSources(previous => previous.map((value, i) => i === index ? next : value));
  };

  const changeSourceSheet = async (index, sheet) => {
    const current = sources[index];
    setBusy(true); setMessage("");
    try {
      const updated = await withPreview(current.file, sheet);
      const profile = PROFILES.find(p => p.source_id === current.source_id);
      replaceSource(index, { ...updated, source_id: current.source_id, mapping: initialMapping(updated.preview, profile) });
    } catch (error) { setMessage(error.message); }
    finally { setBusy(false); }
  };

  const changeProfile = (index, source_id) => {
    const current = sources[index];
    const profile = PROFILES.find(p => p.source_id === source_id);
    replaceSource(index, { ...current, source_id, mapping: initialMapping(current.preview, profile) });
  };

  const executeImport = async () => {
    const multi = method === "multi";
    const items = multi ? sources : [single];
    if (!items.length || items.some(item => !item.file || !item.mapping || !item.mapping.date_column || !item.mapping.amount_column)) {
      setMessage("Upload your files and confirm cash date and amount columns first."); return;
    }
    if (multi && items.some(item => !item.source_id)) {
      setMessage("Confirm a finance source profile for each uploaded file."); return;
    }
    const form = new FormData();
    form.append("company_name", company);
    form.append("forecast_start", startDate);
    form.append("opening_cash", openingCash);
    form.append("management_reserve", reserve);
    form.append("max_breach_probability", Number(risk) / 100);
    form.append("uncertainty_profile", uncertainty);
    if (multi) {
      items.forEach(item => form.append("files", item.file));
      form.append("sources_json", JSON.stringify(items.map(item => ({
        source_id: item.source_id, sheet_name: item.preview.selected_sheet,
        mapping: item.mapping,
      }))));
    } else {
      form.append("file", single.file);
      form.append("mapping_json", JSON.stringify(single.mapping));
      if (single.preview.selected_sheet) form.append("sheet_name", single.preview.selected_sheet);
    }
    setBusy(true); setMessage("Validating mapped evidence and running RiskPilot financial engines...");
    try {
      const path = multi ? "/customer/multi/import" : "/customer/mapping/import";
      const response = await fetch(`${API}${path}`, { method: "POST", body: form });
      const data = await response.json();
      if (!response.ok) throw new Error(errorText(data, "Import could not be completed."));
      onImported(data);
      setPage("command");
    } catch (error) { setMessage(error.message); }
    finally { setBusy(false); }
  };

  return (
    <div className="advanced-import">
      <div className="advanced-import-head">
        <h3>{method === "mapping" ? "Map an existing CSV or Excel file" : "Combine multiple finance sources"}</h3>
        <p>{method === "mapping" ? "Preview the file and confirm every critical column before validating the cash evidence." : "Import Accounts Receivable, Accounts Payable, payroll, tax or modelled cash files into one 13-week evidence set."}</p>
      </div>
      {method === "mapping" ? (
        <MappingFile file={single.file} preview={single.preview} mapping={single.mapping}
          title="Choose existing CSV / Excel file" busy={busy}
          onFile={chooseSingle} onSheet={selectSingleSheet}
          onMapping={mapping => setSingle(prev => ({ ...prev, mapping }))} />
      ) : (
        <>
          <label className="mapping-file-input">Select up to five finance source files (CSV, XLSX or XLSM)
            <input type="file" multiple accept=".csv,.xlsx,.xlsm" disabled={busy}
              onChange={event => chooseMulti(event.target.files)} />
          </label>
          {sources.map((source, index) => (
            <div key={`${index}-${source.file.name}`} className="mapping-multi-card">
              <div className="mapping-source-heading">
                <b>Source {index + 1}: {source.file.name}</b>
                <label>Finance source profile
                  <select disabled={busy} value={source.source_id} onChange={event => changeProfile(index, event.target.value)}>
                    <option value="">Choose source type</option>
                    {PROFILES.map(p => <option key={p.source_id} value={p.source_id}>{p.label}</option>)}
                  </select>
                </label>
              </div>
              {source.preview?.sheets.length > 0 && (
                <label className="mapping-sheet-picker">Excel worksheet
                  <select disabled={busy} value={source.preview.selected_sheet} onChange={event => changeSourceSheet(index, event.target.value)}>
                    {source.preview.sheets.map(name => <option key={name} value={name}>{name}</option>)}
                  </select>
                </label>
              )}
              <MappingEditor preview={source.preview} mapping={source.mapping}
                onChange={mapping => replaceSource(index, { ...source, mapping })} />
            </div>
          ))}
        </>
      )}
      <div className="mapping-safety-note">Evidence controls: uploaded classifications are preserved when mapped. Unmapped evidence defaults to Management Assumption unless you explicitly choose a different classification. Committed cash dates and amounts are never changed by this import process.</div>
      <button className="big-blue-button" type="button" disabled={busy} onClick={executeImport}>
        {busy ? "Processing finance data..." : "Validate mapped evidence & run RiskPilot →"}
      </button>
      {message && <div className="import-message" role="status">{message}</div>}
    </div>
  );
}
