# BD-14 — Enterprise Risk, Control & Assurance

**Office:** Cross-cutting — corporate.

**Maturity:** Provisional · 9 Service Domains for operational, fraud, conduct, third-party, model and cyber-risk management; internal control; legal and contract

The Business Domain that carries the firm's risk-control-and-assurance stack — the functions that keep the institution in control of itself. BD-14 decomposes how the firm identifies and manages the risk of running itself, how it meets its obligations as a licensed entity, how it protects itself from financial crime and cyber threat, how it governs the models and AI it depends on, how it stays resilient through disruption, and how it assures — to management and independently to the board — that all of this is working. It runs the three-lines-of-defence control structure plus the specialist control and governance disciplines that the modern investment manager carries, and it manages the firm's legal agreements. It does not *govern* the firm or *report* on its behalf — that is [BD-16](../BD-16-enterprise-governance-and-accountability/README.md) — and it does not *run* the firm's corporate services — that is [BD-17](../BD-17-corporate-services-and-resources/README.md).

Each Service Domain below is its own file.

## Service Domains

| ID | Service Domain | Applies | What it does |
|---|---|---|---|
| SD-14.1 | [Enterprise & Operational Risk Management](SD-14.1-enterprise-and-operational-risk-management.md) | BOTH | The CRO function — firm-level risk appetite, the enterprise risk register, operational risk. |
| SD-14.2 | [Corporate Compliance & Conduct](SD-14.2-corporate-compliance-and-conduct.md) | BOTH | The CCO function — the compliance programme, the regulator relationship, employee conduct. |
| SD-14.3 | [Financial Crime Prevention](SD-14.3-financial-crime-prevention.md) | BOTH | The MLRO function — AML, KYC, sanctions screening, transaction monitoring. |
| SD-14.4 | [Model Governance & AI Governance](SD-14.4-model-governance-and-ai-governance.md) | BOTH | Governs the lifecycle, validation and responsible use of the firm's models and AI systems. |
| SD-14.5 | [Cyber & Information Security](SD-14.5-cyber-and-information-security.md) | BOTH | Protects the firm's information assets and systems from cyber and information-security threats. |
| SD-14.6 | [Operational Resilience & Business Continuity](SD-14.6-operational-resilience-and-business-continuity.md) | BOTH | Keeps the firm's important business services within impact tolerances through disruption. |
| SD-14.7 | [Internal Control & Assurance](SD-14.7-internal-control-and-assurance.md) | BOTH | Designs and monitors the internal-control framework and gathers the management assurance. |
| SD-14.8 | [Internal Audit](SD-14.8-internal-audit.md) | BOTH | Provides independent third-line assurance to the governing body. |
| SD-14.9 | [Legal & Contract Management](SD-14.9-legal-and-contract-management.md) | BOTH | Manages the firm's legal agreements across the investment lifecycle. |

## The three-lines control stack and the specialist disciplines

BD-14's organising line: it is the firm's **control and assurance stack** — the structure that keeps the institution in control of itself — laid out against the three-lines model and the specialist control disciplines that sit alongside it.

- **Second line** — SD-14.1 Enterprise & Operational Risk Management (the CRO function), SD-14.2 Corporate Compliance & Conduct (the CCO function), SD-14.3 Financial Crime Prevention (the MLRO function). Three functions, three officers, three external framework families — the firm's plural second line, not one Service Domain.
- **Specialist control and governance disciplines** — SD-14.4 Model Governance & AI Governance, SD-14.5 Cyber & Information Security, SD-14.6 Operational Resilience & Business Continuity. Each is a distinct, separately-tooled, regulator-shaped discipline that governs or defends a particular class of firm-level exposure.
- **Management assurance** — SD-14.7 Internal Control & Assurance designs and operates the firm's control framework, and gathers management's own assurance that the controls work.
- **Third line** — SD-14.8 Internal Audit provides independent assurance to the governing body that the other lines are effective.
- Plus **SD-14.9 Legal & Contract Management** — the firm's legal function and the governed repository of its legal agreements, the legal-risk discipline that underpins the control stack.

## The complete three-lines map

The three-lines-of-defence cut is the structural spine of BD-14:

- **Second line** — SD-14.1 (the CRO function), SD-14.2 (the CCO function), SD-14.3 (the MLRO function). Three industry-distinct functions, three different officers, three external framework families.
- **Management assurance** — SD-14.7 Internal Control & Assurance designs and operates the control framework; management's own assurance that the firm is in control.
- **Third line** — SD-14.8 Internal Audit, independent of the functions it audits, reporting functionally to the audit committee, gives the board an objective opinion.

