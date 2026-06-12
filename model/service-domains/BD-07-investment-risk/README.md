# BD-07 — Investment Risk

**Office:** Middle.

**Maturity:** Provisional · 8 Service Domains for market, credit, liquidity, concentration, stress, and climate-risk analytics, with limits governance

The investment-risk capability — the independent function that measures and controls the risk in the firm's investment activity. Where the front office (BD-01 to BD-06) decides what to hold and trades it, Investment Risk is the **second line of defence**: it measures the economic risk in the resulting portfolio — market, credit, liquidity, concentration — against the firm's declared risk appetite, challenges the front office's positioning, and escalates breaches. It is the first of the middle-office Business Domains.

Each Service Domain below is its own file.

## Service Domains

| ID | Service Domain | Applies | What it does |
|---|---|---|---|
| SD-07.1 | [Market Risk Management](SD-07.1-market-risk-management.md) | BOTH | Measures and controls exposure to price, rate, spread and volatility movements. |
| SD-07.2 | [Credit & Counterparty Risk Management](SD-07.2-credit-and-counterparty-risk-management.md) | BOTH | Measures issuer credit risk and trading-counterparty exposure and default risk. |
| SD-07.3 | [Liquidity Risk Management](SD-07.3-liquidity-risk-management.md) | BOTH | Assesses the portfolio's ability to meet its obligations and the liquidity of its holdings under stress. |
| SD-07.4 | [Concentration & Exposure Risk](SD-07.4-concentration-and-exposure-risk.md) | BOTH | Monitors single-name, sector, geography, vintage and factor concentration. |
| SD-07.5 | [Look-Through Exposure Analysis](SD-07.5-look-through-exposure-analysis.md) | BOTH | Decomposes fund and pooled holdings into underlying exposures for true risk aggregation. |
| SD-07.6 | [Scenario Analysis & Stress Testing](SD-07.6-scenario-analysis-and-stress-testing.md) | BOTH | Runs hypothetical and historical scenarios across the total portfolio. |
| SD-07.7 | [Investment Risk Reporting & Limits Governance](SD-07.7-investment-risk-reporting-and-limits-governance.md) | BOTH | Maintains the risk-limit framework and produces consolidated risk reporting to governance bodies. |
| SD-07.8 | [Climate Risk Analytics](SD-07.8-climate-risk-analytics.md) | BOTH | Measures the portfolio's climate exposure — carbon footprint, physical- and transition-risk measures, net-zero pathway position. |

## Two measurement paradigms — no default

BD-07's risk methods do not assume liquid markets. Risk is measured in two paradigms, and BD-07 carries both:

- **The continuously-priced paradigm** — value-at-risk, expected shortfall, factor and tracking-error models, the Greeks, daily-priced stress tests. It works because public markets reprice daily.
- **The non-priced paradigm** — for private markets and illiquid real assets, where there are no daily prices, valuations are stale and smoothed ("volatility laundering"), and the J-curve, vintage concentration and capital-call timing are the real risks. Risk here is measured by commitment and cash-flow modelling, NAV de-smoothing, smoothing-adjusted return statistics, and liquidity-adjusted value-at-risk.

SD-07.1, SD-07.3 and SD-07.6 are reframed to carry both paradigms; SD-07.4 carries vintage concentration. An asset owner with a large private-markets allocation needs both paradigms at once — which is itself the proof that the value-at-risk model is not the universal default. There is no separate "private-markets risk" Service Domain: risk is one capability per type, measured by whichever paradigm the asset's market structure dictates. **SD-07.8 Climate Risk Analytics adds a third lens** — climate risk is an investment exposure, measured here against appetite, alongside the market, credit and liquidity lenses.

## Archetype activation

BD-07's capabilities are a union an implementation switches on; the *shape* of the risk function varies more by archetype than almost any other Business Domain.

| Archetype | BD-07 | What differs |
|---|---|---|
| Third-party asset manager | Full | Periodic independent oversight — fund-by-fund risk scans, scheduled portfolio-manager challenge, risk-committee reporting |
| Hedge fund | Full | A real-time, pre-trade and intraday risk desk — exposure, leverage and drawdown limits enforced by infrastructure |
| Asset owner (pension / SWF / endowment) | Full | Total-fund risk and, for a pension, funded-status / surplus risk — both measurement paradigms at once |
| Insurer | Full | Investment risk integrated into the regulatory-capital framework — Solvency II SCR, the Own Risk and Solvency Assessment, asset-liability matching |
| Index / passive manager | Partial | A thin function — tracking-error and replication risk, most capabilities dormant |
| Wealth manager / private bank | Full | Per-client suitability risk and single-name concentration at the client-portfolio level |

