// Read-only presentation helpers for independently verified monthly-engine responses.
// These functions never modify, forecast, or recompute engine trajectories.
const finite = value => typeof value === "number" && Number.isFinite(value);

export function compareReceivableTiming(withDelay, withoutDelay) {
  const stressed = withDelay?.scenario;
  const reference = withoutDelay?.scenario;
  if (!stressed || !reference ||
      !finite(stressed.stressed_min_cash) || !finite(reference.stressed_min_cash) ||
      !finite(stressed.stressed_end_cash) || !finite(reference.stressed_end_cash)) {
    return null;
  }
  const current = stressed.trajectory || [];
  const baseline = new Map((reference.trajectory || []).map(row => [row.period, row]));
  const trajectory = current.filter(row => finite(row.stressed_cash) && finite(baseline.get(row.period)?.stressed_cash))
    .map(row => ({
      period: row.period,
      noDelayCash: baseline.get(row.period).stressed_cash,
      delayedCash: row.stressed_cash,
      cashDifference: row.stressed_cash - baseline.get(row.period).stressed_cash,
      engineTimingAdjustment: finite(row.receivable_timing_adjustment) ? row.receivable_timing_adjustment : null,
    }));
  return {
    delayDays: Number(stressed.inputs?.receivable_delay_days ?? 0),
    referenceMinimumCash: reference.stressed_min_cash,
    delayedMinimumCash: stressed.stressed_min_cash,
    minimumCashDifference: stressed.stressed_min_cash - reference.stressed_min_cash,
    endCashDifference: stressed.stressed_end_cash - reference.stressed_end_cash,
    trajectory,
  };
}

export function reverseBreakpoint(value, max, unit, breached = false) {
  if (value != null && finite(Number(value))) {
    return unit === "%" ? `${(Number(value) * 100).toFixed(1)}%` : `${Number(value)} days`;
  }
  if (breached) return "Already below target";
  if (unit === "%") return `Not reached up to ${max}%`;
  return `Not reached up to ${max} days`;
}

export const MONTHLY_REVERSE_LIMITS = Object.freeze({
  revenuePct: 30,
  costPct: 30,
  delayDays: 90,
});
