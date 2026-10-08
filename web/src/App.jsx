import CustomerAdvancedImport from "./CustomerAdvancedImport.jsx";
import AiMarkdown from "./AiMarkdown.jsx";
import React, {
  useEffect,
  useMemo,
  useState,
} from "react";


const API = "/api";


function money(value) {
  if (
    value === null
    || value === undefined
  ) {
    return "—";
  }

  return new Intl.NumberFormat(
    "en-US",
    {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    }
  ).format(value);
}


function pct(value) {
  if (
    value === null
    || value === undefined
  ) {
    return "—";
  }

  return `${(value * 100).toFixed(1)}%`;
}


function Brand({
  page,
  setPage,
}) {
  const tabs = [
    ["command", "▣", "Command Center"],
    ["agent", "✦", "AI Agent"],
    ["scenario", "↗", "AI Scenario"],
    ["recovery", "◇", "Recovery Decision Center"],
    ["evidence", "▤", "Methodology & Evidence"],
    ["customer", "▱", "Company Data"],
  ];

  return (
    <div className="topbar">
      <div className="brand">
        <div className="brand-logo">◇</div>

        <div>
          <div className="brand-name">
            RiskPilot
          </div>

          <div className="brand-kicker">
            AI LIQUIDITY DECISION INTELLIGENCE
          </div>
        </div>
      </div>

      <div className="nav">
        {tabs.map(
          ([key, icon, label]) => (
            <button
              key={key}
              className={
                page === key
                  ? "nav-item active"
                  : "nav-item"
              }
              onClick={() => setPage(key)}
            >
              <span>{icon}</span>
              {label}
            </button>
          )
        )}
      </div>

      <div className="top-actions">
        <div className="engine-pill">
          <span className="dot" />
          VERIFIED ENGINE
        </div>

        <div className="profile-circle">
          MC
        </div>

        <button
          className="company-label company-nav-button"
          onClick={() => setPage("customer")}
          title="Open Company Data"
        >
          Company Data →
        </button>
      </div>
    </div>
  );
}


function Hero({
  eyebrow,
  title,
  accent,
  subtitle,
  features,
}) {
  return (
    <div className="hero">
      <div className="hero-main">
        <div className="hero-eyebrow">
          {eyebrow}
        </div>

        <div className="hero-title">
          {title}
          {accent && (
            <>
              {" "}
              <span>{accent}</span>
            </>
          )}
        </div>

        <div className="hero-copy">
          {subtitle}
        </div>
      </div>

      <div className="hero-features">
        {features.map(
          (
            [icon, name, copy],
            index
          ) => (
            <div
              className="hero-feature"
              key={index}
            >
              <div className="feature-icon">
                {icon}
              </div>

              <div>
                <b>{name}</b>
                <small>{copy}</small>
              </div>
            </div>
          )
        )}
      </div>
    </div>
  );
}


function KpiCard({
  icon,
  label,
  value,
  note,
  tone = "",
}) {
  return (
    <div className={`kpi-card ${tone}`}>
      <div className="kpi-icon">
        {icon}
      </div>

      <div>
        <div className="kpi-label">
          {label}
        </div>

        <div className="kpi-value">
          {value}
        </div>

        <div className="kpi-note">
          {note}
        </div>
      </div>
    </div>
  );
}


function CashChart({
  data,
  showScenario = false,
}) {
  const [requestedPeriod, setRequestedPeriod] = useState(13);

  if (!data) {
    return null;
  }

  const validatedWeeks = (data.weeks || []).length;
  const verifiedPeriod = validatedWeeks === 13 ? 13 : validatedWeeks;

  const deterministic = (
    data.weeks || []
  ).map(
    item => item.closing_cash
  );

  const median = (
    data.quantiles || []
  ).map(
    item => item.p50
  );

  const p10 = (
    data.quantiles || []
  ).map(
    item => item.p10
  );

  const p90 = (
    data.quantiles || []
  ).map(
    item => item.p90
  );

  const reserve = (
    data.scenario.reserve
  );

  const allValues = [
    ...deterministic,
    ...median,
    ...p10,
    ...p90,
    reserve,
  ];

  const maxValue = Math.max(
    ...allValues,
    1
  );

  const minValue = Math.min(
    ...allValues,
    0
  );

  const width = 900;
  const height = 330;
  const padX = 60;
  const padY = 35;

  const x = index => (
    padX
    + (
      index
      * (
        width
        - padX * 2
      )
      / Math.max(1, deterministic.length - 1)
    )
  );

  const y = value => (
    height
    - padY
    - (
      (
        value
        - minValue
      )
      / (
        maxValue
        - minValue
        || 1
      )
      * (
        height
        - padY * 2
      )
    )
  );

  const path = values => (
    values
      .map(
        (value, index) => (
          `${index === 0 ? "M" : "L"}`
          + `${x(index)} ${y(value)}`
        )
      )
      .join(" ")
  );

  const area = (
    p90.length
      ? (
        path(p90)
        + " "
        + p10
          .map(
            (
              value,
              reverseIndex
            ) => {
              const index = (
                p10.length
                - 1
                - reverseIndex
              );

              return (
                `L${x(index)} `
                + `${y(p10[index])}`
              );
            }
          )
          .join(" ")
        + " Z"
      )
      : ""
  );

  return (
    <div className="chart-card">
      <div className="panel-title-row">
        <div>
          <h3>
            {showScenario
              ? "Cash trajectory comparison"
              : `${validatedWeeks}-Week Cash Trajectory`}
          </h3>

          <p>
            Forecast · uncertainty ·
            management reserve
          </p>
        </div>

        <div className="range-tabs" role="group" aria-label="Forecast horizon">
          {[13, 26, 52].map(weeks => (
            <button
              key={weeks}
              type="button"
              className={requestedPeriod === weeks ? "selected" : ""}
              aria-pressed={requestedPeriod === weeks}
              onClick={() => setRequestedPeriod(weeks)}
              title={weeks === verifiedPeriod
                ? "Display verified cash forecast"
                : "Check whether a verified forecast is available"}
            >
              {weeks} weeks
            </button>
          ))}
        </div>
      </div>

      {requestedPeriod !== verifiedPeriod ? (
        <div className="horizon-unavailable" role="status">
          <strong>{requestedPeriod}-week forecast is not available</strong>
          <p>
            This API supplies {validatedWeeks} verified weekly cash values. RiskPilot will
            not extrapolate financial forecasts or reuse 13-week risk estimates for
            a longer horizon without a validated engine result.
          </p>
          <button type="button" onClick={() => setRequestedPeriod(verifiedPeriod)}>
            Return to validated {validatedWeeks}-week analysis →
          </button>
        </div>
      ) : <>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="cash-svg"
      >
        {[0, 1, 2, 3, 4].map(
          index => {
            const yy = (
              padY
              + index
              * (
                height
                - 2 * padY
              )
              / 4
            );

            return (
              <line
                key={index}
                x1={padX}
                x2={width - padX}
                y1={yy}
                y2={yy}
                className="grid-line"
              />
            );
          }
        )}

        {area && (
          <path
            d={area}
            className="uncertainty-area"
          />
        )}

        <line
          x1={padX}
          x2={width - padX}
          y1={y(reserve)}
          y2={y(reserve)}
          className="reserve-line"
        />

        {median.length > 0 && (
          <path
            d={path(median)}
            className="median-line"
          />
        )}

        <path
          d={path(deterministic)}
          className="cash-line"
        />

        {deterministic.map(
          (value, index) => (
            <circle
              key={index}
              cx={x(index)}
              cy={y(value)}
              r="4"
              className="cash-point"
            />
          )
        )}

        {deterministic.map(
          (_, index) => (
            <text
              key={`w-${index}`}
              x={x(index)}
              y={height - 7}
              textAnchor="middle"
              className="axis-text"
            >
              W{index + 1}
            </text>
          )
        )}

        <text
          x={width - padX - 4}
          y={y(reserve) - 8}
          textAnchor="end"
          className="reserve-label"
        >
          Reserve {money(reserve)}
        </text>
      </svg>

      <div className="legend">
        <span>
          <i className="legend-dot blue" />
          Deterministic cash
        </span>

        <span>
          <i className="legend-dot navy" />
          Simulated median
        </span>

        <span>
          <i className="legend-box" />
          P10–P90 uncertainty
        </span>

        <span>
          <i className="legend-dash" />
          Management reserve
        </span>
      </div>
      <details className="chart-breakdown">
        <summary>View verified weekly cash values and uncertainty →</summary>
        <div className="chart-breakdown-scroll"><table className="data-table">
          <thead><tr><th>Week</th><th>Closing cash</th><th>Simulated median</th><th>P10</th><th>P90</th></tr></thead>
          <tbody>{(data.weeks || []).map((week, index) => (
            <tr key={week.week}>
              <td>Week {week.week}</td><td>{money(week.closing_cash)}</td>
              <td>{money(data.quantiles?.[index]?.p50)}</td>
              <td>{money(data.quantiles?.[index]?.p10)}</td>
              <td>{money(data.quantiles?.[index]?.p90)}</td>
            </tr>
          ))}</tbody>
        </table></div>
      </details>
      </>}
    </div>
  );
}


