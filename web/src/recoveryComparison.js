// Presentation-only comparison of two independently verified recovery results.
// Financial projections, probabilities and feasibility come from the Python engines.
const cash = value => value == null ? "—" : new Intl.NumberFormat("en-US", {
  style: "currency", currency: "USD", maximumFractionDigits: 0,
}).format(Number(value));
const pct = value => value == null ? "—" : `${(Number(value) * 100).toFixed(1)}%`;
const integer = value => value == null ? "—" : Number(value).toLocaleString("en-US", {maximumFractionDigits: 2});
const difference = (a, b) => a == null || b == null ? null : Number(a) - Number(b);
const deltaCash = value => value == null ? "—" : `${value > 0 ? "+" : ""}${cash(value)}`;
const deltaNumber = (value, suffix) => value == null ? "—" : `${value > 0 ? "+" : ""}${integer(value)}${suffix}`;
const deltaRisk = value => value == null ? "—" : `${value > 0 ? "+" : ""}${(value * 100).toFixed(1)} pp`;

export function buildRecoveryComparison(optimised, custom) {
  if (!optimised?.candidate?.plan || !optimised?.candidate?.evaluation || !optimised?.validation ||
      !custom?.plan || !custom?.evaluation || !custom?.validation) return null;
  const op = optimised.candidate.plan;
  const cp = custom.plan;
  const oe = optimised.candidate.evaluation;
  const ce = custom.evaluation;
  const ov = optimised.validation;
  const cv = custom.validation;
  const row = (key, label, a, b, display, deltaDisplay) => ({
    key, label, optimisedLabel: display(a), customLabel: display(b),
    deltaLabel: deltaDisplay(difference(b, a)),
  });
  const percentUnits = value => value == null ? "—" : `${integer(value)}%`;
  const days = value => value == null ? "—" : `${integer(value)} days`;
  const yesNo = value => value == null ? "—" : value ? "Yes" : "No";
  return [
    row("funding", "External funding", op.external_liquidity, cp.external_liquidity, cash, deltaCash),
    row("revenue", "Revenue improvement", op.revenue_improvement_pct, cp.revenue_improvement_pct, percentUnits, v => deltaNumber(v, " pp")),
    row("cost", "Cost reduction", op.cost_reduction_pct, cp.cost_reduction_pct, percentUnits, v => deltaNumber(v, " pp")),
    row("collections", "Collections accelerated", op.receivable_acceleration_days, cp.receivable_acceleration_days, days, v => deltaNumber(v, " days")),
    row("min_cash", "Resulting minimum cash", oe.resulting_min_cash, ce.resulting_min_cash, cash, deltaCash),
    row("risk", "Simulated reserve-breach risk", ov.reserve_breach_probability, cv.reserve_breach_probability, pct, deltaRisk),
    { key: "feasible", label: "Deterministic feasibility", optimisedLabel: yesNo(oe.feasible), customLabel: yesNo(ce.feasible), deltaLabel: "—" },
    { key: "appetite", label: "Within management risk appetite", optimisedLabel: yesNo(ov.within_risk_appetite), customLabel: yesNo(cv.within_risk_appetite), deltaLabel: "—" },
  ];
}