The first line — the controls operating *inside* the investing Business Domains — is not modelled as a BD-14 Service Domain; it is distributed across the operating domains, and SD-14.7 designs the framework those first-line controls conform to.

## Where the firm-side capabilities sit

| Capability | Sits in |
|---|---|
| Operational Risk Management (not BD-07) | SD-14.1 Enterprise & Operational Risk Management |
| Model Risk Management (not BD-07) | SD-14.4 Model Governance & AI Governance |
| Personal Account Dealing & Conflicts (not BD-10) | SD-14.2 Corporate Compliance & Conduct |
| Investor / LP KYC and AML transaction monitoring (not BD-10) | SD-14.3 Financial Crime Prevention |

## Non-overlap — where the boundaries run

Service Domains are non-overlapping by construction. The boundaries inside and around BD-14 worth stating:

- **BD-14 vs BD-16 Enterprise Governance & Accountability.** BD-14 *executes control* — it runs the three-lines stack, the specialist control disciplines and the assurance functions. BD-16 *governs the firm and accounts for it* — it operates the board and fund-governance machinery and produces the assured accountability reports. The IIA Three Lines Model draws exactly this line: the governing body, and its accountability relationship, are distinct from the lines that execute control. The seam: SD-14.8 Internal Audit reports *functionally to* the audit committee that SD-16.1 operates — audit is the third line, the audit committee is a governing body; the assurance flows from BD-14 to BD-16, the two are not one domain.
- **BD-14 vs BD-17 Corporate Services & Resources.** BD-14 *controls and assures* the firm; BD-17 *runs the firm's corporate services and resources* — its finance, tax, people and technology. The IT estate is decomposed into a plan / build / run trio — SD-17.7 IT Strategy & Enterprise Architecture sets the direction and standards, SD-17.9 Application Portfolio & Engineering builds the software, SD-17.10 IT Operations & Workplace runs the production estate. SD-14.5 Cyber & Information Security is a *control over* that estate as a whole. SD-14.6 Operational Resilience & Business Continuity is a *resilience control* over the production services SD-17.10 keeps running. SD-14.4 Model Governance & AI Governance *governs* the firm's models and AI; SD-17.9 is the engineering platform they are built on; SD-17.10 the production environment they run on. BD-14 is the control layer; BD-17 is the resource layer it controls.
- **BD-14 vs BD-07 Investment Risk.** SD-14.1 owns *enterprise and operational* risk — the risk of running the firm (process, people, systems, fraud, third-party). BD-07 owns *investment* risk — the risk in the portfolio. Operational risk sits in SD-14.1, not BD-07.
- **BD-14 vs BD-10 Investment Compliance.** SD-14.2 owns *corporate* compliance and conduct — the firm's obligations as a licensed entity, and its employees' conduct. BD-10 owns *investment* compliance — the portfolio against the rules it must obey. SD-14.3 owns financial crime — screening the firm's *customers and counterparties*; SD-10.6 owns sanctions screening of *portfolio issuers*. The subject decides the owner: the firm and its people (BD-14) versus the portfolio (BD-10).
- **SD-14.5 Cyber & Information Security vs SD-14.6 Operational Resilience & Business Continuity.** Two linked but distinct disciplines: SD-14.5 *defends the systems* — threat monitoring, access management, security testing; SD-14.6 *keeps the business services available* — important business services, impact tolerances, continuity and recovery. SD-14.5 secures; SD-14.6 sustains.
- **SD-14.1 Enterprise & Operational Risk Management vs SD-14.6 Operational Resilience & Business Continuity.** SD-14.1 *identifies and assesses* what could go wrong — the operational-risk taxonomy, the risk register, the loss-event database. SD-14.6 makes the firm *resilient* to it — the impact tolerances, the continuity plans. Detection and recovery are different disciplines.
- **SD-14.7 Internal Control & Assurance vs SD-14.8 Internal Audit.** SD-14.7 *designs and operates* the control framework — first/second-line management assurance. SD-14.8 *independently tests* whether that framework is effective — third-line assurance to the governing body. Management's own assurance versus the independent opinion.
- **SD-14.7 / SD-14.8 vs SD-17.8 Vendor, Outsourcing & Service-Provider Oversight (cross-Business-Domain).** SD-14.7 *reviews* a provider's SOC 1 / ISAE 3402 control-assurance report; SD-17.8 *manages* the provider relationship — due diligence, the SLA, exit planning. SD-14.7 checks the control evidence; SD-17.8 owns the commercial relationship.
- **SD-14.9 Legal & Contract Management vs the front office.** SD-14.9 owns the *agreement as a legal document* — drafting, the governed repository, obligation tracking. The *negotiation* of an investment's commercial terms is the front office's (SD-04.6 closes a deal); the contractual *compliance* monitoring of side-letter obligations against the portfolio is SD-10.5's. SD-14.9 owns the document and the legal risk.
- **SD-14.2 Corporate Compliance & Conduct vs the BD-15 operational controls (cross-Business-Domain).** SD-14.2 *sets the conduct-compliance standard* the firm operates under — the regulatory horizon-scan, the firm-wide programme, the CCO function. Two BD-15 Service Domains *apply* that standard in their operational workflow: **SD-15.6 Marketing-Material & Financial-Promotion Approval** (the Marketing Review Committee gate on outgoing promotional material — SD-14.2 says what compliant promotion looks like, SD-15.6 applies it to each specific item) and **SD-15.16 Complaint & Client-Case Management** (first-line operational complaint handling — SD-14.2 sets the conduct standard, SD-15.16 operates the case workflow). Operational workflow placement follows where-it-runs, not which-org-function-staffs-it.
- **SD-14.4 Model Governance & AI Governance vs SD-08.2 Model-Based Valuation (cross-Business-Domain).** SD-14.4 *maintains the enterprise model inventory* and runs *independent model validation* across every model the firm depends on — the second-line governance discipline that owns the model lifecycle, the inventory and the independent validation opinion. SD-08.2 *builds, calibrates and uses* the valuation models specifically — multi-curve construction, volatility-surface calibration, structured-product valuation — as a first-line capability. SD-08.2's models are *in* the SD-14.4 inventory and are *subject to* the SD-14.4 independent validation; SD-08.2 does not own that validation.