function Loading() {
  return (
    <div className="loading-card">
      Loading verified RiskPilot engine…
    </div>
  );
}


function CommandCenter({
  data,
  scenarios,
  scenarioId,
  setScenarioId,
  setPage,
  importedMode = false,
  onExitCustomer,
}) {
  if (!data) {
    return <Loading />;
  }

  const currentGap = (
    data.position.current_cash
    - data.scenario.reserve
  );

  return (
    <>
      <Hero
        eyebrow={
          data.scenario.is_public
            ? "PUBLIC SOURCE ANALYSIS"
            : "AI LIQUIDITY DECISION INTELLIGENCE"
        }
        title="13-Week Liquidity"
        accent="Command Center"
        subtitle={data.scenario.description}
        features={[
          [
            "▥",
            data.scenario.is_public
              ? "Verified Public Data"
              : "Verified Finance Data",
            "Trace every number to source evidence",
          ],
          [
            "◇",
            "Transparent Methodology",
            "Financial engines remain authoritative",
          ],
          [
            "✦",
            "AI-Powered Insights",
            "Turn complex evidence into clear action",
          ],
        ]}
      />

      <div className="product-surface">
        <div className="scenario-row">
          <div className="scenario-chip">
            <b>{data.scenario.name}</b>
            <span>·</span>
            <span>13-week forecast</span>
            <span>·</span>
            <span>
              Reserve{" "}
              {money(
                data.scenario.reserve
              )}
            </span>
            <span>·</span>
            <span>
              Risk appetite{" "}
              {pct(
                data.scenario
                  .risk_appetite
              )}
            </span>
          </div>

          <label className="scenario-select">
            <small>{importedMode ? "Customer analysis" : "Change scenario"}</small>

            <select
              value={importedMode ? "customer-upload" : scenarioId}
              onChange={event => (
                setScenarioId(
                  event.target.value
                )
              )}
            >
              {importedMode && <option value="customer-upload">{data.scenario.name} · imported</option>}
              {scenarios.map(
                scenario => (
                  <option
                    key={scenario.id}
                    value={scenario.id}
                  >
                    {scenario.name}
                  </option>
                )
              )}
            </select>
            {importedMode && <button type="button" className="scenario-text-button"
              onClick={onExitCustomer}>Return to demo analysis</button>}
          </label>
        </div>

        {importedMode && <section className="customer-active-banner" role="status">
          <div><b>✓ Your company data is active</b>
            <span>These cash forecasts use your uploaded evidence, not a demo dataset.
              Financial engines remain authoritative.</span>
          </div>
          <button type="button" onClick={() => setPage("agent")}>✦ Ask AI about this company →</button>
          <button type="button" onClick={() => setPage("scenario")}>↗ Test supported assumptions →</button>
        </section>}
        {data.scenario.is_public && (
          <div className="source-banner">
            <span>PUBLIC SOURCE</span>
            Cenveo 2018 SEC-filed
            13-week DIP liquidity forecast ·
            $20m minimum-liquidity reference ·
            RiskPilot analytical overlay
          </div>
        )}

        {data.position.first_breach_week && (
          <div className="alert-strip">
            <div className="alert-icon">
              !
            </div>

            <div>
              <b>ACTION REQUIRED</b>

              <p>
                Cash is projected to fall{" "}
                {money(
                  Math.abs(
                    data.position
                      .minimum_headroom
                  )
                )}{" "}
                below the management reserve.
                Review the recovery plan now.
              </p>
            </div>

            <span className="alert-pill">
              ACTION REQUIRED
            </span>
          </div>
        )}

        <div className="kpi-grid">
          <KpiCard
            icon="▱"
            label="CURRENT CASH"
            value={money(
              data.position.current_cash
            )}
            note={
              `${money(currentGap)} `
              + (
                currentGap >= 0
                  ? "above reserve today"
                  : "below reserve today"
              )
            }
          />

          <KpiCard
            icon="↘"
            label="MINIMUM PROJECTED CASH"
            value={money(
              data.position.minimum_cash
            )}
            note={
              `Week ${
                data.position
                  .minimum_cash_week
              } · `
              + money(
                data.position
                  .minimum_headroom
              )
              + " vs reserve"
            }
            tone={data.position.minimum_headroom < 0 ? "critical" : ""}
          />

          <KpiCard
            icon="△"
            label="RESERVE-BREACH PROBABILITY"
            value={pct(
              data.risk.probability
            )}
            note={
              `Management appetite `
              + pct(
                data.risk
                  .risk_appetite
              )
            }
            tone={data.risk.probability != null &&
              data.risk.probability > data.risk.risk_appetite ? "critical" : ""}
          />

          <KpiCard
            icon="▤"
            label="EVIDENCE BASIS"
            value={
              data.scenario.is_public
                ? "PUBLIC FORECAST"
                : (
                  data.position
                    .evidence_coverage
                    !== null
                    ? pct(
                      data.position
                        .evidence_coverage
                    )
                    : "VERIFIED INPUTS"
                )
            }
            note={
              data.scenario.is_public
                ? "SEC-filed 13-week liquidity budget"
                : "RiskPilot evidence classification"
            }
          />
        </div>

        <div className="main-grid">
          <CashChart data={data} />

          <div className="insight-card">
            <div className="insight-kicker">
              RISKPILOT INSIGHT
              <span>✓ VERIFIED</span>
            </div>

            <h3>
              {data.insight.title}
            </h3>

            <p>
              The current 13-week engine
              evaluates this position against
              the management reserve and risk
              appetite using verified forecast
              evidence.
            </p>
            <p className="insight-next-step"><b>Next action:</b> {data.insight.next_step}</p>

            <div className="driver-heading">
              KEY DRIVERS
            </div>

            {data.cash_drivers
              .slice(0, 3)
              .map(
                (driver, index) => (
                  <div
                    className="driver-row"
                    key={driver.event_id}
                  >
                    <span className="driver-index">
                      {index + 1}
                    </span>

                    <div>
                      <b>
                        {driver.category}
                      </b>

                      <small>
                        Week {driver.week} ·{" "}
                        {money(
                          driver.amount
                        )}
                      </small>
                    </div>
                  </div>
                )
              )}

            <button
              className="big-blue-button"
              onClick={() => (
                setPage("recovery")
              )}
            >
              ✦ Open recovery decision example →
            </button>
          </div>
        </div>
      </div>
    </>
  );
}