The common core, true of every archetype: **an independent second-line function that measures investment exposure against a declared appetite, challenges the front office, escalates breaches and reports to a governance body.** Everything above that is archetype-specific. SD-07.8 Climate Risk Analytics activates in proportion to climate-disclosure obligation — heaviest for asset owners, insurers and large asset managers under TCFD / ISSB / SFDR, lighter for the hedge fund and the smaller wealth manager.

**Why the manager-archetype row is split into sub-archetypes.** The discriminator the sub-archetype rows divide on in BD-07 is the **dominant risk type** — the manager-archetype row is sub-typed because the risk paradigm that dominates differs sharply by manager type, and the risk function takes its shape from that dominant type. A third-party asset manager runs market and tracking-error risk as the spine with periodic challenge cadences; an index / passive manager's risk function is a thin tracking-error and replication-risk discipline; a hedge fund runs a real-time, pre-trade and intraday risk desk where leverage, drawdown and counterparty exposure are the binding metrics, infrastructure-enforced. The dominant-risk-type discriminator is what the sub-typing makes visible; collapsing it would assert one risk shape across managers that the second-line function does not have.

## Wider-source grounding

Grounded against external industry references:

- The **CFA Institute** risk-management process — risk governance, identification, measurement, mitigation, communication.
- The **GARP Buy Side Risk Managers Forum** *Risk Principles for Asset Managers* and *Liquidity Risk Principles* — the closest external analogue to BD-07, and the evidence that operational risk sits *outside* investment risk.
- Market-risk methodology — value-at-risk (parametric, historical-simulation, Monte Carlo), expected shortfall, factor and tracking-error models, the Greeks; the vendor risk models (MSCI Barra, RiskMetrics, Aladdin Risk).
- The **three-lines-of-defence** model; the Financial Stability Board risk-appetite-framework principles; SR 11-7 model risk.
- **TCFD / ISSB IFRS S2** (the climate-risk Risk Management pillar), **PCAF** financed-emissions methodology and the **NGFS** climate scenarios — SD-07.8 Climate Risk Analytics.
- The public-markets / private-markets measurement divide, and the institution-archetype panel.

## Non-overlap — where the boundaries run

- **BD-07 vs BD-05 Portfolio Management (cross-Business-Domain).** BD-05 is the **first line of defence** — the portfolio manager takes risk to generate return and monitors the portfolio to manage it. BD-07 is the independent **second line** — it measures and constrains that risk, independent of the portfolio manager, and challenges the positioning. The same portfolio, a different line of defence; BD-07's reporting flows back into BD-05's decisions.
- **BD-07 vs BD-10 Investment Compliance & Guideline Monitoring (cross-Business-Domain).** SD-07.7 governs **risk-appetite-derived** limits — value-at-risk, tracking error, concentration, the economic risk the firm chooses to bear. SD-10.1 and SD-10.2 own **mandate- and regulatory-derived** limits — the rules a portfolio must obey. A single position can breach both; the *source* of the limit decides which domain owns it.
- **SD-07.4 Concentration vs SD-07.5 Look-Through.** Look-through is the *input mechanism* — it decomposes pooled vehicles into their underlying constituents. Concentration is the *measurement and limit* layer that runs on the look-through output. Two Service Domains because look-through is a heavy data capability in its own right.
- **Operational risk is not BD-07.** The risk of running the *firm* — process, people, systems, fraud, cyber, business continuity — is enterprise risk, owned by SD-14.1 Enterprise & Operational Risk Management.
- **Model governance is not BD-07.** The firm-wide model inventory and independent model validation are **SD-14.4 Model Governance & AI Governance**. The investment-risk function's monitoring of its *own* value-at-risk and factor models is an operation within SD-07.1 and SD-07.6.
- **SD-07.8 Climate Risk Analytics vs SD-13.9 / SD-07.6 / SD-09.5.** SD-07.8 *measures* the portfolio's climate exposure. The climate *data* it runs on — emissions data, climate indicators — is SD-13.9 ESG & Sustainability Data (BD-13). The climate *scenarios* — the NGFS transition and physical pathways — are run by SD-07.6 Scenario Analysis & Stress Testing as one family in its governed scenario library; SD-07.8 consumes SD-07.6's scenario outputs. SD-09.5 Investment Analytics & Insight *consumes* SD-07.8's climate measures as a forward-looking portfolio diagnostic. SD-13.9 supplies the data; SD-07.6 runs the scenario; SD-07.8 measures the exposure; SD-09.5 consumes the measure.
- **SD-07.3 Liquidity Risk Management vs SD-01.11 Liquidity Strategy & Tiering (cross-Business-Domain).** SD-01.11 sets the *tier taxonomy and placement rules* — the buckets, the buffer, the liquid-to-illiquid linking policy. SD-07.3 *applies* that taxonomy to *produce* the per-holding liquidity classification (recorded as Risk Measurement, E-19 `risk_type = liquidity`) and *measures* liquidity risk in the resulting portfolio — the held-portfolio's ability to meet its obligations and the liquidity of its holdings under stress. SD-01.11 sets the policy; SD-07.3 produces the classification and measures the risk against it; SD-05.6 and SD-11.2 consume the classification. The bilateral of the boundary stated in the BD-01 README.
- **BD-07 vs BD-08 Valuation & Pricing (cross-Business-Domain).** BD-08 produces the *value* — the governed, independently-verified mark on every holding. BD-07 *measures the risk* in that value — how much it can move, under what scenario, against what appetite. They share the curve and market-data inputs but answer different questions; BD-07 consumes BD-08's marks as the input to value-at-risk, scenario and exposure measurement.
- **SD-07.5 Look-Through Exposure Analysis vs SD-03.6 GP & Manager Monitoring (cross-Business-Domain).** SD-07.5 *decomposes* fund and pooled holdings into underlying exposures for firm-wide risk aggregation — the look-through input to concentration, market and stress measurement across every manager and fund the firm holds. SD-03.6 *monitors a single manager* — that manager's holdings as one input to manager oversight (performance, organisational health, key people). SD-03.6 watches one manager; SD-07.5 aggregates across all.

