# RiskPilot — Render Competition Demo Deployment

This publishes the existing React/Vite frontend and Python FastAPI/financial
engines under **one HTTPS origin**. It does not change forecasting equations,
simulation assumptions, recovery eligibility, or governance.

## Important boundaries

- **Demo only**: not a production-ready multi-tenant financial data service.
- Access is protected with HTTP Basic authentication. Use username `demo` and
  a long, unique password in the Render environment. Share the password
  separately with authorized Devpost reviewers.
- API uploads and forecasts are temporarily held in process memory (up to one
  hour). They reset on restart/deploy/sleep; nothing is a persistent customer
  account or database. Use **synthetic demo data only**; do not upload real
  customer or personally identifiable financial data to this public host.
- Budget and rotate `OPENAI_API_KEY`. Without an AI key, live generative
  requests will not succeed, although engine-backed dashboards and scenarios
  can function. Do not publish an API key or put it in any repository file.
- In-process rate limiting is **not** a distributed spending cap or a substitute
  for proper edge protections. Run exactly one worker for the demo. The Render
  free tier can sleep and has limited memory/CPU; large simulations may time out.

## 1 — Local checks after applying patch

```bash
cd ~/forgehacks-riskpilot
.venv/bin/python scripts/deployment_preflight.py
.venv/bin/python -m pytest -q tests/test_deploy_security.py
(cd web && npm run build)
.venv/bin/python -m pytest -q

git diff --check
```

Your WSL `python` command may not exist; always use `.venv/bin/python`.

## 2 — Git release

Create a dedicated deployment branch, commit only the new deployment files,
and push that branch. Merge to `main` after local tests pass. Example:

```bash
cd ~/forgehacks-riskpilot
git switch -c deploy/render-competition-demo
# Install the patch before continuing.
git add -- Dockerfile .dockerignore render.yaml requirements-deploy.txt \
  scripts/start_render.sh scripts/deployment_preflight.py \
  src/api/deployment.py src/api/deploy_security.py \
  tests/test_deploy_security.py docs/RENDER_DEPLOYMENT.md
git diff --cached --check
git diff --cached --stat
git commit -m "Add password-protected Render competition demo deployment"
git push -u origin HEAD
```

After this, merge that branch into `main` using a reviewed PR, or use the
normal, non-force Git merge if you control the repository. Render should point
to `main` after the merge.

## 3 — Render dashboard

1. Open <https://dashboard.render.com/>, sign in, connect your GitHub account.
2. Select **New → Blueprint**, then choose `Jlawnat/forgehacks-riskpilot`
   and the `main` branch with `render.yaml`. Apply the Blueprint.
3. Provide `RISKPILOT_DEMO_PASSWORD` when prompted. It must be at least
   **16 characters**. **Do not put it in Git or screenshots.**
4. `riskpilot-forgehacks-demo` will build its Docker image, run Vite production
   build, install Python requirements and launch on `${PORT}`. Watch **Deploy Logs**.
5. Confirm `https://<your-render-host>/api/health` returns `status: ok`.
   This health check is intentionally public. Then visit the root `/` URL.
   Your browser prompts for Basic authentication: username `demo` and the
   password set above.
6. Only if you want live generative AI, add `OPENAI_API_KEY` in the Render
   service **Environment** settings (not in `render.yaml`). Configure a
   sensible usage budget and check the app's model access before judging.
   Redeploy or restart as requested by Render after changing variables.

You can alternatively create **New → Web Service**, connect the GitHub repo,
set **Language/Runtime: Docker**, **Dockerfile: Dockerfile**, **Health Check
Path: /api/health**, and configure the same password. The Blueprint is easiest.

## 4 — Review each live workflow

- Command Center loads Harborview (Synthetic) and other permitted scenarios.
- AI Scenario produces a *new* engine calculation and keeps baseline separate.
- Recovery optimises and validates a sample plan.
- Methodology/Evidence PDF and JSON links return nonempty files.
- Advanced Monthly Analyst imports **synthetic** monthly CSV, runs 0-day and
  14-day stress, and explains intra-horizon vs end-cash differences.
- Company Data imports **synthetic** cash CSV only, with explicit evidence
  classifications and a fresh browser session.
- AI Agent and Recovery AI return real explanations only after API credentials
  are configured. Do not claim live AI is validated until tested.
- Open in an incognito/private window. Verify unauthorized access prompts for
  credentials and wrong credentials do not open the app.
- Confirm that slow/failed requests show a useful error rather than a frozen UI.

## 5 — Publish on Devpost

Add the **actual** `https://...onrender.com` URL only after the above checks.
Provide the demo login details in reviewer instructions (never the OpenAI key),
and state that the data is synthetic. Link GitHub and the public demo video.

### Troubleshooting

- **401 Unauthorized**: use `demo` and the exact demo password; password must
  be at least 16 characters. Clear browser cached credentials if changed.
- **500/build failure**: review Render **Deploy Logs**; check `pip` resolver
  errors and image memory limits. These are not a reason to change financial
  formulas.
- **Live AI 503**: check the `OPENAI_API_KEY`, configured model access, quota.
- **App sleeps / first load slow**: a Render Free web service can sleep after
  inactivity; try again after waking. Consider a paid plan for judging.
- **Customer/monthly session disappeared**: in-memory state expires or resets
  on deploy/restart. Re-import the synthetic data.
- **Large operations fail**: free instances have limited resources. Use a more
  powerful instance if needed rather than weakening model safety checks.
- **Frontend works but API 404**: ensure Render runs
  `src.api.deployment:app`, not Streamlit or Vite development server.
