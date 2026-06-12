# BD-03 — Manager & Fund Investment

**Office:** Front.

**Maturity:** Provisional · 9 Service Domains for the GP / fund-investing route — sourcing, diligence, commitment, monitoring, secondaries

The fund-investing / external-manager investing model — how an institution invests by allocating to external managers and funds rather than selecting securities or assets itself. BD-03 is peer to BD-02 (the public-markets security-selection model) and BD-04 (the direct & co-investment model): three front-office Business Domains, one per investing mode — peer in role, not in decomposition depth (BD-04 is deeper, on a genuine capability difference its design notes record). Where BD-01 sets the allocation, BD-03 fills the sleeves an institution chooses to run through external managers — and for some archetypes (the endowment, the fund-of-funds) it is the primary way capital is put to work.

Each Service Domain below is its own file.

## Service Domains

| ID | Service Domain | Applies | What it does |
|---|---|---|---|
| SD-03.1 | [Manager Sourcing & Pipeline](SD-03.1-manager-sourcing-and-pipeline.md) | BOTH | Identifies and maintains a pipeline of external managers and funds for potential allocation. |
| SD-03.2 | [Manager Research & Selection](SD-03.2-manager-research-and-selection.md) | BOTH | Evaluates external managers on strategy, team and track record, and recommends a selection. |
| SD-03.3 | [Fund Operational Due Diligence (ODD)](SD-03.3-fund-operational-due-diligence.md) | BOTH | Assesses a manager's operations, controls and service providers, independently of investment merit. |
| SD-03.4 | [Fund Investment Due Diligence](SD-03.4-fund-investment-due-diligence.md) | PRIV | Assesses the investment thesis, terms and return drivers of a fund commitment. |
| SD-03.5 | [Fund Commitment & Subscription](SD-03.5-fund-commitment-and-subscription.md) | PRIV | Executes the legal commitment to a closed-end fund and manages the subscription process. |
| SD-03.6 | [GP & Manager Monitoring](SD-03.6-gp-and-manager-monitoring.md) | BOTH | Monitors the performance, portfolio and organisational health of appointed managers. |
| SD-03.7 | [Manager Mandate Administration](SD-03.7-manager-mandate-administration.md) | PUB | Appoints and administers segregated / separately-managed-account mandates given to external managers. |
| SD-03.8 | [Re-Up & Manager Relationship Management](SD-03.8-re-up-and-manager-relationship-management.md) | BOTH | Manages the retention, re-up and relationship decisions across the life of a manager appointment. |
| SD-03.9 | [Fund-Commitment Approval & Authorisation](SD-03.9-fund-commitment-approval-and-authorisation.md) | PRIV | The Investment Committee gate over the fund-commitment chain — recommendation memorandum, staged committee, authorisation, authority-and-mandate verification. Parallel to SD-04.5. |

