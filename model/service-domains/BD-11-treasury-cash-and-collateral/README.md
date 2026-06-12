# BD-11 — Treasury, Cash & Collateral

**Office:** Middle.

**Maturity:** Provisional · 8 Service Domains for cash management, FX, margin and collateral operations, bank-account administration

The treasury capability — the function that manages the cash, liquidity, collateral and funding of the funds and portfolios under management. Every investing institution holds cash, owes and is owed collateral, must meet obligations as they fall due, and must fund what it does. BD-11 is the capability that runs that: positioning cash, forecasting and funding liquidity, executing treasury FX, running the margin-and-collateral cycle and optimising the collateral inventory, financing the firm, and administering the bank accounts.

**Scope line.** BD-11 is the treasury of the **funds and portfolios under management**, run in a fiduciary capacity. The management company's *own* corporate treasury — the firm's operating cash, working capital and corporate liquidity — is BD-17's (SD-17.3 Corporate Treasury). BD-11 manages the capital the firm invests; it does not run the firm's own books.

Each Service Domain below is its own file.

## Service Domains

| ID | Service Domain | Applies | What it does |
|---|---|---|---|
| SD-11.1 | [Cash Management](SD-11.1-cash-management.md) | BOTH | Positions the cash of every fund and portfolio across accounts and currencies, and puts idle cash to work. |
| SD-11.2 | [Liquidity Management](SD-11.2-liquidity-management.md) | BOTH | Forecasts the liquidity the funds will need and ensures the funding gap is closed. |
| SD-11.3 | [FX Execution & Share-Class Hedging](SD-11.3-fx-execution-and-share-class-hedging.md) | BOTH | Executes treasury FX and runs the operational share-class-hedging programme. |
| SD-11.4 | [Margin & Collateral Operations](SD-11.4-margin-and-collateral-operations.md) | BOTH | Runs the daily margin-and-collateral cycle — calculate, call, settle, substitute, dispute. |
| SD-11.5 | [Collateral Optimisation & Inventory Management](SD-11.5-collateral-optimisation-and-inventory-management.md) | BOTH | Manages the firm-wide collateral inventory and the cheapest-to-deliver allocation. |
| SD-11.6 | [Fund Finance & Capital-Call Liquidity](SD-11.6-fund-finance-and-capital-call-liquidity.md) | PRIV | Manages subscription lines, NAV facilities and the liquidity to meet capital calls. |
| SD-11.7 | [Bank Account & Mandate Administration](SD-11.7-bank-account-and-mandate-administration.md) | BOTH | Administers the bank accounts, signatory mandates and bank relationships. |
| SD-11.8 | [Securities Finance & Funding](SD-11.8-securities-finance-and-funding.md) | BOTH | Runs the firm's funding book and the securities-lending programme. |

## Buy-side treasury, not bank treasury

BD-11 is treasury on the **buy-side** — it has no deposit-funding base, no banking-book balance sheet, no bank-style regulatory liquidity ratio. Buy-side treasury is the function that positions and forecasts the cash of the funds and portfolios, sources funding and liquidity, manages the collateral and margin against the firm's derivatives and financing, and administers the accounts and bank relationships. It is increasingly an alpha-aware, front-office-adjacent function — cash is an asset with a yield, collateral is a fundable resource with a cost — not the back-office plumbing it once was.

## Margin is the obligation, collateral is the asset

The ISDA collateral framework, the vendors and the triparty agents treat margin and collateral as **one discipline**: margin is the calculated *obligation*, collateral is the *asset* that satisfies it, and the margin call and the collateral movement are one workflow. The seam is **workflow stage**: SD-11.4 Margin & Collateral Operations runs the daily, per-relationship cycle — calculate, call, settle, substitute, dispute; SD-11.5 Collateral Optimisation & Inventory Management takes the firm-wide view — which asset to post, where, at the lowest funding cost. One discipline, two stages: the operational cycle and the strategic inventory.

## Two financing capabilities

BD-11 owns securities finance and funding, across two distinct capabilities. **SD-11.8 Securities Finance & Funding** owns the principal-side securities-finance capability — the firm's funding book (repo, securities lending and credit lines as a funding tool), the negotiation and execution of the firm's own financing trades, the securities-lending programme that lends the funds' assets for return, the lending-agent oversight and the cash-collateral reinvestment. **SD-11.6 Fund Finance & Capital-Call Liquidity** runs the private-fund financing — subscription lines, NAV facilities, hybrid facilities — and the liquidity to meet capital calls. There is no front-office securities-financing desk: the financing trade is treasury's act of running the funding book.

**Securities lending is two Service Domains.** SD-11.8 owns the programme and the financing book — whether to lend, on what terms, the operating model, lending-agent oversight, the funding book, and the reinvestment of cash collateral within the reinvestment-risk policy. SD-12.13 Securities Lending Operations owns the operational loan book — loan open, recall and return processing, per-loan collateral management, lending-revenue accounting, and corporate-action handling on loaned securities. SD-11.8 decides and funds; SD-12.13 operates the book. Cash-collateral reinvestment and lending-agent oversight sit in SD-11.8 only; the operational loan book sits in SD-12.13 only.

