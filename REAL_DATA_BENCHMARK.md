# RiskPilot external real-data benchmark

## Purpose and source

This is a historical external model benchmark. It is **not** demo-company revenue, training data for the 13-week engine, cash commitments, receivables or evidence coverage. The controlled weekly demo businesses and all existing financial semantics are preserved.

Official source: [ABS Monthly Business Turnover Indicator, September 2025](https://www.abs.gov.au/statistics/economy/business-indicators/monthly-business-turnover-indicator/sep-2025).
[Official methodology](https://www.abs.gov.au/methodologies/monthly-business-turnover-indicator-methodology/sep-2025).
Released 10 November 2025; retrieved 7 October 2026. ABS ceased this publication after September 2025. This is a frozen historical benchmark, not a current business-activity feed.

The indicator derives from monthly ATO Business Activity Statements. It covers monthly remitters rather than all businesses, with industry-dependent coverage. These are current-price turnover indexes, **not dollar revenue**. Economically diverse industries provide a longer and more demanding comparison than the 18-month demo histories. They share macroeconomic shocks and are not statistically independent.

| Industry | Exact ABS series ID | Type | Coverage | Count |
|---|---|---|---|---:|
| Retail trade | A124873965J | Seasonally Adjusted | 2010-01-01–2025-09-01 | 189 |
| Accommodation and food services | A124873821W | Seasonally Adjusted | 2010-01-01–2025-09-01 | 189 |
| Professional, scientific and technical services | A124873641L | Seasonally Adjusted | 2010-01-01–2025-09-01 | 189 |

Total: **567 observations**, 189 per series. Unit: index points, July 2019 = 100.
The original official XLSX files, their SHA-256 hashes, exact column names, URLs and retrieval date are in `data/external_benchmark/metadata.json`. `observations.csv` is the extracted long-format dataset. No interpolation, smoothing, rescaling, imputation or outlier removal is performed. Data ordering is canonical and missing/duplicate/non-finite observations are rejected.

## Validation design

Design fixed before reviewing the first benchmark results:

- Five existing transparent candidates: Naive, Drift, SES, Holt and Damped Holt. Existing mathematical implementations are reused without modification.
- Expanding rolling-origin validation, initial training prefix of 60 months.
- Origins every three months, from December 2014 training end through June 2025 training end. Each series has 43 windows at each horizon.
- One- and three-month holdouts; primary decision horizon is three months. Holdout windows do not overlap within each horizon. Origins and holdouts match across all models.
- Every model fit uses only observations before its holdout. All fitted parameters and MASE scales are derived from the training prefix. No data from the holdout is passed to fitting or scaling.
- MAE averages absolute errors across holdout months. RMSE is the square root of mean squared error, not the mean of window RMSE values.
- Nonseasonal MASE (m=1) divides each window MAE by the training-prefix mean absolute first difference. Constant prefixes have undefined MASE and are not silently averaged into a valid aggregate.
- Industry MAE and MASE are averaged equally across industries. Aggregate RMSE is the square root of the equal-weight mean industry MSE. Raw MAE/RMSE units are index points, not dollars.
- Win frequency counts strict MAE wins against Holt; ties are not wins. Failures are retained in planned-window counts, and incomplete models receive no comparable aggregate score.
- Time stability uses three prespecified eras: pre-2020, 2020–2021 and 2022 onwards. Every window retains its origin, training end, target dates, predictions, actuals, scale and fit warnings. Annual metrics can be recomputed from the `year` field.

129 series-window comparisons per model per horizon; **1,290 fitted model windows** in total. The one- and three-month scores reuse training origins and must not be interpreted as independent replications.

## Exact results

Full precision, individual forecasts and per-window errors are in `results.json`; the following tables round only for presentation. The report carries data/code hashes and a SHA-256 sidecar; stale or corrupt reports fail closed in the UI.

### 3-month horizon

| Model | MAE | RMSE | MASE | MAE improvement vs Holt | Window wins vs Holt | Industry wins | Era wins |
|---|---:|---:|---:|---:|---:|---:|---:|
| Drift | 2.769328 | 5.200863 | 1.893347 | 2.1289% | 45.7364% | 2/3 | 2/3 |
| Holt | 2.829568 | 5.606079 | 1.910892 | 0.0000% | 0.0000% | 0/3 | 0/3 |
| Damped Holt | 2.913522 | 5.628728 | 1.976179 | -2.9670% | 43.4109% | 0/3 | 0/3 |
| Naive | 2.937468 | 5.281742 | 2.004068 | -3.8133% | 33.3333% | 1/3 | 1/3 |
| SES | 2.993224 | 5.483981 | 2.030125 | -5.7838% | 35.6589% | 0/3 | 1/3 |

### 1-month horizon

| Model | MAE | RMSE | MASE | MAE improvement vs Holt | Window wins vs Holt | Industry wins | Era wins |
|---|---:|---:|---:|---:|---:|---:|---:|
| Holt | 2.499288 | 5.467873 | 1.716004 | 0.0000% | 0.0000% | 0/3 | 0/3 |
| Drift | 2.476182 | 4.998889 | 1.716059 | 0.9245% | 41.8605% | 2/3 | 2/3 |
| Naive | 2.558140 | 5.001907 | 1.775827 | -2.3547% | 37.2093% | 2/3 | 1/3 |
| Damped Holt | 2.585640 | 5.487258 | 1.785064 | -3.4551% | 38.7597% | 0/3 | 0/3 |
| SES | 2.595654 | 5.235072 | 1.795150 | -3.8557% | 37.9845% | 1/3 | 1/3 |

All 1,290 fits succeeded with zero captured warning windows. The report includes runtime versions; numerical optimizers can vary slightly across versions/platforms.

## Decision and promotion controls

**Retain the existing production policy.** Holt is the governance reference; the existing monthly implementation still validates and selects between the approved Holt and Naive alternatives. The original code does not universally force Holt for every uploaded dataset. This delivery leaves that selector unchanged. No external benchmark can switch it, and no external series enters the V2 engine.

**Drift is the leading challenger**, ranked by equal-weight industry MASE at the primary horizon. It improves three-month MAE versus Holt by 2.1289%, wins 45.7364% of windows, and improves average MAE in two of three industries and two of three eras. At one month its MAE improves only 0.9245%. This supports **REVIEW CHALLENGER**, not promotion.

**Damped Holt is not a promotion candidate.** Its MAE is 2.9670% worse than Holt at three months and 3.4551% worse at one month. It improves no industry's or era's mean MAE versus Holt in this benchmark.

Conservative, descriptive eligibility gates must pass at **both** horizons: at least 90 windows across three industries and three eras; complete fits without warnings for candidate and Holt; at least 5% MAE improvement versus Holt; lower RMSE and MASE; at least 55% strict window wins; mean MAE improvement in at least two industries and two eras. Lower MAE alone never passes this policy. These thresholds are governance heuristics, not a statistical significance claim.

PROMOTION CANDIDATE additionally requires regression PASS and explicit downstream financial-consistency approval. It is still advisory: explicit human configuration approval is needed to change production. Downstream promotion review remains **NOT_APPROVED**, because no new financial model was promoted or validated for downstream use.

## AI supervisor

The supervisor reuses RiskPilot's OpenAI Agents architecture. A tool supplies structured, engine-computed metrics, fit warnings, gates, limitations and a policy outcome. Generative AI selects approved explanation IDs and must retain that outcome. The renderer uses Python-verified numerical sentences, preventing invented forecasts or altered metrics from entering the card. Scope, human approval and vintage caveats are always retained.

The default summary is explicitly labelled **Deterministic evidence summary**. AI runs only when requested using the button and configured service; no key, service errors or invalid responses return the same deterministic summary. No model selector or promotion tool is exposed. Live external AI service execution was not verified in this environment; tool/schema success and failure paths are tested with mocked service responses.

## Reproduction

From the repository root:

```bash
python scripts/import_abs_benchmark.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m scripts.run_external_benchmark
python -m pytest -q
```

The import command uses the frozen official XLSX files offline. To explicitly download the same pinned ABS release, use `python scripts/import_abs_benchmark.py --fetch`. Tests never require the internet. Regenerating results resets regression/promotion gates to NOT_ASSESSED/NOT_APPROVED; do not copy old approvals onto new evidence.

## Limitations

The September 2025 data vintage includes source revisions and concurrent seasonal adjustments which used information unavailable at earlier historical origins. Prefix-only fitting avoids direct future leakage **within the frozen vintage**, but does not make this an as-published real-time evaluation. This limitation blocks any claim of deployment-ready performance based solely on these scores.

Industry indexes are not company-level dollar revenue, and do not establish suitability for a specific uploaded business. COVID shocks materially affect RMSE. The selected five nonseasonal models are not the full possible model universe. Win rates and era comparisons are descriptive; no formal significance test, selection-bias adjustment, real-time vintage reconstruction or business-specific downstream promotion experiment is included. Monthly horizons do not validate the separate 13-week cash architecture.
