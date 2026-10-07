# RiskPilot

AI-powered liquidity decision intelligence. The approved 13-week Command Center remains the primary workspace, with separate monthly analytics and an external ABS forecasting benchmark.

## Run

Use your existing verified environment, or create an isolated environment:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-verified.txt
python -m streamlit run app.py
```

The application works without an AI key. Configure `OPENAI_API_KEY` locally to use generative explanations. Do not commit credentials. `RISKPILOT_AI_MODEL` controls the existing AI model selection.

## Workspaces

- **Command Center:** three controlled demo scenarios; deterministic and uncertain 13-week cash trajectories, verified evidence, recovery, management actions, monitoring and temporary what-if analysis.
- **Advanced Analytics:** separate monthly business forecasts, liquidity risk, stress lab and monthly business analysis. Forecast Intelligence includes the clearly labelled external model benchmark.
- **Methodology & Evidence:** current monthly input diagnostics and verified financial-to-AI decision architecture.

## V2M external benchmark

567 official ABS monthly observations across Retail trade, Accommodation and food services, and Professional, scientific and technical services. Frozen January 2010–September 2025 data; publication ceased. Five existing models, two forecast horizons, 1,290 rolling validation fits. Industry index data never becomes demo-company revenue or V2 cash evidence.

The current conclusion is **REVIEW CHALLENGER**: retain the approved production policy and review Drift. Damped Holt does not qualify for promotion. AI consumes structured verified metrics and prioritizes approved explanatory claims; it cannot calculate replacements or switch production. The deterministic summary remains available without a generative service.

See [REAL_DATA_BENCHMARK.md](REAL_DATA_BENCHMARK.md) for exact results, methodology, source URLs, reproduction and limitations. See [FINAL_V2M_AUDIT.md](FINAL_V2M_AUDIT.md) for release checks and known limits.

## Verify and reproduce offline

```bash
python scripts/import_abs_benchmark.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m scripts.run_external_benchmark
python -m compileall -q .
git diff --check
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -q
```

`--fetch` on the import script explicitly downloads the pinned official ABS release. No tests need internet access. Rebuilding evidence resets its regression/promotion approvals and requires re-verification.

The original `requirements.txt` is retained with its local editable path repaired. `requirements-verified.txt` records the direct dependency versions actually used in this verification; it is not a complete transitive lockfile.