## Archetype activation

Treasury is present at every archetype; what is heavy, light or dormant varies by what the firm trades and how it is structured.

| Archetype | BD-11 | What differs |
|---|---|---|
| Third-party asset manager | Full | Cash and liquidity across many funds and mandates; share-class hedging for cross-border ranges; collateral and margin for any derivatives used; often a securities-lending programme. The most balanced profile. |
| Hedge fund | Full | The heaviest, most front-office-adjacent treasury — prime-brokerage financing, heavy margin and collateral, cross-product netting, a dedicated financing desk; SD-11.8 and SD-11.5 matter most. |
| Private-markets manager (PE / private credit / real assets) | Partial | Episodic, event-driven treasury — capital-call funding, distribution cash, subscription lines and NAV facilities (SD-11.6); little day-to-day margin or sweep activity. |
| Asset owner (pension / SWF / endowment) | Full | Two-sided liquidity — funding benefit payments and spending-policy outflows, and meeting its own capital calls to GPs; often a large securities-lending programme. |
| Insurer | Full | ALM-driven — the liquidity buffer sized to liability cash flows; margin and collateral on the ALM derivatives hedge book (uncleared, UMR-scoped). |
| Index / passive manager | Partial | Cash-drag minimisation and cash equitisation; the securities-lending programme is often a material revenue line; little bespoke collateral. |
| Wealth manager / private bank | Partial | The lightest on the fund side — client-cash sweeps and settlement FX; mostly operational cash plumbing. |

The common core, true of every archetype: **every firm must know and position its cash, forecast and fund its liquidity, and administer the accounts the cash moves through.** The collateral, financing and fund-finance capabilities are activated by what the firm trades and how it is structured.

**Why the manager-archetype row is split into sub-archetypes.** The discriminator the sub-archetype rows divide on in BD-11 is the **dominant liquidity profile** — operating-cash, ALM-buffer, or commitment-funding — and the financing-book weight. A third-party asset manager runs a balanced profile across many funds and mandates with share-class hedging and collateral on derivatives where used. A hedge fund's BD-11 is the heaviest and most front-office-adjacent — prime-brokerage financing, heavy margin and collateral, cross-product netting, a dedicated financing desk (SD-11.8 and SD-11.5 weight most). A private-markets manager runs an episodic, event-driven treasury — capital-call funding, distribution cash, subscription lines and NAV facilities (SD-11.6), with little day-to-day margin or sweep. An index / passive manager weights to cash-drag minimisation and the securities-lending revenue line; bespoke collateral is thin. The liquidity-profile discriminator is what the sub-typing makes visible; collapsing it would assert one treasury shape across managers that the cash and collateral operating model does not have.

## Wider-source grounding

Grounded against external industry references:

- The **ISDA collateral framework** — the ISDA Master Agreement and Credit Support Annex, and the ISDA Collateral Management Suggested Operational Practices, which defines collateral management as one discipline and grounds the SD-11.4 / SD-11.5 re-cut.
- The **BCBS-IOSCO margin framework** and the **Uncleared Margin Rules**; **EMIR** and **Dodd-Frank** clearing-and-margin.
- The **triparty-collateral model** — the ECB AMI-SeCo triparty harmonisation work and the triparty agents.
- The **securities-financing and fund-finance industries** — the repo and securities-lending markets, the GMRA and GMSLA master agreements, and the subscription-line / NAV-facility market.
- **ILPA** guidance on subscription-line use and disclosure.
- The buy-side treasury operating model and the treasury / collateral vendor capability maps as a completeness cross-check.
- **ISO 20022** and SWIFT cash messaging; **SEC Rule 2a-7** and the EU MMF Regulation, where cash and cash collateral are placed.
- The institution-archetype panel.

## Non-overlap — where the boundaries run