function AgentPage({
  data,
  scenarioId,
  setPage,
  importedMode = false,
  customerSessionId = null,
  history,
  setHistory,
  initialQuestion = "",
}) {
  const [
    question,
    setQuestion,
  ] = useState(initialQuestion);

  const [
    response,
    setResponse,
  ] = useState(null);

  const [
    running,
    setRunning,
  ] = useState(false);

  const questionExamples = [
    "What is our current liquidity position and reserve headroom?",
    "What is driving cash movement over the next 13 weeks?",
    "What if modelled revenue falls 20% and operating costs rise 10% over the next 13 weeks?",
    "Which recovery actions should management consider?",
    "What should management monitor next?",
  ];

  const runAgent = async () => {
    if (!question.trim() || (importedMode && !customerSessionId) || running) return;
    setResponse(null);

    setRunning(true);

    try {
      const result = await fetch(
        `${API}/agent`,
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            scenario_id: scenarioId,
            customer_session_id: customerSessionId,
            question,
          }),
        }
      );

      const body = await result.json();

      if (!result.ok) {
        throw new Error(
          body.detail
          || "Agent request failed"
        );
      }

      setResponse(body);
      setHistory(previous => [{
        question: question.trim(),
        answer: body.answer,
        tools: body.tools_used || [],
        result: body.result,
        temporaryWhatIf: !!body.temporary_what_if,
        at: new Date().toLocaleTimeString(),
      }, ...previous].slice(0, 10));
    } catch (error) {
      setResponse({
        error: error.message,
      });
    } finally {
      setRunning(false);
    }
  };

  const runVerified = !!response && !response.error;
  const activeData = (
    runVerified ? response.result : data
  );

  const tools = (
    response?.tools_used
    || []
  );

  const steps = [
    [
      "Interpret management intent",
      "Parse the management question and map it to supported RiskPilot workflows.",
      "✦",
    ],
    ...tools.map(
      tool => {
        const labels = {
          run_v2_what_if_scenario:
            [
              "Apply scenario shock",
              "Run one verified temporary scenario with the requested supported assumptions.",
              "↗",
            ],

          get_v2_liquidity_position:
            [
              "Run liquidity engine",
              "Retrieve the 13-week cash position, reserve headroom and liquidity risk.",
              "▥",
            ],

          get_v2_cash_evidence:
            [
              "Inspect cash evidence",
              "Retrieve evidence coverage and ranked cash-flow drivers.",
              "◎",
            ],

          get_v2_recovery_evidence:
            [
              "Evaluate recovery options",
              "Check deterministic feasibility and probabilistic recovery evidence.",
              "◇",
            ],

          get_v2_actions_monitoring:
            [
              "Review actions & monitoring",
              "Retrieve management actions and monitoring triggers.",
              "✓",
            ],
        };

        return (
          labels[tool]
          || [
            tool,
            "Verified RiskPilot tool used during this run.",
            "◇",
          ]
        );
      }
    ),
    [
      "Generate grounded recommendation",
      "Synthesize only verified evidence returned during the current run.",
      "◆",
    ],
  ];

  return (
    <>
      <Hero
        eyebrow="AI DECISION AGENT"
        title="AI Agent"
        accent="Execution Trace"
        subtitle={
          "From natural language to verified financial decisions. "
          + "See how RiskPilot uses trusted tools and delivers grounded recommendations."
        }
        features={[
          [
            "✦",
            "Natural Language",
            "Ask management questions in everyday language",
          ],
          [
            "◇",
            "Verified Tools",
            "Agent calls financial engines instead of inventing values",
          ],
          [
            "▥",
            "Grounded Decisions",
            "Clear management-ready recommendations",
          ],
        ]}
      />

      <div className="product-surface">
        <section className="agent-composer" aria-label="Ask RiskPilot AI">
          <div className="agent-composer-heading">
            <div className="question-icon">✦</div>
            <div>
              <h3>Ask RiskPilot AI</h3>
              <p>Write your own management question. The suggested questions below are optional.</p>
            </div>
            <span className="agent-composer-tag">Verified financial tools</span>
          </div>
          <label className="agent-custom-label" htmlFor="riskpilot-custom-question">
            YOUR QUESTION — FREE TEXT
          </label>
          <textarea
            id="riskpilot-custom-question"
            className="agent-custom-question"
            value={question}
            rows={3}
            maxLength={2000}
            disabled={running || (importedMode && !customerSessionId)}
            placeholder="Ask anything about your liquidity, evidence, risks or supported what-if scenarios. For example: What if revenue falls 15% and costs rise 8%?"
            onChange={event => {
              setQuestion(event.target.value);
              setResponse(null);
            }}
            onKeyDown={event => {
              if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
                event.preventDefault();
                runAgent();
              }
            }}
          />
          <div className="agent-composer-actions">
            <small>{question.length}/2000 characters · Ctrl/⌘ + Enter to analyse</small>
            <div>
              <button type="button" className="quiet-button"
                disabled={running || !question}
                onClick={() => { setQuestion(""); setResponse(null); }}>
                Clear
              </button>
              <button type="button" className="run-button"
                onClick={runAgent}
                disabled={running || (importedMode && !customerSessionId) || !question.trim()}>
                {running ? "Running verified tools…" : "▶ Run Analysis →"}
              </button>
            </div>
          </div>
        </section>

        {importedMode && (
          <div className="workflow-notice success" role="status">
            {customerSessionId
              ? `Customer workspace active: ${data?.scenario?.name}. AI tools use the uploaded 13-week evidence, not a demo scenario. Session expires after one hour or API restart.`
              : "No active customer session. Re-import your cash CSV to enable AI analysis."}
          </div>
        )}
        <details className="agent-example-bar">
          <summary>✦ Optional example questions — click to expand</summary>
          <div className="agent-example-list">
            {questionExamples.map((example, index) => (
              <button type="button" key={example}
                onClick={() => { setQuestion(example); setResponse(null); }}>
                {index + 1}. {example}
              </button>
            ))}
          </div>
          <small>Custom questions and examples use the same AI endpoint. Each run is independent, not a persistent conversation. Unsupported requests may receive a limitation message.</small>
        </details>

        <div className="agent-layout">
          <div className="trace-card">
            <div className="panel-title-row">
              <div>
                <h3>
                  ✦ Agent execution trace
                </h3>

                <p>
                  Observable runtime actions only —
                  not private model reasoning.
                </p>
              </div>

              <span className={runVerified ? "verified-chip" : "status-pending"}>
                {running ? "● RUNNING" : runVerified ? "● VERIFIED RUN" : "○ AWAITING RUN"}
              </span>
            </div>

            {steps.map(
              (
                [title, copy, icon],
                index
              ) => (
                <div
                  className="trace-row"
                  key={`${title}-${index}`}
                >
                  <div className="trace-number">
                    {index + 1}
                  </div>

                  <div className="trace-icon">
                    {icon}
                  </div>

                  <div className="trace-copy">
                    <b>{title}</b>
                    <small>{copy}</small>
                  </div>

                  <span className={runVerified ? "trace-status" : "status-pending"}>
                    {runVerified ? "✓ Verified" : "Awaiting run"}
                  </span>
                </div>
              )
            )}

            {!runVerified && (
              <div className="trace-placeholder">
                Run the management question to
                populate the real tool provenance.
              </div>
            )}
          </div>

          <div className="recommendation-card">
            <div className="recommendation-head">
              <h3>
                ◎ Management recommendation
              </h3>

              <span className={runVerified ? "green" : "status-pending"}>
                {runVerified ? "● VERIFIED" : "○ BASELINE PREVIEW"}
              </span>
            </div>

            {response?.error ? (
              <div className="error-box">
                {response.error}
              </div>
            ) : (
              <>
                <div className={`recommendation-alert ${activeData?.insight?.tone || ""}`}>
                  <b>
                    {activeData
                      ?.insight
                      ?.title
                      || "Run the agent to generate a recommendation."}
                  </b>

                  <span>
                    {activeData
                      ?.insight
                      ?.next_step}
                  </span>
                </div>

                {response?.answer && (
                  <div className="agent-answer">
                    <AiMarkdown text={response.answer} />
                  </div>
                )}

                {activeData && (
                  <div className="mini-kpis">
                    <KpiCard
                      icon="↘"
                      label="MINIMUM PROJECTED CASH"
                      value={money(
                        activeData
                          .position
                          .minimum_cash
                      )}
                      note={
                        `Week ${
                          activeData
                            .position
                            .minimum_cash_week
                        }`
                      }
                    />

                    <KpiCard
                      icon="△"
                      label="RESERVE-BREACH PROBABILITY"
                      value={pct(
                        activeData
                          .risk
                          .probability
                      )}
                      note={
                        `vs. ${
                          pct(
                            activeData
                              .risk
                              .risk_appetite
                          )
                        } appetite`
                      }
                    />
                  </div>
                )}

                <button
                  className="big-blue-button"
                  onClick={() => (
                    setPage("scenario")
                  )}
                >
                  ↗ Adjust scenario assumptions →
                </button>
              </>
            )}
          </div>
        </div>

        <div className="provenance-card">
          <div className="panel-title-row">
            <div>
              <h3>▥ Tool provenance</h3>
              <p>
                Tool calls shown here are the
                actual tools returned by the agent runtime.
              </p>
            </div>
          </div>

          <table className="data-table">
            <thead>
              <tr>
                <th>STEP</th>
                <th>TOOL</th>
                <th>STATUS</th>
              </tr>
            </thead>

            <tbody>
              {tools.map(
                (tool, index) => (
                  <tr key={tool + index}>
                    <td>{index + 1}</td>
                    <td>{tool}</td>
                    <td className="green">
                      ✓ Verified
                    </td>
                  </tr>
                )
              )}

              {tools.length === 0 && (
                <tr>
                  <td colSpan="3">
                    Run the agent to view
                    real runtime provenance.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <section className="analysis-history">
          <div className="panel-title-row">
            <div>
              <h3>✦ Recent AI analyses</h3>
              <p>Session-only history. Each row is an independent API response.</p>
            </div>
            {history.length > 0 && <button type="button" onClick={() => setHistory([])}>
              Clear history
            </button>}
          </div>
          {history.length === 0 ? <p className="muted-note">Run an analysis to see the results here.</p> :
            history.map((entry, index) => (
              <details className="history-item" key={`${entry.at}-${index}`}>
                <summary>{entry.question} <small>{entry.at} · {entry.tools.length} tools</small></summary>
                <div className="history-answer"><AiMarkdown text={entry.answer} /></div>
                {entry.tools.length > 0 && <small>Tools: {entry.tools.join(", ")}</small>}
                <button type="button" onClick={() => {setQuestion(entry.question); setResponse(null);}}>
                  Use question again
                </button>
              </details>
            ))}
        </section>
      </div>
    </>
  );
}