## Design notes

- **Two paradigms.** Risk methods cover both the public-markets value-at-risk paradigm and the private-markets non-priced paradigm — the same asset-class-skew correction the BD-04 and BD-06 expansions applied.
- **SD-07.8 Climate Risk Analytics is an investment-risk capability.** Climate risk is an investment exposure, and measuring exposure against appetite is BD-07's purpose (the TCFD / ISSB Risk Management pillar). The standalone climate-scenario operation folds into SD-07.6 (climate is a scenario family, not a separate capability); the climate *data* sits in BD-13 as part of SD-13.9.
- **No new entities.** BD-07 consumes the holding, valuation, market-data and ESG / climate-data entities and produces risk measurements; it is configured by Risk Limit (E-16) and Scenario (E-17), and records into Risk Measurement (E-19) and Limit Breach (E-18).
- **Panel-substitution rationale — asset-owner collapse.** The single "Asset owner (pension / SWF / endowment)" row collapses DBP and SWF-E — BD-07's discriminating axis is **the measurement paradigm and its independence from the front office**, not the asset-owner sub-archetype. The DB-pension funded-status / surplus measure and the SWF total-fund measure run on the same capability shape: an independent second-line function measuring exposure against appetite, with the pension's surplus-risk paradigm a configuration of the same SD-07.6 / SD-07.7 machinery the SWF's total-fund measure also uses. The Insurer keeps its own row (Solvency II SCR, the ORSA, regulatory-capital integration) — it is not included in the collapse.

## How BD-07 relates to the rest of the model

- **Consumes** the book-of-record and market-data entities — Holding / Position (E-04, `book = ibor` for intraday measures, `book = abor` for period-end), Valuation (E-07, any `method`), Price & Market Data (E-08), Portfolio / Mandate (E-03) — and, for private-markets risk, LP Commitment (PM-06), Capital Call (PM-07) and Fund Investment (PM-09).
- **Owns** the risk-configuration and risk-record entities: Risk Limit (E-16) and Limit Breach (E-18) are owned by SD-07.7; Scenario (E-17) is owned by SD-07.6; Risk Measurement (E-19) is the append-only record the risk Service Domains produce.
- **Feeds** the front office (BD-05 Portfolio Management, whose positioning it challenges), governance and the board (SD-16.1, through SD-07.7's reporting), and BD-09 Performance & Analytics (risk-adjusted performance consumes BD-07's risk measures). It consumes the look-through of the manager book that BD-03 oversight (SD-03.6) also draws on.
