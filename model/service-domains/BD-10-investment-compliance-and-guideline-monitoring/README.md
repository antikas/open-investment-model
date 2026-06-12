# BD-10 — Investment Compliance & Guideline Monitoring

**Office:** Middle.

**Maturity:** Provisional · 9 Service Domains for the coded-rule library, pre- and post-trade monitoring, regulatory rules, sustainability compliance, and breach lifecycle

The investment-compliance capability — the independent function that checks the firm's investing against the rules it must obey. Every pool of capital the firm runs is bound by rules: a client's mandate, a fund's prospectus, a limited-partnership agreement, securities regulation, the firm's own investment policy. BD-10 is the **second-line** capability that codes those rules, checks the portfolio against them before and after trading, watches the firm's trading for market abuse, and manages the response when a rule is breached. Where BD-07 Investment Risk measures the economic risk the firm *chooses* to bear, BD-10 enforces the rules the firm *must* obey.

Each Service Domain below is its own file.

## Service Domains

| ID | Service Domain | Applies | What it does |
|---|---|---|---|
| SD-10.1 | [Investment Guideline Monitoring](SD-10.1-investment-guideline-monitoring.md) | BOTH | Checks every portfolio against the rules it must obey — pre-trade, intraday, post-trade, and at deal approval for closed-end vehicles. |
| SD-10.2 | [Investment Restriction Coding & Rule Library](SD-10.2-investment-restriction-coding-and-rule-library.md) | BOTH | Interprets the guideline sources and codes them into the machine-checkable rule library. |
| SD-10.3 | [Regulatory Investment Compliance](SD-10.3-regulatory-investment-compliance.md) | BOTH | Interprets the regulation and keeps that interpretation current — which regime binds a portfolio and what it requires (UCITS 5/10/40, 1940 Act, AIFMD, position limits, short-selling); SD-10.2 codes the interpreted requirement, SD-10.1 runs it. |
| SD-10.4 | [Restricted & Watch List Management](SD-10.4-restricted-and-watch-list-management.md) | BOTH | Maintains the restricted, watch and grey lists and enforces the information barriers behind them. |
| SD-10.5 | [Side-Letter & Fund-Term Compliance](SD-10.5-side-letter-and-fund-term-compliance.md) | PRIV | Tracks and enforces the negotiated side-letter and fund-term obligations a fund owes its investors. |
| SD-10.6 | [Sanctions & Prohibited-Issuer Screening](SD-10.6-sanctions-and-prohibited-issuer-screening.md) | BOTH | Screens issuers, counterparties and investees against sanctions and prohibited-party lists. |
| SD-10.7 | [Trade Surveillance & Market-Abuse Monitoring](SD-10.7-trade-surveillance-and-market-abuse-monitoring.md) | BOTH | Watches the firm's own trading for insider dealing, manipulation and other market abuse. |
| SD-10.8 | [Compliance Breach Management & Remediation](SD-10.8-compliance-breach-management-and-remediation.md) | BOTH | Manages a breach from raised alert to closed correction, and assesses the disclosure obligation. |
| SD-10.9 | [ESG & Sustainability Compliance](SD-10.9-esg-and-sustainability-compliance.md) | BOTH | Runs the product-level sustainability-compliance discipline — SFDR / Taxonomy mapping, ESG-mandate enforcement, disclosure-pack gating, stewardship-code compliance. |

## Investment compliance, not firm compliance

BD-10's question is **does the *portfolio* obey the rules that bind it** — not *does the firm obey the rules that bind it as a licensed business, and do its employees behave*. Two capabilities sit outside BD-10:

- **Personal Account Dealing & Conflicts** monitors *employees*, not the portfolio — it is conduct compliance, owned by SD-14.2.
- **Investor-KYC and AML-transaction-monitoring** monitors the firm's *customers and cash flows* — it is financial-crime compliance, owned by SD-14.3.

What stays is the portfolio-side: the rules a portfolio must obey, and the screening of what the portfolio may hold.

## The rule lifecycle

BD-10's nine Service Domains decompose along the compliance rule lifecycle. **SD-10.3** interprets the regulation — it owns the regulatory rule set's currency and interpretation (which regime applies and what it requires), and hands the interpreted requirement to **SD-10.2**, which codes it into the library where the rules live; **SD-10.1** runs the library against the portfolio — pre-trade, intraday, post-trade; **SD-10.4** and **SD-10.6** enforce the list-based prohibitions; **SD-10.7** watches the firm's trading for abuse; **SD-10.8** handles the breach when a rule is crossed; **SD-10.5** tracks the contractual obligations a private-markets fund owes its investors; and **SD-10.9** carries the sustainability rule set as a distinct compliance capability — mapping the portfolio against the SFDR / Taxonomy classifications, enforcing ESG-mandate constraints, gating the sustainability disclosure packs, and routing any sustainability breach into SD-10.8. Detection (SD-10.1, SD-10.7) and response (SD-10.8) are separate Service Domains — the same separation BD-07 draws between measuring a risk and governing the limit.