function ScenarioPage({
  scenarioId,
  data,
  scenarios = [],
  setScenarioId,
  onAskAgent,
  importedMode = false,
  customerSessionId = null,
  customerCapabilities = null,
}) {
  const [
    revenue,
    setRevenue,
  ] = useState(-20);

  const [
    cost,
    setCost,
  ] = useState(10);

  const [
    result,
    setResult,
  ] = useState(null);
  const [managementReserve, setManagementReserve] = useState("");
  const [scenarioQuestion, setScenarioQuestion] = useState("");
  const [scenarioHistory, setScenarioHistory] = useState([]);
  const [error, setError] = useState("");
  const revenueSupported = !importedMode || !!customerCapabilities?.modelled_revenue_events;
  const costSupported = !importedMode || !!customerCapabilities?.modelled_cost_events;
  useEffect(() => {
    if (importedMode) {
      setRevenue(0);
      setCost(0);
      setManagementReserve("");
      setResult(null);
      setScenarioHistory([]);
    }
  }, [customerSessionId]);
  const scenarioPresets = [
    { name: "No shock", revenue: 0, cost: 0 },
    { name: "Mild stress", revenue: -10, cost: 5 },
    { name: "Demand shock", revenue: -20, cost: 10 },
    { name: "Severe stress", revenue: -35, cost: 20 },
    { name: "Upside", revenue: 10, cost: -5 },
  ];
  const updateRevenue = value => { setRevenue(value); setResult(null); setError(""); };
  const updateCost = value => { setCost(value); setResult(null); setError(""); };
  const updateReserve = value => { setManagementReserve(value); setResult(null); setError(""); };

  const [
    running,
    setRunning,
  ] = useState(false);

  const run = async () => {
    if (importedMode && !customerSessionId) {
      setError("Customer analysis session unavailable. Re-import your cash CSV.");
      return;
    }
    setError("");
    setResult(null);
    if (revenue === "" || cost === "" ||
        !Number.isFinite(Number(revenue)) || !Number.isFinite(Number(cost)) ||
        Number(revenue) < -100 || Number(revenue) > 100 ||
        Number(cost) < -100 || Number(cost) > 100 ||
        (managementReserve !== "" &&
          (!Number.isFinite(Number(managementReserve)) || Number(managementReserve) < 0))) {
      setError("Enter valid percentage changes (-100 to +100) and a non-negative reserve.");
      return;
    }
    setRunning(true);

    try {
      const response = await fetch(
        `${API}/what-if`,
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            scenario_id: scenarioId,
            customer_session_id: customerSessionId,
            revenue_change_pct:
              Number(revenue),
            cost_change_pct:
              Number(cost),
            management_reserve: managementReserve === ""
              ? null : Number(managementReserve),
          }),
        }
      );

      const body = await response.json();

      if (!response.ok) {
        throw new Error(
          body.detail
          || "Scenario failed"
        );
      }

      setResult(body);
      setScenarioHistory(previous => [{
        id: Date.now(),
        revenue: Number(revenue),
        cost: Number(cost),
        reserve: managementReserve === "" ? "" : Number(managementReserve),
        result: body,
        at: new Date().toLocaleTimeString(),
      }, ...previous].slice(0, 8));
    } catch (error) {
      setError(error.message);
    } finally {
      setRunning(false);
    }
  };

  const active = (
    result?.result
    || data
  );

  if (!active) {
    return <Loading />;
  }

  return (
    <>
      <Hero
        eyebrow="AI SCENARIO COMMAND"
        title="Ask a what-if."
        accent="Get a plan."
        subtitle={
          "Turn supported management scenarios into verified "
          + "13-week liquidity analysis and management-ready actions."
        }
        features={[
          [
            "✦",
            "Natural Language Scenarios",
            "Translate management questions into supported levers",
          ],
          [
            "◇",
            "Engine-Backed Analysis",
            "Financial engines recalculate the verified scenario",
          ],
          [
            "▥",
            "Actionable Recommendation",
            "Compare the result with management appetite",
          ],
        ]}
      />

      <div className="product-surface">
        <section className="scenario-workbench" aria-label="Scenario builder">
          <div className="scenario-workbench-heading">
            <div>
              <small>FINANCIAL SCENARIO BUILDER</small>
              <h3>Test your own assumptions</h3>
              <p>All controls below send real, supported values to the 13-week What-if API. Inputs do not modify your baseline.</p>
            </div>
            <span className="verified-chip">13-WEEK ENGINE</span>
          </div>

          <div className="scenario-config-grid">
            <label className="scenario-config-field">
              <span>Baseline company / scenario</span>
              <select value={importedMode ? "customer-upload" : scenarioId}
                disabled={importedMode || !scenarios.length}
                onChange={event => setScenarioId(event.target.value)}>
                {importedMode && <option value="customer-upload">{data?.scenario?.name} · imported</option>}
                {scenarios.map(item => <option value={item.id} key={item.id}>{item.name}</option>)}
              </select>
              <small>{importedMode
                ? "Using your uploaded cash evidence. Return to a demo from Command Center to change datasets."
                : "Changing the base case loads a separate verified forecast."}</small>
            </label>
            <div className="scenario-config-readonly">
              <span>Risk appetite (current policy)</span>
              <b>{pct(data?.risk?.risk_appetite)}</b>
              <small>Read-only: not an adjustable What-if API parameter.</small>
            </div>
          </div>

          <div className="scenario-preset-area">
            <strong>Quick stress tests</strong>
            <div className="scenario-preset-buttons">
              {scenarioPresets.map(preset => (
                <button type="button" key={preset.name}
                  className={Number(revenue) === preset.revenue && Number(cost) === preset.cost
                    ? "scenario-preset active" : "scenario-preset"}
                  disabled={running || (importedMode &&
                    ((preset.revenue !== 0 && !revenueSupported) || (preset.cost !== 0 && !costSupported)))}
                  onClick={() => {
                    updateRevenue(preset.revenue);
                    updateCost(preset.cost);
                    updateReserve("");
                  }}>
                  {preset.name}
                  <small>{preset.revenue > 0 ? "+" : ""}{preset.revenue}% revenue · {preset.cost > 0 ? "+" : ""}{preset.cost}% cost</small>
                </button>
              ))}
            </div>
            <small>Presets fill the inputs only. Click Run new scenario to calculate a verified result.</small>
          </div>

          <div className="scenario-lever-grid">
            <label className="scenario-lever">
              <span>MODELLED REVENUE CHANGE <b>{revenue === "" ? "—" : `${revenue}%`}</b></span>
              <input aria-label="Modelled revenue change percentage" type="range" min="-100" max="100" step="1"
                value={revenue === "" ? 0 : revenue} disabled={running || !revenueSupported}
                onChange={event => updateRevenue(Number(event.target.value))} />
              <input type="number" min="-100" max="100" step="1" value={revenue}
                disabled={running || !revenueSupported} aria-label="Revenue change percentage exact value"
                onChange={event => updateRevenue(event.target.value)} />
              <small>{revenueSupported
                ? "Only MODELLED residual sales receipts are adjusted; COMMITTED evidence stays fixed."
                : "Unavailable: no MODELLED residual sales receipts in this upload."}</small>
            </label>
            <label className="scenario-lever">
              <span>OPERATING COST CHANGE <b>{cost === "" ? "—" : `${cost}%`}</b></span>
              <input aria-label="Operating cost change percentage" type="range" min="-100" max="100" step="1"
                value={cost === "" ? 0 : cost} disabled={running || !costSupported}
                onChange={event => updateCost(Number(event.target.value))} />
              <input type="number" min="-100" max="100" step="1" value={cost}
                disabled={running || !costSupported} aria-label="Operating cost change percentage exact value"
                onChange={event => updateCost(event.target.value)} />
              <small>{costSupported
                ? "Only MODELLED variable operating costs are adjusted; COMMITTED evidence stays fixed."
                : "Unavailable: no MODELLED variable operating costs in this upload."}</small>
            </label>
            <label className="scenario-lever">
              <span>MANAGEMENT RESERVE <b>{managementReserve === "" ? "Use policy" : money(managementReserve)}</b></span>
              <input type="number" min="0" step="1000" value={managementReserve}
                disabled={running} aria-label="Management reserve override in USD"
                placeholder={String(data?.scenario?.reserve ?? "")}
                onChange={event => updateReserve(event.target.value)} />
              <small>Optional USD override. Blank uses the selected baseline's policy.</small>
              <button type="button" className="scenario-text-button" disabled={running || managementReserve === ""}
                onClick={() => updateReserve("")}>Use baseline reserve</button>
            </label>
          </div>

          <div className="scenario-run-actions">
            <div>
              <strong>What will be calculated?</strong>
              <small>13-week cash forecast, cash minimum, reserve-breach risk, uncertainty and key drivers.</small>
            </div>
            <button type="button" className="run-button" onClick={run}
              disabled={running || (importedMode && !customerSessionId)}>
              {running ? "Running verified scenario…" : "▶ Run new scenario →"}
            </button>
          </div>
        </section>

        <section className="scenario-ai-question">
          <div>
            <strong>Prefer to describe the situation in your own words?</strong>
            <small>Send a custom question to the AI Agent. The AI tool decides whether it can run a supported scenario; this does not silently change the structured inputs.</small>
          </div>
          <textarea rows={2} maxLength={2000} value={scenarioQuestion} disabled={importedMode && !customerSessionId}
            aria-label="Describe your custom management scenario"
            placeholder="For example: If our revenues fall by 15% and costs rise 6%, how much liquidity headroom would remain?"
            onChange={event => setScenarioQuestion(event.target.value)} />
          <button type="button" disabled={(importedMode && !customerSessionId) || !scenarioQuestion.trim()}
            onClick={() => onAskAgent(scenarioQuestion.trim())}>Ask AI Agent →</button>
        </section>
        {importedMode && <div role="status" className="workflow-notice success">
          Active customer data: {data?.scenario?.name}. Only matching MODELLED categories
          can be stress-tested; committed evidence is never scaled. Revenue eligible:
          {" "}{customerCapabilities?.modelled_revenue_events ?? 0} events; cost eligible:
          {" "}{customerCapabilities?.modelled_cost_events ?? 0} events. Receivable timing changes are not supported by this V2 engine.
        </div>}
        {error && <div role="alert" className="error-box">{error}</div>}
        <div className={result ? "workflow-notice success" : "workflow-notice"} role="status">
          {result
            ? "Verified temporary scenario result below. Changes do not overwrite the baseline."
            : "BASELINE PREVIEW — Press Run new scenario to calculate the inputs above."}
        </div>

        <div className="scenario-summary">
          <div>
            <h3>Scenario summary</h3>
            <p>
              {result
                ? "Verified temporary overlay based on supported V2 levers."
                : "Inputs are staged; results below still show the baseline."}
            </p>
          </div>

          <div className="lever-card negative">
            <small>Revenue</small>
            <b>
              {Number(revenue) > 0
                ? "+"
                : ""}
              {revenue}%
            </b>
            <span>vs. base case</span>
          </div>

          <div className="lever-card negative">
            <small>Operating costs</small>
            <b>
              {Number(cost) > 0
                ? "+"
                : ""}
              {cost}%
            </b>
            <span>vs. base case</span>
          </div>

          <div className="lever-card">
            <small>Time horizon</small>
            <b>13 weeks</b>
            <span>temporary analysis</span>
          </div>
        </div>

        {result?.applied_changes?.length > 0 && (
          <div className="scenario-applied-changes">
            <b>Engine-confirmed changes</b>
            <ul>{result.applied_changes.map((change, i) => <li key={i}>{String(change)}</li>)}</ul>
          </div>
        )}
        {scenarioHistory.length > 0 && (
          <details className="scenario-run-history">
            <summary>Previous verified scenario runs ({scenarioHistory.length})</summary>
            {scenarioHistory.map(item => (
              <button type="button" key={item.id} onClick={() => {
                setRevenue(item.revenue);
                setCost(item.cost);
                setManagementReserve(item.reserve);
                setResult(item.result);
                setError("");
              }}>
                <b>{item.at}</b>
                <span>Revenue {item.revenue}% · costs {item.cost}% · reserve {item.reserve === "" ? "baseline" : money(item.reserve)}</span>
                <strong>Min cash {money(item.result.result.position.minimum_cash)} · breach risk {pct(item.result.result.risk.probability)}</strong>
              </button>
            ))}
          </details>
        )}
        {result && data && (
          <div className="scenario-baseline-compare">
            <b>BASELINE VS. VERIFIED SCENARIO</b>
            <div><span>Minimum cash</span>
              <strong>{money(data.position.minimum_cash)}</strong>
              <span>→</span><strong>{money(active.position.minimum_cash)}</strong></div>
            <div><span>Reserve-breach risk</span>
              <strong>{pct(data.risk.probability)}</strong>
              <span>→</span><strong>{pct(active.risk.probability)}</strong></div>
          </div>
        )}
        <div className="kpi-grid">
          <KpiCard
            icon="▱"
            label="CURRENT CASH"
            value={money(
              active.position.current_cash
            )}
            note="Current verified starting position"
          />

          <KpiCard
            icon="↘"
            label="MINIMUM PROJECTED CASH"
            value={money(
              active.position.minimum_cash
            )}
            note={
              `Week ${
                active.position
                  .minimum_cash_week
              }`
            }
            tone={active.position.minimum_headroom < 0 ? "critical" : ""}
          />

          <KpiCard
            icon="△"
            label="RESERVE-BREACH PROBABILITY"
            value={pct(
              active.risk.probability
            )}
            note={
              `vs. ${
                pct(
                  active.risk
                    .risk_appetite
                )
              } appetite`
            }
            tone={active.risk.probability != null &&
              active.risk.probability > active.risk.risk_appetite ? "critical" : ""}
          />

          <KpiCard
            icon="▣"
            label="FIRST RESERVE BREACH"
            value={
              active.position
                .first_breach_week
                ? (
                  `Week ${
                    active.position
                      .first_breach_week
                  }`
                )
                : "No breach"
            }
            note="Verified scenario result"
          />
        </div>

        <div className="main-grid">
          <CashChart
            data={active}
            showScenario
          />

          <div className="recommendation-card">
            <div className="recommendation-head">
              <h3>
                ◎ Management recommendation
              </h3>

              <span className={result ? "green" : "status-pending"}>
                {result ? "● VERIFIED SCENARIO" : "○ BASELINE"}
              </span>
            </div>

            <div className={`recommendation-alert ${active.insight.tone || ""}`}>
              <b>
                {active.insight.title}
              </b>

              <span>
                {active.insight.next_step}
              </span>
            </div>

            <div className="driver-heading">
              KEY DRIVER IMPACTS
            </div>

            {active.cash_drivers
              .slice(0, 3)
              .map(
                driver => (
                  <div
                    className="driver-row"
                    key={driver.event_id}
                  >
                    <div>
                      <b>
                        {driver.category}
                      </b>
                      <small>
                        {money(
                          driver.amount
                        )}
                      </small>
                    </div>
                  </div>
                )
              )}
          </div>
        </div>
      </div>
    </>
  );
}


