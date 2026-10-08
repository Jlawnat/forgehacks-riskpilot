# RiskPilot — Public Interactive Judge Sandbox V2

**Purpose:** Give ForgeHacks judges a clickable, password-free financial decision demo without accepting private or real company records. Existing financial engines remain authoritative; no calculations are replaced.

## Access modes

- `RISKPILOT_PUBLIC_INTERACTIVE=1`: anonymous, isolated synthetic-sample demo. **No password prompt.** Every browser gets an HttpOnly/Secure, signed, temporary cookie.
- With this variable unset or set to `0`, the existing `RISKPILOT_DEMO_PASSWORD` Basic-auth private mode remains the default. Keep the password stored in Render Environment for rollback.
- The old `RISKPILOT_PUBLIC_DEMO` (restricted V1) should be removed or set to `0` if present. It is not required for V2.

## Judge experience

1. Visit the web page. No sign-in.
2. Explore the Command Center, AI Scenario and Recovery Decision Center.
3. Under Company Data, download the **synthetic cash CSV** or **synthetic Excel workbook**, then select Mapping to upload it, review fields/evidence types and run calculations.
4. For Multi-Source, download **Receipts** and **Payments** files separately from the Company Data mapping panel, select both, choose a finance source profile and explicitly review the column mappings before import. Never mark a MODELLED cash flow as COMMITTED without documentation. The files are fictional, and their dates are aligned automatically to the forecast start date selected on the page.
5. Use Advanced Monthly Analyst with the existing **synthetic monthly CSV** and run Stress / Reverse Stress.
6. In Methodology & Evidence, save and compare forecast snapshots with Forecast History. The synthetic `actuals.csv` example is available at `/api/demo/samples/actuals.csv` for optional reconciliation.
7. Download generated management PDF or audit JSON for the selected fictional scenario.
8. AI interpretation requires an `OPENAI_API_KEY` in Render; set a budget and monitor usage. No key should ever appear in client JS or GitHub.

## Public access boundaries

- Only the exact bundled synthetic CSV/XLSX byte contents can be uploaded. The server enforces this **before** opening/parsing arbitrary files. Resaving the spreadsheets or editing the samples may make them ineligible. Re-download if the service restarts before your import.
- Customer and monthly analysis tokens are bound to a signed browser session. History keys are additionally namespaced by the browser session. Sessions are **ephemeral**, in memory, expire after one hour, and vanish on restart/sleep; no accounts or shared storage exist.
- The gateway uses fixed API route allowlists, a request body cap, request/AI throttles, origin checks, and a limit of two concurrent heavy operations. These are **best-effort controls on one server**, not a formal audit, distributed quota enforcement, or a guarantee that anonymous AI requests cannot cause costs.
- Do not upload actual client, bank, personal, or confidential data. No claim of production-grade customer hosting.
- The sandbox intentionally does not support editing and re-uploading arbitrary files. Reviewers can freely vary scenario, policy, mapping, recovery and timing inputs while using the official fictional files.

## Install, verify, deploy

1. Apply V2 ZIP to a clean git feature branch based on deployed `main` (`9afad11` or compatible). The installer checks the expected file anchors and previous gateway versions.
2. Run `tests/test_public_interactive.py`, `tests/test_deploy_security.py`, full project tests and `npm run build` locally.
3. Review `git diff --check`, stage only intended paths and push branch, then fast-forward `main`.
4. In Render **Environment**, set `RISKPILOT_PUBLIC_INTERACTIVE=1`, keep `RISKPILOT_DEMO_PASSWORD` unchanged and ensure old `RISKPILOT_PUBLIC_DEMO` is unset / `0`. Deploy latest main.
5. In a Chrome Incognito window open the actual Render URL. Confirm no username dialog; test mapping and history, open a different browser profile (or a normal window versus Incognito) and verify sessions do not cross. Multiple Incognito windows in Chrome may share cookies.
6. Add the live site URL to the Devpost project only after manual smoke testing. State plainly that datasets are synthetic.

## Rollback

Set `RISKPILOT_PUBLIC_INTERACTIVE=0` in Render Environment and redeploy. The original password gate will return. The installer prints a backup location for source restoration if necessary.