## No default mandate origin, no default cadence

- **Mandate origin.** The rules a portfolio obeys come from any source — a client investment-management agreement, a fund prospectus, a limited-partnership agreement, or the institution's own investment policy. An asset owner has no external client mandate at all; its guidelines are its own IPS. SD-10.1 and SD-10.2 are written neutral on origin.
- **Checking cadence.** Pre-trade compliance is a continuously-traded-portfolio concept. A closed-end private-markets fund checks its LPA restrictions and eligible-investment criteria at *deal approval*, and monitors concentration drift periodically as it draws down. SD-10.1 carries both cadences; neither is the default.

## Archetype activation

The investment-compliance function is present at every archetype; what is heavy, light or dormant varies.

| Archetype | BD-10 | What differs |
|---|---|---|
| Third-party asset manager | Full | The fullest expression — inbound client IMAs drive heavy SD-10.2 onboarding; pooled funds bring the UCITS / 1940-Act regulatory set; a continuous pre-trade / intraday / post-trade engine. |
| Hedge fund | Full | Fewer client-mandate rules, more internal-risk and regulatory rules; SD-10.7 trade surveillance heavy (manipulation and MNPI exposure); SD-10.5 dormant. |
| Private-markets manager (PE / private credit / real assets) | Partial | No continuous pre-trade engine — guideline compliance is checked at investment committee against the LPA; SD-10.5 side-letter compliance is central; SD-10.7 largely dormant. |
| Asset owner (pension / SWF / endowment) | Full | No external client mandate — the rules are its own self-authored investment policy; compliance often monitors external managers' adherence as much as direct holdings. |
| Insurer | Full | The regulatory rule set carries the admitted-asset and Solvency II / NAIC investment limits; mandate monitoring is lighter. |
| Index / passive manager | Partial | A thin function — the dominant rule is index-replication tolerance; the UCITS 20/35 index-tracking exception. |
| Wealth manager / private bank | Full | SD-10.1 runs at per-client-account scale; per-client suitability is an additional dimension that sits in BD-15 (SD-15.12 Client Advice & Suitability), not BD-10. |

The common core, true of every archetype: **a second-line capability that codes the rules a pool of capital is bound by, checks the portfolio against them, and manages the response when a rule is breached.** The rules' source and the checking cadence vary; the capability does not.

**Why the manager-archetype row is split into sub-archetypes.** The discriminator the sub-archetype rows divide on in BD-10 is the **source of the binding rule set** — self-authored, client-mandated, or regulatory — and how heavily each source weights. A third-party asset manager carries the fullest mix: inbound client IMAs drive heavy SD-10.2 onboarding, pooled funds bring the UCITS / 1940-Act regulatory set, and a continuous pre-trade / intraday / post-trade engine runs across all three. A private-markets manager has no continuous engine — the source mix is the LPA + side letters (SD-10.5 central), with deal-approval IC-stage checking rather than pre-trade. An index / passive manager is dominantly regulatory — the UCITS 20/35 index-tracking exception and the index-replication-tolerance rule. The rule-source discriminator is what the sub-typing makes visible; collapsing it would assert one rule mix across managers that the compliance-engine load and shape contradicts.

## Wider-source grounding

Grounded against external industry references:

- The **compliance-vendor capability maps** — BlackRock Aladdin Compliance, Charles River IMS / SimCorp, Bloomberg AIM, SS&C, Confluence — the completeness cross-check on the rule-coding / pre-trade / intraday / post-trade / breach / surveillance sub-capability cluster.
- The **securities and fund regulation** BD-10 monitors against — the **UCITS Directive** (Article 50 eligible assets, the Article 52 **5/10/40 diversification rule**), **AIFMD**, the **US Investment Company Act 1940**, **MiFID II**, the **EU Short Selling Regulation**, and exchange and statutory position-limit regimes.
- The **EU Market Abuse Regulation** — the source of the trade-surveillance obligation.
- The **OFAC / EU / UN / OFSI** sanctions regimes and the **FATF** financial-crime framework — the latter governing the AML capability that sits in BD-14, not BD-10.
- The **CFA Institute Asset Manager Code** — the requirement for an empowered, independent compliance function.
- **ILPA** guidance on side letters and most-favoured-nation elections.
- The **three-lines-of-defence** model — investment compliance as a second-line control.
- The institution-archetype panel and the public / private cadence divide.

## Non-overlap — where the boundaries run