function RecoveryPage({ scenarioId, importedMode = false }) {
  const [targetScenarioId, setTargetScenarioId] = useState("stressed_recoverable");
  const [error, setError] = useState("");
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [
    payload,
    setPayload,
  ] = useState(null);

  const [
    selected,
    setSelected,
  ] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setPayload(null);
    setError("");
    setDetailsOpen(false);
    fetch(`${API}/recovery-options/${encodeURIComponent(targetScenarioId)}`)
      .then(async response => {
        const body = await response.json();
        if (!response.ok) throw new Error(body.detail || "Recovery request failed");
        return body;
      })
      .then(body => { if (!cancelled) {setPayload(body); setSelected(0);} })
      .catch(err => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [targetScenarioId]);

  if (!payload) {
    return <>
      <Hero eyebrow="RECOVERY INTELLIGENCE" title="Recovery" accent="Decision Center"
        subtitle="Verified recovery plans are generated only for scenarios with configured recovery constraints."
        features={[["◇", "Engine-backed plans", "No fabricated results"]]}/>
      <div className="product-surface">
        {error ? <div className="workflow-notice" role="alert">
          <strong>Recovery is unavailable for this scenario.</strong> {error}
          <button type="button" onClick={() => setTargetScenarioId("stressed_recoverable")}>
            Open validated stressed recovery example →
          </button>
        </div> : <Loading />}
      </div>
    </>;
  }

  const options = payload.options;
  const active = options[selected];

  return (
    <>
      <Hero
        eyebrow="RECOVERY INTELLIGENCE"
        title="Recovery"
        accent="Decision Center"
        subtitle={
          "Compare verified recovery strategies and "
          + "the trade-off between operating intervention "
          + "and external liquidity."
        }
        features={[
          [
            "▱",
            "Reserve Gap",
            money(
              Math.abs(
                payload.scenario
                  .position
                  .minimum_headroom
              )
            ),
          ],
          [
            "◇",
            "Verified Alternatives",
            "Every option reruns the recovery engine",
          ],
          [
            "✓",
            "Probabilistic Validation",
            "Compare outcomes with management appetite",
          ],
        ]}
      />

      <div className="product-surface">
        <div className="recovery-context">
          <div>
            <b>Recovery evidence: {payload.scenario.scenario.name}</b>
            <p>{importedMode
              ? "DEMO ONLY — this recovery comparison is not based on your uploaded company. Custom recovery constraints are not connected yet."
              : targetScenarioId === scenarioId
                ? "Evaluating recovery constraints for the selected scenario."
                : "This page shows a separate verified recovery example, not the active Command Center scenario."}</p>
          </div>
          {!importedMode && targetScenarioId !== scenarioId && <button type="button" onClick={() => setTargetScenarioId(scenarioId)}>
            Try current scenario →
          </button>}
          {targetScenarioId !== "stressed_recoverable" && <button type="button" onClick={() => setTargetScenarioId("stressed_recoverable")}>
            View recovery example
          </button>}
        </div>
        <div className="recovery-cards">
          {options.map(
            (option, index) => (
              <button
                className={
                  selected === index
                    ? "recovery-card selected"
                    : "recovery-card"
                }
                onClick={() => (
                  setSelected(index)
                )}
                key={option.name}
              >
                <div className="recovery-title">
                  <span className="recovery-icon">
                    {index === 0
                      ? "⚖"
                      : index === 1
                        ? "▱"
                        : "◇"}
                  </span>

                  <div>
                    <h3>{option.name}</h3>
                    <p>{option.subtitle}</p>
                  </div>

                  {index === 0 && (
                    <span className="recommended-chip">
                      ✦ RECOMMENDED
                    </span>
                  )}
                </div>

                <div className="recovery-metrics">
                  <div>
                    <small>
                      External liquidity
                    </small>
                    <b>
                      {money(
                        option.plan
                          .external_liquidity
                      )}
                    </b>
                  </div>

                  <div>
                    <small>
                      Resulting minimum cash
                    </small>
                    <b>
                      {money(
                        option.evaluation
                          .resulting_min_cash
                      )}
                    </b>
                  </div>

                  <div>
                    <small>
                      Breach risk after
                    </small>
                    <b>
                      {pct(
                        option.validation
                          .reserve_breach_probability
                      )}
                    </b>
                  </div>
                </div>

                <div className="recovery-actions">
                  <b>Recovery actions</b>
                  <span>
                    Revenue recovery:{" "}
                    {option.plan
                      .revenue_improvement_pct}%
                  </span>
                  <span>
                    Cost reduction:{" "}
                    {option.plan
                      .cost_reduction_pct}%
                  </span>
                  <span>
                    Collections faster:{" "}
                    {option.plan
                      .receivable_acceleration_days} days
                  </span>
                </div>
              </button>
            )
          )}
        </div>

        <div className="two-table-grid">
          <div className="table-card">
            <h3>
              ▥ Management trade-offs
            </h3>

            <table className="data-table">
              <thead>
                <tr>
                  <th>Metric</th>
                  {options.map(
                    option => (
                      <th key={option.name}>
                        {option.name}
                      </th>
                    )
                  )}
                </tr>
              </thead>

              <tbody>
                <tr>
                  <td>External liquidity</td>
                  {options.map(
                    option => (
                      <td key={option.name}>
                        {money(
                          option.plan
                            .external_liquidity
                        )}
                      </td>
                    )
                  )}
                </tr>

                <tr>
                  <td>Resulting minimum cash</td>
                  {options.map(
                    option => (
                      <td key={option.name}>
                        {money(
                          option.evaluation
                            .resulting_min_cash
                        )}
                      </td>
                    )
                  )}
                </tr>

                <tr>
                  <td>Deterministic feasible</td>
                  {options.map(
                    option => (
                      <td key={option.name}>
                        {option.evaluation.feasible
                          ? "YES"
                          : "NO"}
                      </td>
                    )
                  )}
                </tr>
              </tbody>
            </table>
          </div>

          <div className="table-card">
            <h3>
              ▥ Probabilistic validation
            </h3>

            <table className="data-table">
              <thead>
                <tr>
                  <th>Metric</th>
                  {options.map(
                    option => (
                      <th key={option.name}>
                        {option.name}
                      </th>
                    )
                  )}
                </tr>
              </thead>

              <tbody>
                <tr>
                  <td>Allowed risk</td>
                  {options.map(
                    option => (
                      <td key={option.name}>
                        {pct(
                          option.validation
                            .max_acceptable_breach_probability
                        )}
                      </td>
                    )
                  )}
                </tr>

                <tr>
                  <td>Breach risk after</td>
                  {options.map(
                    option => (
                      <td
                        key={option.name}
                        className={option.validation.within_risk_appetite ? "green" : "red"}
                      >
                        {pct(
                          option.validation
                            .reserve_breach_probability
                        )}
                      </td>
                    )
                  )}
                </tr>

                <tr>
                  <td>Within appetite</td>
                  {options.map(
                    option => (
                      <td key={option.name}>
                        <span className={
                          option.validation
                            .within_risk_appetite
                            ? "yes-pill"
                            : "no-pill"
                        }>
                          {
                            option.validation
                              .within_risk_appetite
                              ? "✓ YES"
                              : "✕ NO"
                          }
                        </span>
                      </td>
                    )
                  )}
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div className={active.evaluation.feasible && active.validation.within_risk_appetite
          ? "success-strip" : "success-strip unfeasible"}>
          <div className="success-icon">
            {active.evaluation.feasible && active.validation.within_risk_appetite ? "✓" : "!"}
          </div>

          <div>
            <b>
              {active.evaluation.feasible && active.validation.within_risk_appetite
                ? "Selected plan: " : "Selected plan requires review: "}
              {active.name}
            </b>

            <p>
              Resulting minimum cash{" "}
              {money(
                active.evaluation
                  .resulting_min_cash
              )}; modeled breach risk{" "}
              {pct(
                active.validation
                  .reserve_breach_probability
              )}.
              {(!active.evaluation.feasible || !active.validation.within_risk_appetite)
                && " This plan is not within the currently verified feasibility/risk limits."}
            </p>
          </div>

          <button type="button" onClick={() => setDetailsOpen(true)}>
            View recovery plan details →
          </button>
        </div>
        {detailsOpen && <div className="details-backdrop" role="presentation"
          onClick={() => setDetailsOpen(false)}>
          <section className="details-dialog" role="dialog" aria-modal="true"
            aria-label="Verified recovery plan details" onClick={event => event.stopPropagation()}>
            <div className="details-heading">
              <div>
                <small>ENGINE-VERIFIED RECOVERY EVIDENCE</small>
                <h2>{active.name}</h2>
                <p>{payload.scenario.scenario.name} · analysis from the recovery API</p>
              </div>
              <button type="button" onClick={() => setDetailsOpen(false)}>✕ Close</button>
            </div>
            <div className="details-metrics">
              <div><small>External liquidity</small><b>{money(active.plan.external_liquidity)}</b></div>
              <div><small>Resulting minimum cash</small><b>{money(active.evaluation.resulting_min_cash)}</b></div>
              <div><small>Reserve breach probability</small><b>{pct(active.validation.reserve_breach_probability)}</b></div>
              <div><small>Allowed probability</small><b>{pct(active.validation.max_acceptable_breach_probability)}</b></div>
            </div>
            <h3>Operating interventions</h3>
            <div className="details-metrics">
              <div><small>Revenue recovery</small><b>{active.plan.revenue_improvement_pct}%</b></div>
              <div><small>Cost reduction</small><b>{active.plan.cost_reduction_pct}%</b></div>
              <div><small>Collection acceleration</small><b>{active.plan.receivable_acceleration_days} days</b></div>
            </div>
            <div className={active.evaluation.feasible && active.validation.within_risk_appetite
              ? "workflow-notice success" : "workflow-notice"}>
              Deterministic feasibility: <b>{active.evaluation.feasible ? "YES" : "NO"}</b>
              {" · "}Within management risk appetite: <b>{active.validation.within_risk_appetite ? "YES" : "NO"}</b>
            </div>
            <details className="recovery-raw">
              <summary>View full verified engine response</summary>
              <pre>{JSON.stringify({
                plan: active.plan,
                evaluation: active.evaluation,
                validation: active.validation
              }, null, 2)}</pre>
            </details>
          </section>
        </div>}
      </div>
    </>
  );
}


