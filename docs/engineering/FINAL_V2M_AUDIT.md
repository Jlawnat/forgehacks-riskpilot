# Final V2M audit

Date: 7 October 2026 (UTC).
Branch: `v2m-real-data-ai-governance`.
Verified implementation HEAD: `eebdcec079f3786c2f93bc1fcf56d59a4fbeed6e`.
Baseline HEAD: `43bd79aabc19f31b9236bdb4a7e40a7c711a991a`.
Baseline tag: `v2l-model-governance-verified`.
Release tag: `v2m-real-data-ai-governance-verified`.

The implementation HEAD above contains every verified source/data/test/UI change. A subsequent audit-only commit adds this file. The exact final archive HEAD is the release tag target, recorded in the archived Git history and ZIP comment; run `git rev-parse HEAD` or `git rev-parse v2m-real-data-ai-governance-verified`.

## Verification

- Baseline full suite: **487 passed**; compileall and diff check passed before changes.
- Final full suite: **525 passed** (all 487 original tests plus 38 new checks).
- `python -m compileall -q .`: PASS.
- `git diff --check`: PASS.
- Statistical benchmark: 1,290 rolling fits; zero failed or warning windows.
- Dataset/raw-file/result checksums: PASS; stale code/data evidence is rejected.
- Verified financial engines, approved monthly selector, forecasting mathematics, V2 Command Center module and V2 copilot are unchanged relative to the baseline tag.
- No existing test was changed, removed or weakened.

Coverage includes loader/schema/provenance, chronological order, missing/duplicate/non-finite data, prefix-only fitting and MASE scaling, rolling metrics, cross-series weighting, failure retention, stale report checks, stability thresholds, explicit promotion gates, AI verified-tool contract, constrained generative response, deterministic/service-error fallback, production freeze and degraded UI resilience.

Python 3.12 was used. Installed dependency versions differ from the uploaded environment snapshot; the direct versions actually verified are recorded in `requirements-verified.txt`. This is not a complete transitive lockfile.

## Dataset and model results

Official ABS Monthly Business Turnover Indicator final September 2025 release; retrieved 7 October 2026. Three seasonally adjusted industry index series, January 2010–September 2025, **189 observations each / 567 total**:

- Retail trade: A124873965J.
- Accommodation and food services: A124873821W.
- Professional, scientific and technical services: A124873641L.

The official XLSX files, exact series names, source URLs, units, retrieval date, transformations and checksums are frozen in `data/external_benchmark/`. All data sources are ABS; no secondary commercial source or FRED/Census fallback was needed. See [REAL_DATA_BENCHMARK.md](../validation/REAL_DATA_BENCHMARK.md) for all official links and both horizon tables.

Primary three-month results (equal-weight industries; MAE/RMSE in index points):

| Model | MAE | RMSE | MASE | Window win frequency vs Holt |
|---|---:|---:|---:|---:|
| Drift | 2.769328 | 5.200863 | 1.893347 | 45.7364% |
| Holt | 2.829568 | 5.606079 | 1.910892 | 0.0000% |
| Damped Holt | 2.913522 | 5.628728 | 1.976179 | 43.4109% |
| Naive | 2.937468 | 5.281742 | 2.004068 | 33.3333% |
| SES | 2.993224 | 5.483981 | 2.030125 | 35.6589% |

Full precision and every validation window are in `results.json`. At both horizons, every model has 129 industry-origin windows; 43 per series. Era and per-industry results are visible in the UI and reproducible from the retained rows.

## Governance decision

**Current policy: retained.** Holt is the frozen governance reference. The existing monthly implementation still selects between approved Holt and Naive alternatives based on validation error; this was already true at handoff. No production model was promoted, removed or silently fixed to one model for all possible inputs.

**Leading challenger: Drift.** Three-month MAE improves 2.1289% versus Holt; win frequency is 45.7364%; mean MAE improves in two industries and two eras. It fails the prespecified 5% improvement and 55% win thresholds, including the one-month stability check.

**Damped Holt: not a promotion candidate.** It is 2.9670% worse by MAE at three months and 3.4551% worse at one month. It improves no industry or era mean MAE relative to Holt here. The favorable result on the short demo dataset does not generalize to this external benchmark.

**AI governance recommendation: REVIEW CHALLENGER; retain production.** Regression status is PASS, downstream model-promotion review is NOT_APPROVED. No generative or deterministic route is authorized to switch configuration. Even PROMOTION CANDIDATE would require a separate explicit human decision.

## Visual and presentation audit

Browser-rendered application inspected at 1440 × 1100 with scroll captures; screenshots are in `docs/visual_qa/`.