- **BD-10 vs BD-07 Investment Risk.** SD-07.7 governs **risk-appetite-derived** limits — value-at-risk, tracking error, the economic risk the firm *chooses* to bear. BD-10 owns **mandate- and regulatory-derived** limits — the rules a portfolio *must* obey. The *source* of the limit decides the owner. A single position can breach both; SD-10.8 and SD-07.7 are parallel breach pipelines distinguished by limit source.
- **BD-10 vs BD-14 Enterprise Risk, Control & Assurance and BD-16 Enterprise Governance & Accountability.** BD-10 monitors the *portfolio* against investment regulation and *detects* breaches. BD-14 owns the firm's *control and conduct* obligations as a licensed entity — the regulator relationship, firm-wide regulatory-change horizon-scanning, and the conduct (SD-14.2 Corporate Compliance & Conduct) and financial-crime (SD-14.3 Financial Crime Prevention) compliance that govern *employees* and *customers*. BD-16 owns the firm's *accountability and disclosure* obligations — the regulatory returns themselves (SD-16.3 Regulatory Reporting & Filings). The hand-off: SD-10.8 assesses whether a breach triggers a disclosure obligation; SD-16.3 produces and files the return. Investment-rule-affecting regulatory change flows from SD-14.2's horizon-scan into SD-10.3 and the SD-10.2 rule library.
- **BD-10 vs BD-01.** SD-01.2 owns the *mandate* — the objectives and constraint set a portfolio carries. SD-10.2 owns the *coded rules* the mandate is translated into. SD-01.2 owns the prose; SD-10.2 owns the machine rule.
- **SD-10.2 Investment Restriction Coding & Rule Library vs SD-02.5 Security Selection & Recommendation (cross-Business-Domain).** SD-10.2 maintains the *coded investment restrictions* — what a mandate, fund prospectus or regulation *permits*. SD-02.5 maintains the *recommended / approved list* — what research conviction says the firm *wants* to hold. A name can be on the recommended list and still be barred by a mandate restriction; the two lists are different artefacts owned by different domains. SD-02.5 expresses conviction; SD-10.2 codes constraint.
- **BD-10 vs BD-03.** SD-03.7 oversees an *external manager's* adherence to the guidelines the institution set it. SD-10.1 is the institution's own compliance engine for the portfolios it directly runs.
- **Personal account dealing and AML are not BD-10.** Monitoring employees' personal trading is conduct compliance; investor KYC and AML transaction monitoring are financial-crime compliance. Both govern the *firm and its people*, not the portfolio — they sit in BD-14 (SD-14.2 and SD-14.3).

## Design notes

- **SD-10.1 and SD-10.2 are mandate-origin- and cadence-neutral.** One capability carries every mode — self-authored IPS, inbound client mandate, fund prospectus, LPA, regulatory rule set, and pre-trade / intraday / post-trade / deal-approval cadences. "Mandate" was dropped from SD-10.1's name to avoid a collision with SD-01.2 Investment Mandate & Policy Definition.
- **Suitability is BD-15's, not BD-10's.** The wealth-manager archetype's distinctive compliance activity — per-client suitability and appropriateness — is client-advice compliance owned by SD-15.12 Client Advice & Suitability, not portfolio-guideline monitoring.
- **No new entities.** BD-10 owns the coded rule library, the restricted lists and the breach record as process artefacts.
- **Panel-substitution rationale — asset-owner collapse.** The single "Asset owner (pension / SWF / endowment)" row collapses DBP and SWF-E — BD-10's discriminating axis is **the source of the rule** (self-authored IPS vs inbound client mandate vs regulatory rule set), not the asset-owner sub-archetype. A DB pension, a SWF and an endowment all run BD-10 on the same shape — checking the portfolio against their own self-authored investment policy, often extending the same checks to external managers' adherence. The Insurer keeps its own row (admitted-asset rules, Solvency II / NAIC investment limits) — it is not included in the collapse, because the regulatory rule set is the insurer's defining BD-10 activation.

## How BD-10 relates to the rest of the model

- **Consumes** the mandate and book-of-record entities — Portfolio / Mandate (E-03, the mandate facet from SD-01.2), Holding / Position (E-04, `book = ibor` — compliance runs against the live IBOR position), Transaction (E-05), Order (PB-03), Fund Terms (PM-10), Risk Limit (E-16, the `mandate`-typed limits) — and the legal-entity master (E-01) for issuer and counterparty screening.
- **Owns** the coded rule library, the restricted lists and the breach record as process artefacts; the candidate entity questions are flagged above. It produces compliance results, breach records and surveillance reports.
- **Feeds** the front office — SD-06.1 Order Management (the pre-trade gate), SD-05.2 Portfolio Management & Monitoring (the desk that corrects a breach); BD-16 SD-16.3 (the regulatory filing a breach triggers); BD-14 (the conduct and financial-crime functions that received Personal Account Dealing and AML — SD-14.2 and SD-14.3); and the compliance reporting in BD-13.