**The shape of BD-03 is a shared front end, an IC gate, and two divergent paths.** SD-03.1 to SD-03.4 are common — every external-manager investment is sourced, researched, and run through two due-diligence streams (operational and investment). **SD-03.9 Fund-Commitment Approval & Authorisation** is the Investment Committee gate that authorises a fund commitment before close, the parallel of SD-04.5 for the direct route. The capability then forks: **SD-03.5** is the closed-end *fund-commitment* path (a fund subscription — an LP interest with a capital-call lifecycle); **SD-03.7** is the open-ended *segregated-mandate* path (an investment-management agreement over assets held in the institution's own name). SD-03.6 and SD-03.8 are the shared ongoing oversight. A commitment is *either* a fund subscription *or* a mandate appointment — the two are parallel, not sequential.

**Asset-class coverage in BD-03.** BD-03 serves *every* asset class through the SMA or fund route: SD-03.7's segregated-mandate path covers public equity, fixed income, **cash and money-market mandates** (recognised institutional products), and credit; SD-03.5's fund-commitment path covers private equity, private credit, real estate, infrastructure, **natural-resources funds** (timberland, farmland, natural-resource and commodity-fund vehicles operated by TIMOs and farmland operators), and hedge funds (the closed-end fund-of-hedge-funds case). Both paths consume the shared SD-03.1–03.4 sourcing and diligence chain.

**Archetype activation: HF as allocator.** The seven-archetype panel in BD-03 covers the standard cases. Hedge funds *as allocators* — running external sleeves, pods or sub-adviser appointments — are uncommon but real (large multi-strategy platforms seed external pods; some single-manager HFs sub-advise specialist strategies). Where present, the HF-as-allocator activates SD-03.5 (the closed-end fund / sub-adviser fund route) or SD-03.7 (a segregated sub-advisory mandate), per the panel-substitution discipline in [`service-domains/INDEX.md`](../INDEX.md).

## Archetype activation

BD-03 is activated by **seven of the eight** buy-side institution archetypes — only the pure direct-only investor sits it out. The model is the union; an implementation activates its subset.

| Archetype | BD-03 | What differs |
|---|---|---|
| Corporate / public pension fund | Full | Both paths — public segregated mandates and private fund commitments; often consultant-mediated |
| Endowment & foundation | Full | The endowment model — manager selection is the primary route to return |
| Fund-of-funds / multi-manager | Full | Inverted — manager selection *is the product* sold to end investors |
| OCIO / fiduciary manager | Full | Inverted — manager selection delivered as a delegated discretionary service, per SD-01.2's `inbound-delegated` operation and the landscape OCIO rule in [`service-domains/INDEX.md`](../INDEX.md) |
| Wealth manager / private bank | Full | Shaped as the recommended- / approved-fund list, plus a client-suitability layer |
| Sovereign wealth fund / large asset owner | Partial | Asset-class-dependent — external where specialist or local expertise beats internal management |
| Insurer | Partial | Concentrated on specialist asset classes and smaller balance sheets |
| Hedge fund / multi-strategy platform | Partial | Uncommon but real — HF-as-allocator activates SD-03.5 (closed-end fund / sub-adviser fund route) or SD-03.7 (segregated sub-advisory mandate) when the platform seeds external pods or sub-advises specialist strategies; the rest of the BD-03 chain (SD-03.1–03.4, 03.6, 03.8, 03.9) supports those activations |
| Direct-only / pure-internal investor | **Dormant** | Replaced by direct security selection (BD-02) and direct & co-investment (BD-04) |

For the fund-of-funds and the OCIO the capability is *inverted*: BD-03 is not a support function but the firm's saleable output. The model carries this as an operating-model property — the Service Domains are the same; the consumer of their output differs.

## Wider-source grounding

Grounded against external industry references:

- The **CFA Institute** *Investment Manager Selection* body of knowledge — the universe → quantitative → qualitative process, the investment-DD / operational-DD split, and Type I / Type II selection errors.
- **ILPA** — the **Due Diligence Questionnaire 2.0** (2021) and **Principles 3.0** (2019, fostering transparency, governance and alignment of interests in LP–GP partnerships); the **AIMA DDQ** for hedge funds.
- **Operational due diligence** as a distinct, separately-staffed discipline, and its post-Madoff history.
- Fund-commitment mechanics — the LPA, side letters, the most-favoured-nation election, fund closings.
- The **segregated-mandate / SMA** path — the investment-management agreement, guidelines, transition management.
- The investment-consultant / manager-research industry, and the institution-archetype panel.

## Non-overlap — where the boundaries run

- **BD-03 vs BD-02 Securities Research & Selection (cross-Business-Domain).** BD-03 invests *through* an external manager's vehicle; BD-02 selects *securities* directly. They are the two answers to "who picks the securities" — an institution that delegates activates BD-03; one that insources activates BD-02.
- **BD-03 vs BD-04 Direct & Co-Investment (cross-Business-Domain).** BD-03 invests through a manager's vehicle; BD-04 invests *in an asset* directly. **Co-investment is the deliberate boundary case:** the negotiation of co-investment *rights* is an operation of SD-03.5 (a side-letter term obtained when committing to the fund); the *underwriting and execution* of a co-investment in a single asset is BD-04. The fund relationship originates the deal flow; BD-04 does the deal.
- **BD-03 vs SD-01.10 Commitment Pacing (cross-Business-Domain).** SD-01.10 decides *how much* to commit to illiquid strategies per vintage — the pacing budget. BD-03 decides *which* manager and executes the commitment. SD-03.5 consumes the SD-01.10 pacing budget; it does not set it.
- **BD-03 vs BD-15 SD-15.10 Fund Capital Raising (cross-Business-Domain).** Same transaction, two sides. BD-03 is the **LP / allocator buying** a fund — sourcing the manager, running due diligence, committing. SD-15.10 is the **GP / manager selling** one — the fundraise, the data room, the close. One firm's BD-15 fundraise is another firm's BD-03 commitment.
- **SD-03.3 Operational DD vs SD-03.4 Investment DD.** SD-03.3 assesses operational integrity — service providers, controls, valuation policy — *independently of investment merit*, and can veto an investment the SD-03.4 team favours. SD-03.4 assesses investment merit — thesis, terms, return drivers. Two due-diligence streams, deliberately separate and separately staffed.
- **SD-03.5 Fund Commitment vs SD-03.7 Manager Mandate Administration.** The two divergent paths. SD-03.5 is the closed-end fund subscription — an LP interest, a capital-call lifecycle, a fixed term. SD-03.7 is the open-ended segregated mandate — an investment-management agreement, immediate funding, terminable at will. Both consume the shared SD-03.1–03.4 front end.
- **SD-03.6 GP & Manager Monitoring vs SD-03.7 Manager Mandate Administration.** SD-03.6 monitors the *manager* — performance, organisation, key people — across both paths. SD-03.7's own monitoring is narrower and path-specific: the appointed manager's adherence to the *segregated-mandate guidelines*. SD-03.6 watches the manager; SD-03.7 watches the mandate.
- **SD-03.7 vs SD-10.1 Investment Guideline Monitoring (cross-Business-Domain).** SD-03.7 oversees an *external manager's* adherence to the guidelines the institution set it. SD-10.1 is the institution's own pre- and post-trade compliance engine for the portfolios it directly manages. Different portfolios, different party running them.
- **SD-03.6 vs SD-07.5 Look-Through Exposure Analysis (cross-Business-Domain).** SD-03.6 monitors a manager's holdings as manager oversight; SD-07.5 decomposes fund and pooled holdings into underlying exposures for firm-wide risk aggregation. SD-03.6 watches one manager; SD-07.5 aggregates across all.
- **SD-03.9 Fund-Commitment Approval & Authorisation vs SD-04.5 Investment Approval & Authorisation (cross-Business-Domain).** The two Investment Committee capabilities — structurally parallel, operationally distinct. **SD-03.9** is the IC gate over the fund-investing chain: reviews a GP, a fund strategy, fund terms, the two diligence streams (ODD + IDD); authorises a fund commitment. **SD-04.5** is the IC gate over the direct-investment chain: reviews a company or asset, an investment thesis, term sheets; authorises a deal. A real firm may operate one IC body across both routes or two separate bodies — the OpenIM model carries them as distinct *capabilities* so both implementations are served.
- **SD-03.9 vs SD-16.1 Corporate & Fund Governance (cross-Business-Domain).** SD-16.1 is the firm's governance machinery — committee terms of reference, board-level decision capture, the scaffolding within which committees operate. SD-03.9 (and SD-04.5) own the investment-substantive content of the IC's deliberation and decision. SD-16.1 sets up the committee; SD-03.9 runs its investment business.

## Design notes

- **Applicability tags.** SD-03.3 (ODD), SD-03.6 (monitoring) and SD-03.8 (re-up) are tagged `BOTH` because operational due diligence, manager monitoring and the retention decision apply to any external manager, public-markets or private. SD-03.5 stays `PRIV` (the closed-end fund subscription) and SD-03.7 stays `PUB` (the segregated mandate) — those two genuinely are the asset-class-specific pair, by design.
- **Manager structure is a portfolio-construction discipline.** Constructing the *portfolio of managers* — manager-level allocation sizing, cross-manager concentration and style-overlap analysis, manager capacity budgeting, vintage diversification across commitments — is **SD-05.10 Manager Structure** in BD-05 (the Waring et al. precedent), not a Service Domain here. BD-03 covers the *individual* manager and feeds candidate managers to SD-05.10; the roster is constructed in BD-05.
- **The fund-of-funds inversion is an operating-model property, not a different capability.** A fund-of-funds runs the same SD-03.1 to SD-03.8 a pension fund's manager-research desk runs; the difference is that its output is sold as a product rather than consumed internally. The model does not duplicate the Service Domains for it.
- **BD-03 owns few entities.** It is a selection and oversight domain: it consumes the private-markets fund entities and the party master, and produces analytical artefacts — diligence reports, manager ratings, scorecards. SD-03.5 owns LP Commitment (PM-06).
- **Panel-substitution rationale — sub-archetype expansion.** BD-03 expands the default seven-archetype panel along two axes: a separate **"Fund-of-funds / multi-manager"** row, because manager-of-managers inverts the BD-03 capability into the saleable product; and a separate **"Endowment & foundation"** row, because the endowment model — where manager selection is the primary route to return — is BD-03's most distinctive activation and is materially different from the DB-pension and insurer cases. A single asset-owner row would erase the endowment-model differentiation, so the default asset-owner collapse is not used here; the "Sovereign wealth fund / large asset owner" and "Insurer" rows stand alone alongside the endowment row.

## How BD-03 relates to the rest of the model

- **Consumes** the private-markets fund entities — Fund & Vehicle (PM-01), Fund Terms (PM-10) — the party master Legal Entity (E-01), with GP, manager, administrator and custodian as roles of it — Portfolio / Mandate (E-03) — and the SD-01.10 commitment-pacing budget.
- **Owns** LP Commitment (PM-06), through SD-03.5 — the institution's committed and undrawn capital in a fund. The diligence reports, manager ratings and scorecards are analytical artefacts.
- **Feeds** BD-12 Investment Operations & Servicing (which processes the capital calls and distributions on the commitments BD-03 makes — SD-12.8), BD-09 Performance & Analytics (which measures the manager and fund returns), BD-07 Investment Risk (which aggregates look-through exposure across the manager book), and BD-01 SD-01.10 (whose pacing it consumes and informs). Co-investment deal flow originates here and is executed in BD-04.
