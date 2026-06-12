# BD-02 — Securities Research & Selection

**Office:** Front.

**Maturity:** Provisional · 8 Service Domains for fundamental, quantitative, and credit research feeding security selection

The public-markets active-management capability — generating, researching and selecting the individual securities a portfolio holds. BD-02 is the **public-markets investing model**, peer to BD-03 (the fund-investing model) and BD-04 (the direct & co-investment model): three front-office Business Domains, one per investing mode — peer in role, not in decomposition depth (BD-04 is deeper, on a genuine capability difference its design notes record). Where BD-01 sets the allocation, BD-02 fills the public-markets sleeve of it with specific securities; it ends at a rated recommendation, which BD-05 Portfolio Management constructs into a position.

Each Service Domain below is its own file.

## Service Domains

| ID | Service Domain | Applies | What it does |
|---|---|---|---|
| SD-02.1 | [Investment Idea Generation](SD-02.1-investment-idea-generation.md) | PUB | Originates public-markets investment ideas and screens the investable universe. |
| SD-02.2 | [Fundamental Equity Research](SD-02.2-fundamental-equity-research.md) | PUB | Analyses listed-equity issuers on fundamentals to form a research view and an intrinsic-value estimate. |
| SD-02.3 | [Credit Research & Analysis](SD-02.3-credit-research-and-analysis.md) | PUB | Analyses debt issuers and instruments for creditworthiness, relative value and default / recovery risk. |
| SD-02.4 | [Quantitative & Systematic Research](SD-02.4-quantitative-and-systematic-research.md) | PUB | Researches factors and signals and builds the models behind systematic strategies. |
| SD-02.5 | [Security Selection & Recommendation](SD-02.5-security-selection-and-recommendation.md) | PUB | Converts research into the buy / sell / hold decision and the recommended list. |
| SD-02.6 | [Investment Thesis Management](SD-02.6-investment-thesis-management.md) | PUB | Maintains and revalidates the live research thesis on each candidate and held security. |
| SD-02.7 | [Research Management & Coverage](SD-02.7-research-management-and-coverage.md) | PUB | Runs the research function's operating model — coverage, workflow and the research record. |
| SD-02.8 | [Research Procurement & Evaluation](SD-02.8-research-procurement-and-evaluation.md) | PUB | Sources, budgets, pays for and evaluates the external research the firm consumes. |

SD-02.1 to SD-02.6 are the research-and-selection chain. SD-02.7 is the operating model the chain runs inside; SD-02.8 governs the external research the chain consumes.

## Archetype activation

Securities research and selection is **conditionally activated** — the model does not treat "research a company, pick a stock" as the universal shape, because the *unit of a selection decision* differs by institution type and some archetypes do not activate BD-02 at all.

| Archetype | BD-02 | What differs |
|---|---|---|
| Fundamental active equity manager | Full | The canonical case — the selection unit is the security |
| Quantitative / systematic manager | Full, reshaped | SD-02.4 dominant; the selection unit is the *signal*, not the stock |
| Credit / fixed-income manager | Full | SD-02.3 dominant; the internal credit rating is its standing artefact |
| Long/short & multi-strategy hedge fund | Full | HF-strategy idea generation (global macro, event-driven situations, arbitrage relationships) in SD-02.1 + short-thesis and event/catalyst research operations inside SD-02.2 / SD-02.3 / SD-02.4 + the strategy-level live thesis in SD-02.6; in a multi-strategy platform the capability is instantiated per pod |
| Wealth manager / private bank | Partial | Curation — SD-02.5 lists and SD-02.8 procurement dominate; little primary research production |
| Index / passive manager | **Dormant** | Replaced by rules-based index replication; the index provider's eligibility methodology is a BD-02-adjacent external function |
| Asset owner (pension / SWF / endowment) | **Conditional** | Off by default — the owner delegates security selection and activates BD-03 instead; on if it insources public-markets active management |

The model is the union; an implementation activates the subset its operating model needs. The **selection unit is configurable** — a security, a signal, an issuer and then its specific issue, an event/catalyst situation, or membership of a recommended list — and the Service Domains are written so no single unit is hard-coded.