function CustomerPage({
  setPage,
  onImported,
}) {
  const today = (
    new Date()
      .toISOString()
      .slice(0, 10)
  );

  const [
    company,
    setCompany,
  ] = useState("My Company");

  const [
    startDate,
    setStartDate,
  ] = useState(today);

  const [
    openingCash,
    setOpeningCash,
  ] = useState(250000);

  const [
    reserve,
    setReserve,
  ] = useState(75000);

  const [
    risk,
    setRisk,
  ] = useState(10);

  const [
    uncertainty,
    setUncertainty,
  ] = useState("Standard");

  const [
    method,
    setMethod,
  ] = useState("template");

  const [
    file,
    setFile,
  ] = useState(null);

  const [
    message,
    setMessage,
  ] = useState("");

  const upload = async () => {
    if (!file) {
      setMessage(
        "Choose a RiskPilot cash-event CSV first."
      );
      return;
    }

    const form = new FormData();

    form.append("file", file);
    form.append(
      "company_name",
      company
    );
    form.append(
      "forecast_start",
      startDate
    );
    form.append(
      "opening_cash",
      openingCash
    );
    form.append(
      "management_reserve",
      reserve
    );
    form.append(
      "max_breach_probability",
      Number(risk) / 100
    );
    form.append(
      "uncertainty_profile",
      uncertainty
    );

    setMessage(
      "Validating evidence and running verified engines…"
    );

    try {
      const response = await fetch(
        `${API}/customer/import`,
        {
          method: "POST",
          body: form,
        }
      );

      const body = await response.json();

      if (!response.ok) {
        throw new Error(
          body.detail
          || "Import failed"
        );
      }

      onImported(body);

      setMessage(
        `Validated ${
          body.report.rows_loaded
        } cash events.`
      );

      setPage("command");
    } catch (error) {
      setMessage(error.message);
    }
  };

  return (
    <>
      <Hero
        eyebrow="CASH EVIDENCE ONBOARDING"
        title="Build a 13-week liquidity view from"
        accent="your own cash evidence"
        subtitle={
          "Import dated customer receipts, supplier payments, payroll, "
          + "taxes and modelled cash movements. RiskPilot validates evidence "
          + "before running the same liquidity, uncertainty and decision engines."
        }
        features={[
          [
            "◇",
            "Validated evidence",
            "Checks and reconciles your data before analysis",
          ],
          [
            "▥",
            "Same proven engines",
            "Uses the Command Center liquidity and uncertainty engines",
          ],
          [
            "✦",
            "Management-ready insights",
            "Turn finance data into clear forecasts and actions",
          ],
        ]}
      />

      <div className="product-surface customer-layout">
        <div className="step-rail">
          {[
            [
              "1",
              "Configure policy",
              "Set your policy and assumptions",
            ],
            [
              "2",
              "Import cash evidence",
              "Upload your data",
            ],
            [
              "3",
              "Validate and run",
              "Build your 13-week view",
            ],
          ].map(
            ([number, title, copy]) => (
              <div
                className="step-item"
                key={number}
              >
                <div className={
                  number === "1"
                    ? "step-circle active"
                    : "step-circle"
                }>
                  {number}
                </div>

                <div>
                  <b>{title}</b>
                  <small>{copy}</small>
                </div>
              </div>
            )
          )}
        </div>

        <div className="customer-main">
          <div className="customer-intro-card">
            <div className="customer-icon">
              ◎
            </div>

            <div>
              <h2>
                Build a 13-week liquidity view
                from your own cash evidence
              </h2>

              <p>
                Import dated cash evidence and run
                the same verified engines used by
                the Command Center.
              </p>
            </div>
          </div>

          <section className="form-section">
            <div className="section-number">
              1
            </div>

            <div className="section-heading">
              <h3>Configure policy</h3>
              <p>
                Set the policy and assumptions for
                your 13-week liquidity view.
              </p>
            </div>

            <div className="form-grid">
              <label>
                Company / workspace name
                <input
                  value={company}
                  onChange={e => (
                    setCompany(
                      e.target.value
                    )
                  )}
                />
              </label>

              <label>
                Opening cash (USD)
                <input
                  type="number"
                  value={openingCash}
                  onChange={e => (
                    setOpeningCash(
                      e.target.value
                    )
                  )}
                />
              </label>

              <label>
                Maximum breach risk (%)
                <input
                  type="number"
                  value={risk}
                  onChange={e => (
                    setRisk(
                      e.target.value
                    )
                  )}
                />
              </label>

              <label>
                Forecast start date
                <input
                  type="date"
                  value={startDate}
                  onChange={e => (
                    setStartDate(
                      e.target.value
                    )
                  )}
                />
              </label>

              <label>
                Minimum cash reserve (USD)
                <input
                  type="number"
                  value={reserve}
                  onChange={e => (
                    setReserve(
                      e.target.value
                    )
                  )}
                />
              </label>

              <label>
                Uncertainty basis
                <select
                  value={uncertainty}
                  onChange={e => (
                    setUncertainty(
                      e.target.value
                    )
                  )}
                >
                  <option value="Low">
                    Conservative operating profile
                  </option>
                  <option value="Standard">
                    Standard operating profile
                  </option>
                  <option value="High">
                    High-volatility operating profile
                  </option>
                </select>
              </label>
            </div>
          </section>

          <section className="form-section">
            <div className="section-number">
              2
            </div>

            <div className="section-heading">
              <h3>Import cash evidence</h3>

              <p>
                Choose how to import your cash data.
              </p>
            </div>

            <div className="method-cards">
              {[
                [
                  "template",
                  "RiskPilot template",
                  "Use our CSV template (recommended)",
                ],
                [
                  "mapping",
                  "Map existing CSV / Excel",
                  "Use your own file with column mapping",
                ],
                [
                  "multi",
                  "Multiple finance sources",
                  "Combine data from multiple systems",
                ],
              ].map(
                ([key, title, copy]) => (
                  <button
                    key={key}
                    className={
                      method === key
                        ? "method-card selected"
                        : "method-card"
                    }
                    onClick={() => (
                      setMethod(key)
                    )}
                  >
                    <span className="radio-dot" />
                    <b>{title}</b>
                    <small>{copy}</small>
                  </button>
                )
              )}
            </div>

            {method !== "template" ? (
              <CustomerAdvancedImport
                key={method}
                method={method}
                company={company}
                startDate={startDate}
                openingCash={openingCash}
                reserve={reserve}
                risk={risk}
                uncertainty={uncertainty}
                onImported={onImported}
                setPage={setPage}
              />
            ) : (
              <>
                <div className="upload-zone">
                  <div className="upload-icon">⇧</div>
                  <b>Upload a RiskPilot cash-event CSV</b>
                  <span>Choose a file containing dated cash events.</span>
                  <label className="file-button">Choose file
                    <input type="file" accept=".csv"
                      onChange={event => setFile(event.target.files[0])} />
                  </label>
                  {file && <small>Selected: {file.name}</small>}
                  <div className="template-strip">
                    <span>▤ Need a template?</span>
                    <a href={`${API}/customer/template?forecast_start=${startDate}`}>
                      Download CSV template
                    </a>
                  </div>
                </div>
                <button className="big-blue-button" onClick={upload}>
                  Validate evidence & run RiskPilot →
                </button>
                {message && <div className="import-message">{message}</div>}
              </>
            )}
          </section>
        </div>
      </div>
    </>
  );
}


