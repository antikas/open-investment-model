# BD-06 — Trading & Execution

**Office:** Front.

**Maturity:** Provisional · 6 Service Domains for order management, execution, allocation, and TCA

The trading and execution capability — it takes the trades portfolio management decides (BD-05) and executes them in the market. BD-06 is the last of the six front-office Business Domains, and the end of the front-office process: where BD-01 to BD-05 decide *what* to hold and *why*, BD-06 decides *how, when and where* to execute, and hands a completed trade to the operations domains (BD-12) to settle.

Each Service Domain below is its own file.

## Service Domains

| ID | Service Domain | Applies | What it does |
|---|---|---|---|
| SD-06.1 | [Order Management](SD-06.1-order-management.md) | PUB | Receives, validates and routes the trade decision through the desk — the order-management capability. |
| SD-06.2 | [Trade Execution](SD-06.2-trade-execution.md) | PUB | Executes the order in the market, by the mode the market structure dictates. |
| SD-06.3 | [Execution Venue & Broker Management](SD-06.3-execution-venue-and-broker-management.md) | PUB | Manages the universe of counterparties and venues the desk can trade with. |
| SD-06.4 | [Best Execution & Transaction Cost Analysis](SD-06.4-best-execution-and-transaction-cost-analysis.md) | PUB | Proves execution was in clients' best interest and measures how well the desk traded. |
| SD-06.5 | [Trade Allocation](SD-06.5-trade-allocation.md) | PUB | Fairly allocates executed trades across the accounts and funds that participated. |
| SD-06.6 | [Derivatives & OTC Trade Management](SD-06.6-derivatives-and-otc-trade-management.md) | BOTH | Executes OTC derivatives and manages the clearing path. |

SD-06.1 to SD-06.5 are the trade chain — order, execution, the venues it runs through, the proof it was done well, and the allocation of the result. SD-06.6 is the specialised desk — OTC derivatives — whose instruments trade through a different path.

## Execution is mode-dependent — not equity by default

Execution is not one activity. It runs in modes set by the *market structure* of the instrument, not by asset-class label:

- **Order-driven / algorithmic** — equities and listed futures trade on a central limit order book; execution is algo selection (VWAP, participation, implementation-shortfall), smart order routing and dark-pool block work.
- **Quote-driven / request-for-quote** — fixed income and FX are dealer markets with no continuous screen price; execution is *select a counterparty, request a quote, compare, execute* — and, increasingly, portfolio (list) trading on electronic platforms.
- **High-touch / voice** — large, illiquid or sensitive orders are worked by a trader, by voice, managing information leakage and sourcing block liquidity.

SD-06.2 Trade Execution is one Service Domain whose operations branch across these three modes; SD-06.1's routing decision sends an order down whichever mode fits. The equity, order-driven model is one mode among three — encoding it as the default would mis-model the fixed-income, FX and OTC-derivative execution that is the larger part of the buy-side's flow.

## Archetype activation — BD-06 is switchable

BD-06 is the clearest case in the model of a Business Domain a whole archetype switches off.

| Archetype | BD-06 | What differs |
|---|---|---|
| Third-party asset manager | Full | A central, multi-asset dealing desk — specialist and low-touch teams across the six Service Domains |
| Hedge fund | Full | PM-traded or pod-traded; the systematic fund runs an automated execution layer |
| Index / passive manager | Full | Program / basket trading; scheduled index-reconstitution trades |
| Insurer | Full or delegated | A general-account, fixed-income-weighted desk; often delegated to a specialist manager |
| Wealth manager / private bank | Partial | Model-portfolio rebalancing across many accounts; increasingly outsourced |
| Asset owner (pension / SWF / endowment) | **Often dormant** | An owner that delegates to external managers runs no trading desk — execution lives in the managers' BD-06; large internalised owners run one |

BD-06 also illustrates the difference between *owning* a capability and *operating* it: **outsourced trading** — an outsourced dealing desk run by a custodian or a specialist provider — is BD-06 owned by the institution but operated externally. It is a sourcing choice over the same six Service Domains, not a separate capability, and not a new Service Domain.

**Why the manager-archetype row is split into sub-archetypes.** The discriminator the sub-archetype rows divide on in BD-06 is the **execution-channel mix** — the manager-archetype row is sub-typed because the channel a desk weights toward is what differentiates BD-06 production, not the manager archetype label. A third-party asset manager runs a high-touch + low-touch mix across cash and OTC; an index / passive manager runs program / basket trading and scheduled index-reconstitution trades on the algorithmic channel; a hedge fund runs PM-traded or pod-traded mixes and the systematic case adds an automated execution layer. The channel-mix discriminator is what the row sub-types make visible; collapsing it would assert one channel pattern across managers that the desk operating model does not have.

