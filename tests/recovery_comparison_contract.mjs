import fs from 'node:fs';
import assert from 'node:assert/strict';

const source = fs.readFileSync(new URL('../web/src/recoveryComparison.js', import.meta.url), 'utf8');
const { buildRecoveryComparison } = await import(`data:text/javascript,${encodeURIComponent(source)}`);
const optimised = {
  candidate: {
    plan: {external_liquidity: 0, revenue_improvement_pct: 30, cost_reduction_pct: 25, receivable_acceleration_days: 7},
    evaluation: {resulting_min_cash: 70000, feasible: true},
  },
  validation: {reserve_breach_probability: 0, within_risk_appetite: true},
};
const custom = {
  plan: {external_liquidity: 5000, revenue_improvement_pct: 15, cost_reduction_pct: 10, receivable_acceleration_days: 3},
  evaluation: {resulting_min_cash: 70500, feasible: true},
  validation: {reserve_breach_probability: 0, within_risk_appetite: true},
};
const rows = buildRecoveryComparison(optimised, custom);
assert.equal(rows.length, 8);
assert.equal(rows.find(r => r.key === 'funding').deltaLabel, '+$5,000');
assert.equal(rows.find(r => r.key === 'min_cash').deltaLabel, '+$500');
assert.equal(rows.find(r => r.key === 'revenue').deltaLabel, '-15 pp');
assert.equal(rows.find(r => r.key === 'collections').deltaLabel, '-4 days');
assert.equal(rows.find(r => r.key === 'risk').customLabel, '0.0%');
assert.equal(rows.find(r => r.key === 'risk').deltaLabel, '0.0 pp');
assert.equal(buildRecoveryComparison(optimised, null), null);
assert.equal(buildRecoveryComparison({candidate:{}}, custom), null);
const withRisk = {...custom, validation: {...custom.validation, reserve_breach_probability: 0.167}};
assert.equal(buildRecoveryComparison(optimised, withRisk).find(r => r.key === 'risk').deltaLabel, '+16.7 pp');
console.log('PASS: recovery comparison uses verified fields and handles missing results (9 assertions)');