- Healthy, Stressed Recoverable and Severe Uncertain Command Centers: overview, chart, evidence quality and insight/action text inspected.
- Cash Drivers, Recovery and Actions & Monitoring tabs opened for all three scenarios.
- Forecast Intelligence: external source/counts, governance card, aggregate table, expanded industry/era/source details, current business metrics, model labels and forecast chart.
- Liquidity Risk, Stress Lab, Monthly Analysis and Methodology & Evidence opened and scrolled.
- No visible raw HTML, traceback or debug block was found in rendered page text. The decision architecture renders as designed.
- Display fixes: SES capitalization, negative-zero percentages (including the candidate table), month-3 forecast label, monthly workspace heading, monthly breach timing and visible operating-recovery terminology.
- Primary Command Center styling/architecture preserved. No standalone page or new financial architecture was introduced.
- Gen-AI supervisor success/tool/schema and service-error paths use mocked service responses. No live model call or live V2 what-if AI session was run in this environment; existing deterministic/what-if regression tests remain passing.

## Limits and readiness

**Ready for a local product freeze**, preserving the production policy and explicit promotion restrictions. This is not approval to deploy a challenger or claim real-time forecast performance.

Known limits:

1. ABS ceased the publication; this is a historical archive ending September 2025.
2. The final vintage includes revisions and concurrent seasonal adjustment. Chronological model fitting is leakage-free within that vintage, but does not reproduce data available in real time at each old origin.
3. Industry indexes are not individual-company revenue and never become 13-week cash evidence. Shared economic shocks reduce independence.
4. Three selected industries and descriptive thresholds are not a significance test or universal model-ranking claim. COVID periods materially affect RMSE.
5. Live generative-service behavior requires the user's configured account/model. Offline deterministic operation and mocked integration/failure routes are verified.
6. Downstream promotion consistency is deliberately NOT_APPROVED; no challenger was installed into financial engines.
7. Existing monthly intervals and simulation limitations are preserved; this task does not revalidate or redesign their statistical interpretation.

## Files changed

- `README.md`
- `REAL_DATA_BENCHMARK.md`
- `app.py`
- `data/external_benchmark/metadata.json`
- `data/external_benchmark/observations.csv`
- `data/external_benchmark/raw/accommodation.xlsx`
- `data/external_benchmark/raw/professional.xlsx`
- `data/external_benchmark/raw/retail.xlsx`
- `data/external_benchmark/results.json`
- `data/external_benchmark/results.sha256`
- `docs/visual_qa/command-healthy.png`
- `docs/visual_qa/command-severe-actionsmonitoring.png`
- `docs/visual_qa/command-severe-cashdrivers.png`
- `docs/visual_qa/command-severe-recovery.png`
- `docs/visual_qa/command-severe-scroll-0.png`
- `docs/visual_qa/command-severe-scroll-1900.png`
- `docs/visual_qa/command-severe-scroll-950.png`
- `docs/visual_qa/command-severe.png`
- `docs/visual_qa/command-stressed-actionsmonitoring.png`
- `docs/visual_qa/command-stressed-cashdrivers.png`
- `docs/visual_qa/command-stressed-recovery.png`
- `docs/visual_qa/command-stressed-scroll-0.png`
- `docs/visual_qa/command-stressed-scroll-1900.png`
- `docs/visual_qa/command-stressed-scroll-950.png`
- `docs/visual_qa/command-stressed.png`
- `docs/visual_qa/forecast-details-scroll-0.png`
- `docs/visual_qa/forecast-details-scroll-1900.png`
- `docs/visual_qa/forecast-details-scroll-2850.png`
- `docs/visual_qa/forecast-details-scroll-3800.png`
- `docs/visual_qa/forecast-details-scroll-950.png`
- `docs/visual_qa/forecast.png`
- `docs/visual_qa/healthy-actionsmonitoring.png`
- `docs/visual_qa/healthy-cashdrivers.png`
- `docs/visual_qa/healthy-recovery.png`
- `docs/visual_qa/healthy-scroll-0.png`
- `docs/visual_qa/healthy-scroll-1900.png`
- `docs/visual_qa/healthy-scroll-950.png`
- `docs/visual_qa/liquidity-scroll-0.png`
- `docs/visual_qa/liquidity-scroll-1900.png`
- `docs/visual_qa/liquidity-scroll-950.png`
- `docs/visual_qa/liquidity.png`
- `docs/visual_qa/methodology-scroll-0.png`
- `docs/visual_qa/methodology-scroll-950.png`
- `docs/visual_qa/methodology.png`
- `docs/visual_qa/monthly-scroll-0.png`
- `docs/visual_qa/monthly-scroll-950.png`
- `docs/visual_qa/monthly.png`
- `docs/visual_qa/stress-scroll-0.png`
- `docs/visual_qa/stress-scroll-950.png`
- `docs/visual_qa/stress.png`
- `requirements-verified.txt`
- `requirements.txt`
- `scripts/import_abs_benchmark.py`
- `scripts/run_external_benchmark.py`
- `src/ai/model_governance.py`
- `src/forecasting/external_benchmark.py`
- `src/ui/external_benchmark.py`
- `tests/test_external_benchmark.py`
- `tests/test_external_benchmark_ui.py`
- `FINAL_V2M_AUDIT.md` (this audit-only release record).