**Absent archetypes — landscape-rule activation.** BD-02 uses a manager-substyle cut (fundamental / quant / credit / long-short) rather than the seven-archetype spine; the spine's other archetypes — **DBP, SWF-E, INS and OCIO** — activate BD-02 as **"the third-party asset manager's subset"** via the [landscape OCIO / panel-substitution rule in `service-domains/INDEX.md`](../INDEX.md). DBP, SWF-E and INS activate BD-02 only where they insource public-markets active management (otherwise they delegate to BD-03); the OCIO activates it on whichever delegated books its asset-owner client has insourced public-markets selection to it.

## Wider-source grounding

Grounded against external industry references:

- The **CFA Institute** body of knowledge — the equity-valuation process (understand the business → forecast → select a model → value → recommend), the credit-analysis "Four Cs" (Capacity, Collateral, Covenants, Character), and Standard V (the "reasonable and adequate basis" for a recommendation).
- The **buy-side research function** — coverage models, the analyst-to-portfolio-manager workflow, recommended / approved / focus lists, research management systems.
- **MiFID II research unbundling** — the regulated separation of research from execution that makes research procurement (SD-02.8) a discrete capability.
- The **quantitative research pipeline** — factor research, backtesting, out-of-sample validation, alpha-decay monitoring.
- The buy-side institution-archetype panel, per the institution-archetype balance reviewer.

## Non-overlap — where the boundaries run

- **BD-02 vs SD-01.3 Capital Market Assumptions & House View (cross-Business-Domain).** SD-01.3 is *top-down* macro and capital-market research — the firm-wide house view. BD-02 is *bottom-up*, security-level research on individual issuers and instruments. BD-02 *consumes* the house view as a forecasting input (SD-02.2's top-down forecasting approach, SD-02.1's thematic ideas); it never originates it.
- **BD-02 vs BD-03 Manager & Fund Investment (cross-Business-Domain).** BD-02 selects *securities* — the insourced active-management path. BD-03 selects *external managers and funds* — the delegate path. An asset owner that delegates public-markets selection activates BD-03 and leaves BD-02 dormant; one that insources activates BD-02. The two are the alternative answers to "who picks the securities."
- **BD-02 vs BD-04 Direct & Co-Investment (cross-Business-Domain).** BD-02 selects publicly-traded *securities*; BD-04 acquires private companies and assets *directly*. The two are non-overlapping investing modes — BD-02 is the public-markets active-management chain (research and selection of listed equities and traded debt); BD-04 is the non-delegated private-markets chain (origination, underwriting and stewardship of company, real-asset and direct-loan acquisitions). SD-02.3 Credit Research & Analysis and SD-04.3 Investment Due Diligence are the named boundary: SD-02.3 researches the issuers of *public* debt; SD-04.3 underwrites a *direct private loan the institution itself originates*. Mirrors the BD-04 README's BD-04-vs-BD-02 statement.
- **BD-02 vs BD-05 Portfolio Management (cross-Business-Domain).** BD-02 ends at the *rated recommendation* — a conviction-rated buy / sell / hold with a price target. BD-05 *constructs* the portfolio from those recommendations — position sizing, weighting, diversification. The analyst recommends; the portfolio manager sizes.
- **SD-02.6 Investment Thesis Management vs SD-05.2 Portfolio Management & Monitoring (cross-Business-Domain).** SD-02.6 owns the live *research thesis* on a security — its pillars, its revalidation, its sell triggers. SD-05.2 monitors the *held position* against the portfolio mandate. SD-02.6 watches the thesis; SD-05.2 watches the position.
- **SD-02.5 Security Selection vs SD-10.2 Investment Restriction Coding & Rule Library (cross-Business-Domain).** SD-02.5 maintains the *recommended / approved list* as an expression of research conviction — what the firm *wants* to hold. SD-10.2 maintains the *coded investment restrictions* — what a mandate *permits*. A name can be on the recommended list and still be barred by a mandate restriction; the two lists are different artefacts owned by different domains.
- **SD-02.4 Quantitative & Systematic Research vs SD-09.5 Investment Analytics & Insight (cross-Business-Domain).** SD-02.4 *builds* the factor and alpha models — research that produces a selection signal. SD-09.5 produces diagnostic and forward-looking *portfolio* analytics. SD-02.4 researches what to buy; SD-09.5 analyses what is held.
- **SD-02.8 Research Procurement & Evaluation vs SD-02.7 Research Management & Coverage.** SD-02.8 owns the *commercial* relationship with external research providers — sourcing, budgeting, the broker vote, payment. SD-02.7 owns the *operating model* of the firm's own research — including the research-management-system control of which external content the firm is technically entitled to receive. SD-02.8 decides which providers are paid; SD-02.7 controls what content flows in.
- **SD-02.8 vs BD-06 Trading & Execution (cross-Business-Domain).** SD-02.8 owns research-budget setting and provider evaluation, and the *allocation* of research payments and commissions. The *settlement* of trading commissions on the execution desk is BD-06. SD-02.8 decides the allocation; BD-06 executes the trades it is settled through.

