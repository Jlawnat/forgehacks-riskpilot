# RiskPilot Premium Frontend

## Overview

The premium product is a React/Vite user interface backed by the existing Python API and financial/AI engines. It adds a presentation and workflow layer without replacing financial calculations, model governance, evidence classification or stochastic validation.

**Local endpoints**

- Frontend: `http://localhost:5173`
- Python API: `http://127.0.0.1:8000`

**Local launch from repository root (WSL/Linux)**

```bash
bash scripts/run_premium_web.sh
```

If frontend dependencies have not been installed, run `cd web && npm install && cd ..` before launch. Use the repository's documented Python environment and requirements for the API. API availability and secret-dependent AI features must be verified in the running environment.

## Workspaces

| Workspace | Purpose | Important boundary |
|---|---|---|
| Command Center | Verified 13-week liquidity position, reserve, uncertainty, evidence and next actions | Forecast horizon is 13 weeks unless a separately validated result is available |
| AI Agent | Free-text management questions, verified tools, provenance, grounded explanations | Runtime tool steps only, not private model reasoning; a question is not necessarily a persistent conversation |
| AI Scenario | Supported revenue/cost what-if assumptions and baseline comparisons | Commitments remain unchanged; unsupported levers are not silently applied |
| Recovery Decision Center | Search, compare and validate modelled recovery plans | Results depend on active scenario constraints; deterministic feasibility differs from simulated risk eligibility |
| Company Data | Template CSV, source mapping and multi-source import | Input classification and evidence provenance require review; labels do not verify transactions |
| Methodology & Evidence | Methodology, audit and export workflows | Financial engines calculate; AI only interprets and orchestrates verified evidence |
| Advanced Monthly Analyst | Independent monthly forecasting, stress decomposition, reverse stress and AI explanation | Monthly model is separate from the 13-week cash-event engine |

## Scenario and stress interpretation

- A modelled reserve-breach rate of 0.0% means **no breaches were observed in the simulated paths**, not that real-world risk is zero.
- A cash-timing delay can reduce the **minimum intra-horizon cash balance** even if the **end-cash effect is zero**. These are different financial measures.
- Engine decomposition metrics must keep their original definitions; a `peak contribution` at the period of greatest baseline-versus-stress cash difference is not automatically a one-factor attribution of the scenario's minimum cash.
- Modelled changes are conditional estimates, not realised financial outcomes or customer approvals.
- Forecast history can be local and ephemeral; do not represent it as cloud-persistent unless verified.

## Design references

See the [approved concept gallery](design/APPROVED_DESIGN_REFERENCES.md). It contains **illustrative design references, not captured runtime evidence**.

## Review before competition submission

1. Push the **actual tested local implementation** to GitHub. This document does not deliver or modify executable financial engines.
2. Run frontend build, relevant API/unit regression tests and a manual end-to-end browser smoke test.
3. Capture authentic premium frontend screenshots only after verifying backend data and button behaviors.
4. Inspect the repository for API keys, import fixtures containing private data, and large build artifacts before publishing.
5. Verify the README run path from a clean checkout. Existing archived benchmark evidence is independent of current frontend release validation.
