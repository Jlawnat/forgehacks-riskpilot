# RiskPilot presentation assets

These are marketing compositions and evidence summaries, not new product screens. They change no application behavior, financial values or frozen benchmark results.

| Asset | Source and intended use |
|---|---|
| [Hero](../../assets/marketing/riskpilot-hero.png) | Real cash chart cropped from [stressed overview scroll capture](../visual_qa/command-stressed-scroll-950.png). The visible legend, axes, reserve, baseline and recovery path remain intact. Headline and callouts summarize the same controlled demo. |
| [Risk to recovery](../../assets/marketing/riskpilot-risk-to-recovery.png) | Evidence summary from [stressed overview](../visual_qa/command-stressed.png) and [recovery assessment](../visual_qa/command-stressed-recovery.png): 100% baseline risk, $35,000 minimum cash, $40,000 reserve, $10,000 external liquidity, 0.0% plan risk. |
| [What-if](../../assets/marketing/riskpilot-what-if.png) | Evidence summary from the public main README at commit `4a828533094c4bdcfa97710ce1623b6b236c4028`, confirmed by the task's verified Healthy Business example. No what-if UI screenshot is fabricated. |
| [Governance](../../assets/marketing/riskpilot-governance.png) | Frozen [benchmark](../validation/REAL_DATA_BENCHMARK.md) and [audit](../engineering/FINAL_V2M_AUDIT.md); no report regeneration. Three industry series are not claimed to be statistically independent. |
| [Architecture](../../assets/marketing/riskpilot-architecture.png) | Simplified explanation of the existing financial-evidence-to-AI architecture; no new runtime component. |
| [Social preview](../../assets/marketing/riskpilot-social-preview.png) | 1280 × 672 repository preview; controlled stressed-business evidence. Configure manually in GitHub repository Settings → General → Social preview. |
| [Demo cover](../../assets/marketing/riskpilot-demo-cover.png) | Real stressed chart crop; a local walkthrough cover, not a claim that a recorded demo exists. |

## Reproduce the compositions

From the repository root, with Pillow and DejaVu Sans fonts available:

```bash
python docs/marketing/render_assets.py
```

The script reads preserved QA captures and writes only `assets/marketing/`. It uses exact text and screenshots rather than AI-generated numbers or charts. Font paths are Linux defaults; adjust them for another operating system. Rendering dependencies are separate from the application requirements.

## Verification claims

525 passing tests come from the archived verified freeze, not a rerun in the presentation task. Local live OpenAI verification is stated by the project owner in the task brief. The archived V2M audit explicitly records offline/mocked service checks and is preserved with that distinction.

Modelled 0.0% risk in the controlled scenario is not a guarantee. ABS historical industry indexes do not validate company-level forecasts or the separate weekly cash engine.

## Suggested GitHub metadata

Description: `RiskPilot — AI liquidity decision intelligence for founders and finance teams.`

Topics: `fintech`, `ai`, `liquidity`, `cash-flow`, `forecasting`, `risk-management`, `financial-planning`, `openai`, `streamlit`, `hackathon`.

Repository metadata and the social-preview upload require settings access; the assets alone do not change those settings.