- **BD-11 vs BD-07 Investment Risk.** SD-07.3 Liquidity Risk Management *measures* liquidity risk and sets the limit; BD-11 *manages* the cash and funds the liquidity. Risk quantifies the exposure; treasury acts within it — the same measure-versus-manage seam the model draws between BD-07 and the front office.
- **BD-11 vs BD-12 Investment Operations.** Treasury makes the cash *decision and instruction* — to sweep, to fund, to move; operations *books, settles and reconciles* — SD-12.4 settles, SD-12.10 reconciles the cash, SD-12.5 oversees the custodian. SD-11.7 administers the bank accounts; SD-12.5 oversees the custody accounts.
- **SD-11.8 Securities Finance & Funding vs SD-12.13 Securities Lending Operations (cross-Business-Domain).** SD-11.8 owns the securities-lending *programme and financing book* — whether to lend, on what terms, the operating model, lending-agent oversight, the funding book and cash-collateral reinvestment. SD-12.13 owns the *operational loan book* — loan open, recall and return processing, per-loan collateral, lending-revenue accounting. SD-11.8 decides and funds; SD-12.13 operates the book.
- **BD-11 vs BD-05 Portfolio Management.** SD-05.4 Overlay & Hedging Management decides the currency overlay — the net exposure and hedge ratio; SD-11.3 *executes* the FX and runs the operational share-class hedging. The decision is the front office's; the execution is treasury's.
- **BD-11 vs BD-01.** SD-01.10 Commitment Pacing decides the *pace* of commitments; SD-11.6 *funds* the calls when they land. SD-01.11 sets the total-portfolio liquidity *strategy*; SD-11.2 *funds* the near-term need within it.
- **BD-11 vs BD-17 Corporate Services & Resources.** BD-11 is the treasury of the funds and portfolios under management, in a fiduciary capacity. The management company's own corporate treasury — the firm's operating cash and working capital — is BD-17's (SD-17.3 Corporate Treasury).

## Design notes

- **The Collateral/Margin pair is cut by workflow stage.** ISDA treats collateral management as one discipline; OpenIM splits SD-11.4 Margin & Collateral Operations (the daily cycle) from SD-11.5 Collateral Optimisation & Inventory Management (the firm-wide inventory) on the workflow-stage seam.
- **SD-11.4 is tagged BOTH.** Uncleared bilateral-CSA margin (the Uncleared Margin Rules) applies to any OTC-derivatives user, not only continuously-traded public portfolios.
- **Service Domain scopes.** SD-11.3 FX Execution & Share-Class Hedging (the overlay *decision* is BD-05's, not treasury's); SD-11.6 Fund Finance & Capital-Call Liquidity (the subscription-line / NAV-facility capability, not a vague "bridge financing"); SD-11.7 Bank Account & Mandate Administration (custodian-cash oversight is SD-12.5's).
- **Three owned entities and a key partition.** BD-11 owns DR-04 Margin & Collateral Balance (SD-11.4), E-26 Collateral Position (SD-11.5) and the cash partition of E-25 Account (SD-11.7, co-owned with SD-12.5 for the safekeeping partition). Facility structures remain process artefacts.
- **Cash & money markets as a discrete asset class is served through BD-11.** E-09 Asset Class names *cash and money markets* as one of nine asset classes — separate from fixed income. BD-11 is its principal home: **SD-11.1 Cash Management** owns the placement of surplus cash in money-market funds, short-dated instruments and deposits, governed by **SEC Rule 2a-7** and the **EU Money Market Fund Regulation**; **SD-11.2 Liquidity Management** sizes and maintains the liquidity buffer; **SD-11.7 Bank Account & Mandate Administration** owns the operating-cash bank-account discipline. SD-05.5 Cash Equitisation (in BD-05) removes the drag on idle cash where the strategy wants beta. The cash-and-money-markets *capability path* is therefore complete; the model deliberately serves it through these existing Service Domains rather than carving a dedicated Cash & Money Markets Service Domain.
- **Panel-substitution rationale — asset-owner collapse.** The single "Asset owner (pension / SWF / endowment)" row collapses DBP and SWF-E — BD-11's discriminating axis is **the two-sided liquidity pattern of an in-house owner** (funding outflows on one side, meeting capital calls on the other) and **the securities-lending programme scale**, not the asset-owner sub-archetype. A DB pension's benefit-payment funding and a SWF's spending-policy outflow share the same liability-style demand on BD-11; an endowment's spending policy shares the same pattern. The Insurer keeps its own row (ALM-driven, liability-cash-flow-sized buffer, uncleared UMR-scoped collateral on the ALM hedge book) — it is not included in the collapse, because ALM is the insurer's defining BD-11 activation.

## How BD-11 relates to the rest of the model

- **Consumes** the cash, position and derivative entities — Cash Flow Event (E-06), Holding / Position (E-04, `book = ibor` — treasury runs against the live IBOR position), Portfolio / Mandate (E-03), the derivative and collateral entities (DR-01 to DR-05), and the private-markets commitment entities (PM-01, PM-06, PM-07).
- **Owns** DR-04 Margin & Collateral Balance (SD-11.4); E-26 Collateral Position (SD-11.5) — the generic posted / received collateral record DR-04 and PB-10 both reference; and the cash partition of E-25 Account (SD-11.7, co-owned with SD-12.5 for the safekeeping partition). Facility structures remain process artefacts.
- **Feeds** BD-12 Investment Operations (the cash and settlement instructions), BD-07 Investment Risk (the liquidity and collateral position), BD-08 Valuation & Pricing (collateral into XVA), SD-12.9 Fund Accounting & NAV (the hedged share-class NAV), and treasury and investor governance.