function EvidencePage({
  data,
}) {
  const [selectedSource, setSelectedSource] = useState(null);
  if (!data) {
    return <Loading />;
  }

  const evidenceRows = [
    [
      "Committed",
      data.position.committed_amount,
      "Contracted / committed cash evidence",
      "green",
    ],
    [
      "Modelled",
      data.position.modelled_amount,
      "Forecast engine outputs",
      "blue",
    ],
    [
      "Management assumption",
      data.position.assumption_amount,
      "Explicit management assumptions",
      "purple",
    ],
    [
      "Public source",
      data.scenario.is_public
        ? data.events.reduce(
          (sum, event) => (
            sum + Math.abs(event.amount)
          ),
          0
        )
        : 0,
      "Public filings and source materials",
      "orange",
    ],
  ];

  return (
    <>
      <Hero
        eyebrow="METHODOLOGY & EVIDENCE"
        title="Verified evidence."
        accent="Transparent methodology."
        subtitle={
          "Traceable forecasts, documented assumptions and auditable "
          + "decision evidence. Financial engines calculate. "
          + "AI explains verified evidence."
        }
        features={[
          [
            "◇",
            "Verified Financial Engines",
            "Engine-calculated financial values",
          ],
          [
            "▥",
            "Transparent Provenance",
            "Trace evidence to its source",
          ],
          [
            "✦",
            "AI Explanations",
            "Explain verified engine evidence",
          ],
        ]}
      />

      <div className="product-surface">
        <div className="governance-header">
          <div>
            <h2>
              ◇ AI Model Governance Recommendation
            </h2>

            <p>
              Current 13-week liquidity engine and
              evidence-governance view.
            </p>
          </div>

          <span className="verified-chip">
            ● VERIFIED
          </span>
        </div>

        <div className="evidence-grid">
          <div className="governance-card">
            <div className="success-panel">
              <span className="success-icon">
                ✓
              </span>

              <div>
                <h3>
                  Verified engine boundary preserved
                </h3>

                <p>
                  Financial values remain outputs
                  of RiskPilot engines; AI is used
                  for interpretation and orchestration.
                </p>
              </div>
            </div>

            <div className="governance-metrics">
              <div>
                <b>
                  {data.risk.simulations.toLocaleString()}
                </b>
                <span>
                  Simulated paths
                </span>
              </div>

              <div>
                <b>
                  {pct(
                    data.position
                      .evidence_coverage
                  )}
                </b>
                <span>
                  Evidence coverage
                </span>
              </div>

              <div>
                <b>
                  13 weeks
                </b>
                <span>
                  Direct-cash horizon
                </span>
              </div>

              <div>
                <b>
                  {pct(
                    data.risk
                      .risk_appetite
                  )}
                </b>
                <span>
                  Management appetite
                </span>
              </div>
            </div>
          </div>

          <div className="classification-card">
            <h3>
              ◎ Evidence basis & classification
            </h3>

            {evidenceRows.map(
              (
                [name, amount, copy, tone]
              ) => (
                <div
                  className="classification-row"
                  key={name}
                >
                  <span className={
                    `classification-icon ${tone}`
                  }>
                    ▤
                  </span>

                  <div>
                    <b>{name}</b>
                    <small>{copy}</small>
                  </div>

                  <strong>
                    {money(amount)}
                  </strong>
                </div>
              )
            )}
          </div>
        </div>

        <div className="evidence-grid lower">
          <div className="table-card">
            <h3>▱ Source provenance</h3>

            <table className="data-table">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Type</th>
                  <th>Items</th>
                </tr>
              </thead>

              <tbody>
                {data.sources.map(
                  (
                    source,
                    index
                  ) => (
                    <tr key={index}>
                      <td><button type="button" className="source-link"
                        onClick={() => setSelectedSource({ name: source.name, type: source.type })}>
                        {source.name} ↗
                      </button></td>
                      <td>{source.type}</td>
                      <td>{source.items}</td>
                    </tr>
                  )
                )}
              </tbody>
            </table>
            {selectedSource && <div className="source-events">
              <div className="details-heading">
                <div><b>Source details: {selectedSource.name}</b>
                  <p>Events supplied by the current API response. This is not an external filing viewer.</p></div>
                <button type="button" onClick={() => setSelectedSource(null)}>✕ Close</button>
              </div>
              <table className="data-table"><thead><tr>
                <th>Event ID</th><th>Cash date</th><th>Category</th><th>Amount</th>
              </tr></thead><tbody>
                {data.events.filter(event =>
                  (event.source_reference || "RiskPilot source") === selectedSource.name
                  && event.source_type === selectedSource.type
                ).map(event => <tr key={event.event_id}>
                  <td>{event.event_id}</td><td>{event.date}</td>
                  <td>{event.category}</td><td>{money(event.amount)}</td>
                </tr>)}
              </tbody></table>
            </div>}
          </div>

          <div className="audit-card">
            <h3>
              ◇ Audit trail & model lineage
            </h3>

            {[
              [
                "Data ingested",
                `${data.events.length} cash events classified`,
              ],
              [
                "Financial engines executed",
                `${data.risk.simulations.toLocaleString()} uncertainty paths`,
              ],
              [
                "Governance checks",
                "Reserve, risk appetite and evidence basis preserved",
              ],
              [
                "AI explanation layer",
                "Agent may explain verified results and sources",
              ],
            ].map(
              (
                [title, copy],
                index
              ) => (
                <div
                  className="audit-row"
                  key={title}
                >
                  <span>
                    {index + 1}
                  </span>

                  <div>
                    <b>{title}</b>
                    <small>{copy}</small>
                  </div>
                </div>
              )
            )}
          </div>
        </div>
      </div>
    </>
  );
}