## Archetype activation

BD-14 is among the most archetype-neutral Business Domains in the model — every institution must be controlled and assured. What varies is the weight on each discipline, not whether the stack exists.

| Archetype | BD-14 | What differs |
|---|---|---|
| Third-party asset manager | Full | The reference case — heavy corporate compliance (a registered adviser), the full three-lines stack, model governance over alpha and risk models. |
| Hedge fund | Full | Heavy financial crime (wealthy / offshore investors), trade-conduct compliance and cyber; model governance over quant models; legal-heavy ISDA / prime-brokerage agreements. |
| Private-markets manager | Full | Legal & contract management is central (LPAs, side letters, NDAs); financial crime heavy on investor KYC; lighter model governance. |
| Asset owner (pension / SWF / endowment) | Partial | Corporate-compliance-as-a-licensed-adviser is light or dormant where the asset owner manages only its own money; the conduct thread of SD-14.2 still applies; financial crime light; the control and audit stack full. |
| Insurer | Partial | The investment arm's BD-14 is often a subset embedded in a larger group control function; heavy model governance (actuarial and capital models). |
| Index / passive manager | Partial | A thin second line relative to AUM; cyber and operational resilience heavy — systemic-scale platform operations. |
| Wealth manager / private bank | Full | Heavy financial crime (retail / HNW client KYC at scale) and conduct compliance; the full control stack. |

The common core, true of every archetype: **a three-lines control stack; the specialist model, cyber and resilience disciplines; management assurance and independent internal audit; a legal function and a governed repository of agreements.** For an in-house asset owner that is not an authorised firm, the licensed-adviser thread of SD-14.2 is light — but the conduct thread, and the rest of the stack, still apply.

**Why the manager-archetype row is split into sub-archetypes.** The discriminator the sub-archetype rows divide on in BD-14 is whether the firm is a **licensed adviser running its own conduct stack** and the **group context** the investment arm sits within (standalone vs subsidiary). A third-party asset manager is a registered adviser running heavy corporate compliance, the full three-lines stack and model governance over alpha and risk models. A hedge fund weights to financial crime (wealthy / offshore investors), trade-conduct compliance and cyber, with quant-model governance and ISDA / prime-brokerage-heavy legal. A private-markets manager makes legal and contract management central (LPAs, side letters, NDAs) and investor-KYC financial-crime heavy, with lighter model governance. An index / passive manager runs a thin second line relative to AUM, but cyber and operational resilience are heavy because of systemic-scale platform operations. The licensed-adviser-and-group-context discriminator is what the sub-typing makes visible; collapsing it would assert one control-stack weighting across managers that the regulatory frame (SMCR, the Adviser Compliance Rule, the AIFM Remuneration Code) and operating model do not have.

## Wider-source grounding

Grounded against external industry references:

- The **IIA Three Lines Model** (2020) — the spine of the control structure; the evidence that the second line is plural (risk, compliance and financial crime are distinct), and that the governing body is distinct from the lines that execute control (the BD-14 / BD-16 seam).
- **COSO** — the Internal Control–Integrated Framework (SD-14.7) and ERM–Integrating with Strategy and Performance (SD-14.1); **ISO 31000** risk management.
- The **IIA Global Internal Audit Standards** (2024) — SD-14.8; **SOC 1 / ISAE 3402** and SOC 2 service-auditor reporting — SD-14.7.
- The **financial-crime frameworks** — the FATF Recommendations, the AML regimes (EU AMLD, the UK MLR, the US BSA), the sanctions regimes (OFAC, OFSI, UN, EU), the anti-bribery regimes (the UK Bribery Act, the US FCPA) — SD-14.3.
- The conduct regimes — **FCA SYSC, the SMCR, the Consumer Duty**, the SEC Advisers Act Compliance Rule and Code of Ethics rule, the CFA Institute Asset Manager Code — SD-14.2.
- **SR 11-7** model risk, the **EU AI Act**, the NIST AI Risk Management Framework and the FINOS AI Governance Framework — SD-14.4.
- The **EU Digital Operational Resilience Act (DORA, Regulation (EU) 2022/2554)** and the FCA / PRA operational-resilience rules — SD-14.6; **ISO 27001** and **ISO 22301** as the SD-14.5 / SD-14.6 general-enterprise baselines.
- The **ISDA** documentation architecture and the **ILPA** model legal documents — SD-14.9.
- BIAN's split of the corporate function across multiple control domains beneath a grouping tier — the reference-model precedent for treating risk, control and assurance as a Business Domain distinct from governance and from corporate services.

## Design notes

- **BD-14 is the risk-control-and-assurance stack.** It covers nine Service Domains: the second line (CRO, CCO, MLRO), the specialist control disciplines (model and AI governance, cyber, resilience), management assurance, internal audit, and the legal-and-contract function. Governance and accountability sit in BD-16; corporate services and resources sit in BD-17.
- **The specialist control disciplines are modelled at full depth.** Cyber, resilience and model/AI governance are not stubbed — their investment-management expression is regulator-shaped (the EU Digital Operational Resilience Act — DORA, Regulation (EU) 2022/2554 — SR 11-7, the EU AI Act, the operational-resilience rules, the protection of the IBOR and of material non-public information). Where an operation is genuinely general-enterprise, the Service Domain file names the external baseline (ISO 27001, ISO 22301) rather than claiming distinctive authority.
- **The first line is not a BD-14 Service Domain.** The controls operating inside the investing Business Domains are distributed across those domains; SD-14.7 designs the framework they conform to. BD-14 models the second line, the management-assurance layer, the specialist disciplines and the third line — not the first-line controls themselves.
- **Legal-agreement entities only.** BD-14 consumes entities and control evidence from across the model and produces risk, control and assurance artefacts. SD-14.9 owns DR-03 Master Agreement and DR-05 Clearing Relationship and is the source of PM-10 Fund Terms.
- **Panel-substitution rationale — asset-owner collapse.** The single "Asset owner (pension / SWF / endowment)" row collapses DBP and SWF-E — BD-14's discriminating axis is **whether the institution is a licensed adviser running its own conduct-and-compliance stack**, not the asset-owner sub-archetype. A DB pension, a SWF and an endowment that manage only their own money all sit at the same partial activation: the licensed-adviser thread of SD-14.2 is light or dormant, the conduct thread still applies, financial crime is light, and the control-and-audit stack is full. The Insurer keeps its own row (the investment arm typically embedded in a group control function, heavy actuarial and capital model governance) — it is not included in the collapse, because the insurance-group context is the insurer's defining BD-14 shape.

## How BD-14 relates to the rest of the model

- **Consumes** outputs and control evidence from every Business Domain — the investment, risk, performance, valuation, compliance, treasury, operations and data outputs that the control, assurance and specialist-discipline Service Domains run over; the third-party risk picture from SD-17.8; the resilience and security dependencies of SD-13.12; E-01 Legal Entity (the firm's investors, counterparties and the counterparties to its agreements); E-19 Risk Measurement (any `risk_type` — the `model_id` hook behind SD-14.4 applies across every risk-type partition).
- **Owns** the firm's risk, control and assurance artefacts as process records — the enterprise risk register, the compliance programme, the financial-crime case record, the model and AI inventory, the security and resilience frameworks, the control framework, the internal-audit plan. SD-14.9 owns the firm's legal agreements as documents — DR-03 Master Agreement and DR-05 Clearing Relationship.
- **Feeds** the firm's governing bodies (BD-16, which operates them and reports through them), the regulators and the external auditor; and it sets the firm-wide control standards — the control framework, the model-governance regime, the cyber and resilience standards, the conduct rules — that every other Business Domain operates within.