## Design notes

- **SD-02.8 Research Procurement & Evaluation is a discrete capability.** Sourcing, budgeting, paying for and evaluating *external* research is a discrete, MiFID-II-regulated, separately-tooled capability with no home among the other seven research and selection Service Domains.
- **ESG research is not a Service Domain — it is a cross-cutting operation.** Material-ESG-factor integration is an operation inside SD-02.2 (equity) and SD-02.3 (credit) — it adjusts forecasts and discount-rate assumptions — and an idea source in SD-02.1. The ESG *data* capability belongs to the data Business Domain (BD-13). An eighth research SD for ESG would mis-model an integrated activity as a separate one.
- **Archetype sub-capabilities are operations, not Service Domains.** Short-thesis research, event/catalyst research, the internal credit rating and quant model validation are archetype-specific operations carried inside SD-02.2, SD-02.3 and SD-02.4 — switched on by the institution type, not given their own domains. HF-strategy idea generation — global macro regime calls, event-driven situations and arbitrage relationships — is the long-short row's analogue at the *strategy level*, carried as an explicit operation inside SD-02.1 (and the strategy-level live thesis maintained alongside the security-level theses in SD-02.6); no separate Service Domain.
- **BD-02 owns few entities.** Like BD-01 and BD-09, it is a research and decision domain: it consumes the instrument, issuer and market-data entities and produces research artefacts — research notes, theses, internal ratings, rated recommendations, the recommended list.
- **Panel-substitution rationale — manager-substyle substitution and asset-owner collapse.** BD-02's archetype-activation cut is a **manager-substyle** cut (fundamental / quant / credit / long-short): BD-02 production differs by *how* a manager researches and selects securities — the analyst-and-PM workflow, the signal pipeline, the credit-analysis discipline, the short-and-event approach — not by which institution archetype owns the desk. A fundamental equity manager and a quant manager run materially different SD-02.1–02.4 capabilities; a fundamental equity manager and a fundamental-equity-running pension fund run the same ones. Within the substyle cut, the single "Asset owner (pension / SWF / endowment)" row collapses DBP and SWF-E because BD-02's discriminating axis (substyle) does not run between them; INS keeps its own implicit thread via the absent-archetype landscape rule above.

## How BD-02 relates to the rest of the model

- **Consumes** the issuer and instrument entities — Legal Entity (E-01, issuers as a role), Instrument / Asset (E-02), and the public-markets specialisations Listed Equity (PB-01) and Debt Instrument (PB-02) — the market-data and reference entities — Price & Market Data (E-08), Asset Class (E-09), Benchmark / Index (E-10) — and the house view produced by SD-01.3.
- **Owns** no master entity. The research note, investment thesis, internal credit rating and security recommendation are analytical artefacts.
- **Feeds** BD-05 Portfolio Management (which constructs the portfolio from BD-02's rated recommendations), BD-06 Trading & Execution (which executes the resulting orders, and through which SD-02.8's commission allocations settle), and BD-10 Investment Compliance (which checks selected securities against mandate restrictions). It consumes the allocation set by BD-01 — BD-02 selects securities within the public-markets sleeve BD-01 sizes.
