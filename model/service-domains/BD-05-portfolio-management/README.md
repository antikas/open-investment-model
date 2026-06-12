# BD-05 — Portfolio Management

**Office:** Front.

**Maturity:** Provisional · 13 Service Domains for construction, monitoring, rebalancing, transition, overlay, and class-specific sleeve management

The portfolio-construction-and-management capability — the domain that takes the allocation set by strategy (BD-01) and the securities, managers and assets selected (BD-02, BD-03, BD-04) and builds, monitors, rebalances and adjusts the actual portfolio. In the CFA portfolio-management process, BD-01 is the *planning* half and BD-05 is the *execution and feedback* half: BD-05 turns decisions into a target portfolio, keeps the live portfolio aligned to it, and shapes its exposures.

Each Service Domain below is its own file.

## Service Domains

| ID | Service Domain | Applies | What it does |
|---|---|---|---|
| SD-05.1 | [Portfolio Construction](SD-05.1-portfolio-construction.md) | BOTH | Builds the target portfolio from the allocation, the selected holdings and the construction mode the mandate permits. |
| SD-05.2 | [Portfolio Management & Monitoring](SD-05.2-portfolio-management-and-monitoring.md) | BOTH | Runs ongoing oversight of the portfolio against objectives, benchmark and constraints. |
| SD-05.3 | [Rebalancing](SD-05.3-rebalancing.md) | BOTH | Restores the portfolio to target weights when drift or cash flows breach tolerances. |
| SD-05.4 | [Overlay & Hedging Management](SD-05.4-overlay-and-hedging-management.md) | BOTH | Manages a derivatives book that shapes the portfolio's aggregate exposures. |
| SD-05.5 | [Cash Equitisation & Drag Management](SD-05.5-cash-equitisation-and-drag-management.md) | BOTH | Keeps uninvested cash exposed to markets and minimises cash drag. |
| SD-05.6 | [Liquidity-Aware Portfolio Management](SD-05.6-liquidity-aware-portfolio-management.md) | BOTH | Manages the portfolio's liquidity profile, including unfunded-commitment funding capacity. |
| SD-05.7 | [Model Portfolio & Sleeve Management](SD-05.7-model-portfolio-and-sleeve-management.md) | PUB | Constructs, maintains and delivers model portfolios and strategy sleeves across many accounts. |
| SD-05.8 | [Portfolio Transition Management](SD-05.8-portfolio-transition-management.md) | PUB | Manages the structured movement of a portfolio between strategies, managers or benchmarks. |
| SD-05.9 | [Alternative-Strategy Management](SD-05.9-alternative-strategy-management.md) | PUB | Runs the portfolio mechanics of long/short and other liquid-alternative strategies. |
| SD-05.10 | [Manager Structure](SD-05.10-manager-structure.md) | BOTH | Constructs and manages the portfolio of external managers and funds. |
| SD-05.11 | [Completion Portfolio Management](SD-05.11-completion-portfolio-management.md) | BOTH | Closes the gap between the portfolio's aggregate exposures and the total-portfolio or liability target. |
| SD-05.12 | [Commodity Exposure Management](SD-05.12-commodity-exposure-management.md) | BOTH | Runs a standing synthetic commodity exposure as a diversifying allocation, sized by strategy and expressed through futures, swaps and ETFs. |
| SD-05.13 | [Cash & Money-Market Portfolio Management](SD-05.13-cash-and-money-market-portfolio-management.md) | BOTH | Runs a cash and money-market allocation as a managed sleeve — WAM/WAL, credit-and-liquidity constraints, stable-value mechanics and gates-and-fees — sized by strategy. |

## Construction is mode-dependent — not one activity

**Portfolio construction is not one activity.** It runs in distinct modes, and which mode applies depends on what the investor controls:

- **Optimiser-driven** — picking and sizing positions in a continuously-priced, fully-controlled portfolio (mean-variance, risk-based, factor-budgeted). SD-05.1.
- **Index replication** — choosing a replication method (full / sampled / optimised) to track an index. SD-05.1, in its passive mode.
- **Manager-structure** — building the portfolio of managers. SD-05.10.
- **Pacing-driven** — for a private-markets portfolio, the investor cannot optimise weights it does not control; "construction" is the commitment-pacing schedule. That is **SD-01.10 Commitment Pacing & Deployment Planning** — a BD-01 capability SD-05.1 consumes.
- **Liability-driven** — for a pension or insurer, construction is the matching-versus-growth split and the hedge ratio. That is **SD-01.7 Liability-Driven & Cash-Flow-Driven Strategy** — a BD-01 capability SD-05.1 consumes.

SD-05.1 is therefore reframed mode-neutral: it constructs the target portfolio by the mode the mandate permits, *consuming* the pacing plan, the liability strategy and the manager structure rather than re-deciding them. The optimiser model is one mode, not the default — encoding it as the universal definition of construction would mis-model the private-markets, liability-driven and index archetypes.

## Archetype activation

The Service Domains a BD-05 implementation activates depend sharply on institution type. The model is the union; an implementation activates its subset. BD-05 deliberately uses a **Service Domain × archetype matrix** rather than the one-row-per-archetype table the other Business Domains use: BD-05's archetype differentiation runs at the individual-Service-Domain level, and the matrix is the form that carries that detail without loss.

| Service Domain | Asset manager | Asset owner | Wealth mgr | Hedge fund | Insurer | Index mgr |
|---|---|---|---|---|---|---|
| Construction (SD-05.1) | optimiser | manager-structure + pacing | model-driven | book-level | liability-driven | replication |
| Monitoring, Rebalancing, Cash | all activate |
| Overlay & Hedging (SD-05.4) | partial | core | partial | core | core | dormant |
| Liquidity-Aware (SD-05.6) | open-ended funds | core | partial | core (gates) | core | partial |
| Model Portfolio & Sleeve (SD-05.7) | **core** | dormant | **core** | dormant | dormant | ETF models |
| Transition (SD-05.8) | all activate it episodically |
| Alternative-Strategy (SD-05.9) | hedge-fund arm only | dormant | dormant | **core** | dormant | dormant |
| Manager Structure (SD-05.10) | multi-manager only | **core** | core | internal (pods) | partial | dormant |
| Completion (SD-05.11) | partial | core | dormant | partial | core (LDI) | dormant |
| Commodity Exposure (SD-05.12) | multi-asset only | core | partial | **core** | partial | partial |
| Cash & Money-Market (SD-05.13) | core (liquidity funds) | core | partial | core (cash mgmt) | core | **core** (MMF products) |

The clearest dormancy: Model Portfolios (SD-05.7) is dead for asset owners, hedge funds and insurers; Alternative-Strategy (SD-05.9) is dead for everyone but hedge funds; Manager Structure (SD-05.10) is the asset-owner core but dormant for single-strategy and index managers. Cash & Money-Market (SD-05.13) activates wherever a cash sleeve is held — and is the dedicated-product core for the manager that runs a money-market fund (the asset manager's liquidity range, the index manager's MMF products) — but is partial for the wealth manager, where the client cash sleeve is small.

**Why the manager-archetype row is split into sub-archetypes.** The discriminator the sub-archetype rows divide on in BD-05 is the **construction paradigm** — the manager-archetype manager column is sub-typed because the construction mode is what differentiates a BD-05 implementation, not the manager archetype itself. The Construction (SD-05.1) row makes this visible: an asset manager construct-by-optimiser, a private-markets manager construct-by-pacing-plus-manager-structure, a wealth manager construct-by-model-driven, a hedge fund construct-at-book-level, an insurer construct-liability-driven and an index manager construct-by-replication — each is a genuinely different construction paradigm with its own tools, governance and consumed inputs. Sub-typing the manager row by construction paradigm carries that differentiation into the activation matrix; collapsing it back would assert one construction shape across paradigms that the operating model does not have.

## Wider-source grounding

Grounded against external industry references:

- The **CFA Institute** treatment of portfolio construction (mean-variance, risk-based, factor-based, goals-based), rebalancing (calendar vs corridor), and the monitoring / feedback step.
- Overlay and **completion-portfolio management** (Russell, BlackRock, NISA), portable alpha, tail-risk hedging.
- Model portfolios and the unified-managed-account pattern; portfolio transition management and the T-Standard.
- The five construction modes across the institution-archetype panel — the finding that construction is mode-dependent.
- The buy-side platform capability maps (Aladdin, Charles River, SimCorp) at the portfolio-construction and what-if layer.
- For the cash and money-market sleeve (SD-05.13): **SEC Rule 2a-7** under the Investment Company Act of 1940 — the eligible-security, WAM / WAL, credit-quality and diversification rules, the daily / weekly liquid-asset minimums, the mandatory liquidity fee and the stable-value / shadow-NAV mechanics; the **EU Money Market Fund Regulation (MMFR)** and the ESMA-proposed reforms (CNAV / LVNAV / VNAV structures, liquidity buffers, the decoupling of liquidity thresholds from gates-and-fees); the **money-market-fund rating regimes** (S&P AAAm and the Moody's / Fitch principal-stability equivalents); and the **CFA Institute** fixed-income and liquidity-management body of knowledge. The institution-archetype finding: the cash sleeve is held across the whole panel, and is the dedicated-product core for the manager that runs a money-market fund — distinct from the treasury cash positioning every firm runs in SD-11.1.

## Non-overlap — where the boundaries run

- **BD-05 vs BD-01 Investment Strategy & Allocation (cross-Business-Domain).** BD-01 decides at the *asset-class-weight* level — the strategic and tactical allocation. BD-05 owns everything below it: security- and manager-level position sizing, and the trade list to reach the target. Rebalancing splits the same way — BD-01 sets the rebalancing *policy* in the mandate (the allowable drift, the corridor policy); SD-05.3 *calibrates and executes* it.
- **BD-05 vs BD-06 Trading & Execution (cross-Business-Domain).** BD-05 decides *what* trades are needed and *why* — it produces the trade list and the intent. BD-06 decides *how* and *when* to execute them. Implementation shortfall is measured in both — BD-06 for working an order, SD-05.8 for the whole transition event (the T-Standard) — two applications of one concept.
- **BD-05 vs BD-10 Investment Compliance & Guideline Monitoring (cross-Business-Domain).** BD-05 constructs and what-if-tests the portfolio; **SD-10.1 Investment Guideline Monitoring** runs the pre-trade and post-trade compliance rule engine. Construction proposes; SD-10.1 clears.
- **SD-05.1 vs SD-01.10 / SD-01.7 / SD-05.10.** SD-05.1 constructs the target portfolio but does not re-decide the commitment-pacing plan (SD-01.10), the liability strategy (SD-01.7) or the manager structure (SD-05.10) — it consumes them. For a private-markets or liability-driven mandate, SD-05.1's construction is largely the assembly of what those Service Domains decide.
- **SD-05.3 Rebalancing vs SD-05.4 Overlay & Hedging.** A rebalance can be physical (SD-05.3 trade list) or synthetic (a rebalancing overlay). The synthetic-rebalancing operation is shared — SD-05.3 owns the rebalance decision; SD-05.4 owns the derivative book that may express it.
- **SD-05.4 Overlay vs SD-05.5 Cash Equitisation.** SD-05.5 is a purpose-specific overlay — equitising idle cash to remove drag — sharing the futures and collateral machinery of SD-05.4 but kept separate because the buy-side names it as a distinct service. SD-05.4 *shapes* exposures; SD-05.5 *removes drag*.
- **SD-05.4 Overlay vs SD-05.11 Completion.** Both use overlay instruments. SD-05.4 shapes a portfolio's market exposures and is measured by hedge effectiveness. SD-05.11 closes a *structural gap* between the manager line-up's aggregate exposure and the total-portfolio or liability target, and is measured against that target — a different output, a different capability.
- **SD-05.10 Manager Structure vs BD-03 Manager & Fund Investment (cross-Business-Domain).** BD-03 sources, researches and selects the *individual* manager; SD-05.10 constructs the *portfolio of managers* — count, sizing, overlap, capacity. BD-03 feeds candidates to SD-05.10.
- **SD-05.9 Alternative-Strategy Management vs SD-01.9 Risk-Capital & Strategy Allocation (cross-Business-Domain).** SD-01.9 *allocates* risk capital across a hedge-fund platform's pods and strategies. SD-05.9 *runs the portfolio mechanics* of an alternative strategy — the long/short book, leverage, the short book, prime brokerage. SD-01.9 sizes the pod; SD-05.9 runs its book.
- **SD-05.12 Commodity Exposure Management vs SD-05.4 Overlay & Hedging and SD-05.5 Cash Equitisation.** All three run a derivatives book over the portfolio, and the boundary is purpose. SD-05.4 *shapes or hedges* the portfolio's existing exposures, measured by hedge effectiveness; SD-05.5 *removes cash drag* by equitising idle cash. SD-05.12 holds a *wanted, standing commodity exposure* — a diversifying allocation sized by SD-01.4 and measured against the commodity-allocation target. SD-05.4 reduces an unwanted exposure; SD-05.12 holds a wanted one.
- **SD-05.12 Commodity Exposure Management vs SD-04.10 Direct Real-Asset Management (cross-Business-Domain).** SD-05.12 holds *synthetic*, exchange-traded commodity-price exposure with no physical asset. SD-04.10 operates a *directly-held physical* natural-resource asset — timberland, farmland, a producing asset. The natural-resources / commodities asset class is invested through both routes; the split is the overlay-vs-direct mode boundary, not an asset-class boundary.
- **SD-05.12 Commodity Exposure Management vs SD-01.4 Strategic Asset Allocation (cross-Business-Domain).** SD-01.4 *decides* the size of the commodity allocation at the asset-class-weight level. SD-05.12 *implements and maintains* it — choosing the futures, swap or ETF expression, managing the roll, sizing collateral. BD-01 decides how much; SD-05.12 builds and holds it.
- **SD-05.13 Cash & Money-Market Portfolio Management vs SD-11.1 Cash Management (cross-Business-Domain).** This is the treasury-versus-investing boundary, and it is the one to get right. SD-11.1 is *treasury* — it positions the firm's and the funds' *operational* cash: it knows where the cash is today, runs the sweeps, funds the day's settlements, and places idle operational balances so they earn rather than sit idle — *including by buying money-market-fund units as a placement vehicle*. SD-05.13 is *investing* — it runs a cash and money-market allocation as a *managed asset-class sleeve*, or runs a money-market *product*: the WAM / WAL discipline, the credit-and-liquidity-constraint management, the stable-value (CNAV / LVNAV / VNAV and shadow-NAV) mechanics, and the gates-and-fees. The cut: SD-11.1 *places* operational cash (it is a buyer of a money-market fund); SD-05.13 *runs* the money-market allocation or *manages* the fund the cash is placed into. Treasury positions cash it must keep liquid for operations; portfolio management runs cash the mandate allocates to as an asset class.
- **SD-05.13 Cash & Money-Market Portfolio Management vs SD-05.1 Portfolio Construction.** SD-05.1 is the *mode-neutral* construction of the whole portfolio — it sets the position-level target across the asset classes the allocation spans, and consumes the cash-and-money-market sleeve as one of its inputs. SD-05.13 owns the *cash-class-specific* discipline that SD-05.1 does not carry: the maturity-ladder, credit-and-liquidity-constraint and stable-value management of the sleeve once the allocation has decided its size. This is the same split that makes SD-05.12 a distinct Service Domain rather than a fold into SD-05.1 — a named E-09 asset class with its own construction-and-maintenance discipline gets its own Service Domain.
- **SD-05.6 Liquidity-Aware Portfolio Management vs SD-01.11 Liquidity Strategy & Tiering and SD-07.3 Liquidity Risk Management (cross-Business-Domain).** SD-01.11 sets the *tier taxonomy and placement rules* — the buckets, the buffer, the liquid-to-illiquid linking policy at the strategy layer above any single portfolio. SD-07.3 *produces* the per-holding liquidity classification (applying the SD-01.11 taxonomy). SD-05.6 *consumes* that classification and applies the policy within a specific portfolio — managing the held portfolio's liquidity profile, including its unfunded-commitment funding capacity. SD-05.6 does not produce the classification; it builds the portfolio liquidity budget against it. The bilateral of the boundary stated in the BD-01 README.

## Design notes

- **SD-05.1 is mode-neutral.** Portfolio construction is mode-dependent; SD-05.1 covers the modes BD-05 owns (optimiser-driven, factor-risk, replication) and consumes the modes other Service Domains own (pacing, liability strategy, manager structure).
- **SD-05.11 Completion Portfolio Management is a distinct capability** — measured against the liability or total-portfolio target, not hedge effectiveness.
- **SD-05.12 Commodity Exposure Management.** Natural resources / commodities is a named E-09 asset class; its *direct* route is BD-04 and its *fund* route is BD-03; the *synthetic* commodity-overlay route — a standing diversifying exposure expressed through futures, swaps and ETFs — is a fourth derivatives-book capability alongside SD-05.4, SD-05.5 and SD-05.11, kept separate for the same reason those three are: each is measured against a different target.
- **SD-05.13 Cash & Money-Market Portfolio Management.** Cash and money markets is a named E-09 asset class — a governed allocation segment, not a residual of fixed income — and its investing discipline (WAM / WAL, the credit-and-liquidity constraints, the stable-value CNAV / LVNAV / VNAV and shadow-NAV mechanics, the gates-and-fees of the money-market-fund regimes) is its own. SD-05.13 owns it, on the same logic as SD-05.12: a named asset class with a distinct construction-and-maintenance discipline gets its own Service Domain rather than folding into the mode-neutral SD-05.1. It is the *investing* counterpart to SD-11.1's *treasury* cash positioning — SD-11.1 places operational cash (including into money-market funds as a vehicle); SD-05.13 runs the money-market allocation or the money-market product.
- **No new master entities.** BD-05 consumes the portfolio, holding, valuation, benchmark, risk and derivatives entities and produces target portfolios and trade lists as analytical artefacts.
- **Panel-substitution rationale — asset-owner collapse (as a matrix column).** BD-05's archetype activation is rendered as a **Service Domain × archetype matrix** rather than the one-row-per-archetype table the other Business Domains use, because BD-05's archetype differentiation runs at the individual-Service-Domain level. Within that matrix, the single **"Asset owner"** column collapses DBP and SWF-E — BD-05's construction-mode axis (optimiser / manager-structure + pacing / liability-driven / replication / book-level / model-driven) cuts on capability shape, not between DBP and SWF-E. The pension-vs-SWF asset-owner differences (LDI weighting, pacing-driven mode emphasis) shape the cell contents but do not warrant a panel split. The **"Insurer"** column is kept separate from the asset-owner column — the liability-driven construction mode is the insurer's defining BD-05 activation. The OCIO is not represented as a column because the matrix renders the construction-mode cut and the OCIO inherits the third-party-asset-manager column's activation per the landscape rule.

## How BD-05 relates to the rest of the model

- **Consumes** the portfolio and holding entities — Portfolio / Mandate (E-03), Holding / Position (E-04, `book = ibor` — front office runs against the IBOR), Valuation (E-07, any `method`), Instrument / Asset (E-02) — the reference and risk entities — Benchmark / Index (E-10), Risk Limit (E-16), Risk Measurement (E-19, any `risk_type`) — the allocation set by BD-01, the securities and managers selected by BD-02 / BD-03 / BD-04, and the commitment-pacing plan (SD-01.10) and manager structure it builds from.
- **Owns** no master entity. The target portfolio, the trade list and the construction model are analytical artefacts.
- **Feeds** BD-06 Trading & Execution (the trade lists it produces), BD-10 Investment Compliance (which clears them), BD-09 Performance & Analytics (which measures the result), and BD-07 Investment Risk (which monitors the portfolio it runs).