export default function App() {
  const [
    page,
    setPage,
  ] = useState("command");

  const [
    scenarios,
    setScenarios,
  ] = useState([]);

  const [
    scenarioId,
    setScenarioId,
  ] = useState(
    "public_sec_cenveo"
  );

  const [
    data,
    setData,
  ] = useState(null);

  const [
    importedData,
    setImportedData,
  ] = useState(null);

  const [customerSession, setCustomerSession] = useState(null);
  const [agentHistory, setAgentHistory] = useState([]);
  const [agentDraft, setAgentDraft] = useState("");
  useEffect(() => { setAgentHistory([]); setAgentDraft(""); }, [scenarioId, customerSession?.id]);
  const importCustomer = (response) => {
    if (!response?.customer_session_id || !response?.result) {
      throw new Error("Import response missing a customer analysis session.");
    }
    setCustomerSession({ id: response.customer_session_id,
      capabilities: response.capabilities });
    setImportedData(response.result);
  };
  const selectDemo = id => {
    setImportedData(null);
    setCustomerSession(null);
    setScenarioId(id);
  };

  useEffect(
    () => {
      fetch(`${API}/scenarios`)
        .then(async response => {
          if (!response.ok) throw new Error("Scenario list unavailable");
          return response.json();
        })
        .then(setScenarios)
        .catch(error => console.error(error));
    },
    []
  );

  useEffect(
    () => {
      let cancelled = false;
      setImportedData(null);
      setData(null);
      fetch(`${API}/command-center/${encodeURIComponent(scenarioId)}`)
        .then(async response => {
          const body = await response.json();
          if (!response.ok) throw new Error(body.detail || "Command Center unavailable");
          return body;
        })
        .then(body => { if (!cancelled) setData(body); })
        .catch(error => { if (!cancelled) console.error(error); });
      return () => { cancelled = true; };
    },
    [scenarioId]
  );

  const activeData = (
    importedData
    || data
  );

  return (
    <div className="app">
      <Brand
        page={page}
        setPage={setPage}
      />

      <main>
        {page === "command" && (
          <CommandCenter
            data={activeData}
            scenarios={scenarios}
            scenarioId={scenarioId}
            setScenarioId={selectDemo}
            setPage={setPage}
            importedMode={!!importedData}
            onExitCustomer={() => selectDemo(scenarioId)}
          />
        )}

        {page === "agent" && (
          <AgentPage
            data={activeData}
            scenarioId={scenarioId}
            setPage={setPage}
            importedMode={!!importedData}
            customerSessionId={customerSession?.id}
            history={agentHistory}
            setHistory={setAgentHistory}
            initialQuestion={agentDraft}
            key={scenarioId + (importedData ? "-customer" : "-demo")}
          />
        )}

        {page === "scenario" && (
          <ScenarioPage
            data={activeData}
            scenarioId={scenarioId}
            scenarios={scenarios}
            setScenarioId={selectDemo}
            importedMode={!!importedData}
            customerSessionId={customerSession?.id}
            customerCapabilities={customerSession?.capabilities}
            onAskAgent={text => { setAgentDraft(text); setPage("agent"); }}
            key={scenarioId + (importedData ? "-customer" : "-demo")}
          />
        )}

        {page === "recovery" && (
          <RecoveryPage scenarioId={scenarioId} importedMode={!!importedData} />
        )}

        {page === "customer" && (
          <CustomerPage
            setPage={setPage}
            onImported={importCustomer}
          />
        )}

        {page === "evidence" && (
          <EvidencePage
            data={activeData}
          />
        )}
      </main>
    </div>
  );
}