## Wider-source grounding

Grounded against external industry references:

- The **buy-side dealing-desk operating model** — the central multi-asset desk, the high-touch / low-touch split, the OMS / EMS distinction.
- The **CFA Institute** treatment of trade strategy and execution, and the implementation-shortfall framework.
- **Best execution and transaction cost analysis** — the MiFID II and FINRA best-execution obligations, pre- and post-trade TCA.
- **Multi-asset execution mechanics** — the order-driven, quote-driven and voice modes; the venue taxonomy (regulated markets, MTFs, OTFs, systematic internalisers, SEFs).
- The institution-archetype panel — including the archetypes that do not run a trading desk at all.

## Non-overlap — where the boundaries run

- **BD-06 vs BD-05 Portfolio Management (cross-Business-Domain).** BD-05 decides *what* to trade and *why* — the investment decision and the decision price; it hands BD-06 the order with its strategy, urgency and constraints. BD-06 decides *how, when and where*. The handoff is the order.
- **BD-06 vs BD-12 Investment Operations & Servicing (cross-Business-Domain).** BD-06 ends at the executed-and-allocated trade; BD-12 confirms, clears and settles it. The handoff is the execution and allocation record. For derivatives, SD-06.6 owns the clearing *routing* decision; BD-12 owns clearing *processing*.
- **SD-06.2 vs SD-06.6.** SD-06.2 executes across all market-structure modes, including listed-derivative execution on an exchange. SD-06.6 owns the *OTC-derivative-specific* execution and the clearing-and-give-up path that distinguishes a derivative trade from a cash-instrument trade.
- **There is no securities-financing desk in BD-06.** Securities lending and repo are two Service Domains, both outside BD-06: SD-11.8 Securities Finance & Funding owns the programme, the funding book and the financing trade; SD-12.13 Securities Lending Operations owns the operational loan book. The financing trade is treasury's act of running the funding book, not a front-office execution desk.
- **SD-06.4 vs SD-02.8 Research Procurement & Evaluation (cross-Business-Domain).** Both evaluate "brokers." SD-06.4 evaluates *execution* quality — how well a broker or venue filled a trade. SD-02.8 evaluates *research* providers and the research budget. Different evaluations of, sometimes, the same firm.
- **Private-market transactions are not BD-06.** A private-market transaction completes by funds-flow (SD-12.8 Capital Call & Distribution Processing) and legal closing (SD-04.6 Deal Execution & Legal Closing) — there is no order, venue or quote. BD-06 is the market-trading domain.

## Design notes

- **Mode-neutral framing.** SD-06.1 and SD-06.2 are framed so execution is parameterised by market-structure mode (order-driven, quote-driven, voice) — the asset-class balance reviewer's C5 / C7.
- **No new entities.** BD-06 consumes the instrument, order and transaction entities and produces executions and allocations recorded as Transactions (E-05).
- **Panel-substitution rationale — asset-owner collapse.** The single "Asset owner (pension / SWF / endowment)" row collapses DBP and SWF-E — BD-06's discriminating axis is **whether the institution runs its own trading desk**, not which non-insurer asset-owner archetype it is. A DB pension, a SWF and an endowment all sit dormant when they delegate to external managers and all activate the full BD-06 capability when they internalise — the cut is between delegated and insourced execution, not between the asset-owner sub-archetypes. The Insurer keeps its own row (fixed-income-weighted general-account desk, often delegated) — it is not included in the collapse.

## How BD-06 relates to the rest of the model

- **Consumes** the order and instrument entities — Instrument / Asset (E-02), the public-markets specialisations (Listed Equity PB-01, Debt Instrument PB-02), the trade-lifecycle entities (Order, Execution, Allocation in the public-markets pack), Price & Market Data (E-08), Legal Entity (E-01, brokers and counterparties as roles) — and the trade lists produced by BD-05.
- **Owns** no master entity. The executed trade is recorded as a Transaction (E-05); the trade-lifecycle entities are owned by the operations domains. The order, the execution record and the TCA output are BD-06's working artefacts.
- **Feeds** BD-12 Investment Operations & Servicing (which confirms, clears and settles the trades), BD-10 Investment Compliance (which monitored them pre-trade through SD-06.1 and reviews them post-trade), BD-11 Treasury, Cash & Collateral (the margin and collateral the trades consume), and BD-09 Performance & Analytics (best-execution and cost data).
