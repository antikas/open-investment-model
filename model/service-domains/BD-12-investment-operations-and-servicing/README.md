# BD-12 - Investment Operations and Servicing

**Office:** Back

**Maturity:** Provisional · 17 Service Domains

BD-12 maintains investment books and processes the events that change them. It covers trade confirmation, settlement, asset servicing, fund accounting and reconciliation.

The domain also covers the operational work behind custody, securities lending, proxy voting and fund-investor servicing. Its outputs provide governed position, cash and accounting records to the rest of the firm.

Each Service Domain below has its own definition, boundary, operations and entity links.

## Service Domains

| ID | Service Domain | Applies | What it does |
|---|---|---|---|
| SD-12.1 | [Investment Book of Record (IBOR)](SD-12.1-investment-book-of-record-ibor.md) | BOTH | Maintains the intraday view of positions, cash and exposures used by investment teams. |
| SD-12.2 | [Accounting Book of Record (ABOR)](SD-12.2-accounting-book-of-record-abor.md) | BOTH | Maintains the official accounting view of holdings and balances. |
| SD-12.3 | [Trade Confirmation and Matching](SD-12.3-trade-confirmation-and-matching.md) | BOTH | Confirms and matches trade details with brokers or counterparties. |
| SD-12.4 | [Trade Settlement](SD-12.4-trade-settlement.md) | PUB | Completes the exchange of securities and cash. |
| SD-12.5 | [Custody and Safekeeping Oversight](SD-12.5-custody-and-safekeeping-oversight.md) | BOTH | Oversees assets held by custodians and depositories. |
| SD-12.6 | [Corporate Actions Processing](SD-12.6-corporate-actions-processing.md) | PUB | Processes mandatory and voluntary events that affect holdings. |
| SD-12.7 | [Income and Distribution Processing](SD-12.7-income-and-distribution-processing.md) | BOTH | Processes investment income and cash distributions received. |
| SD-12.8 | [Capital Call and Distribution Processing](SD-12.8-capital-call-and-distribution-processing.md) | PRIV | Processes drawdowns and distributions against fund commitments. |
| SD-12.9 | [Fund Accounting and NAV](SD-12.9-fund-accounting-and-nav.md) | BOTH | Maintains fund-level books and strikes net asset value for operated vehicles. |
| SD-12.10 | [Reconciliation](SD-12.10-reconciliation.md) | BOTH | Reconciles records across internal books and external providers. |
| SD-12.11 | [Expense, Fee and Carry Processing](SD-12.11-expense-fee-and-carry-processing.md) | BOTH | Calculates or verifies fees, carried interest and expenses. |
| SD-12.12 | [Proxy Voting and Stewardship Operations](SD-12.12-proxy-voting-and-stewardship-operations.md) | PUB | Operates proxy voting and maintains the related stewardship record. |
| SD-12.13 | [Securities Lending Operations](SD-12.13-securities-lending-operations.md) | PUB | Operates securities loans, recalls and returns. |
| SD-12.14 | [Derivatives Lifecycle Processing](SD-12.14-derivatives-lifecycle-processing.md) | BOTH | Processes post-trade events for OTC and cleared derivatives. |
| SD-12.15 | [Transfer Agency and Investor Dealing](SD-12.15-transfer-agency-and-investor-dealing.md) | BOTH | Maintains the investor register and processes open-ended fund dealing. |
| SD-12.16 | [Outsourced Operations Oversight](SD-12.16-outsourced-operations-oversight.md) | BOTH | Reviews an outsourced administrator's operational output. |
| SD-12.17 | [Tax-Lot Accounting](SD-12.17-tax-lot-accounting.md) | BOTH | Maintains client-level tax lots and their accounting history. |

## Non-overlap and boundaries

| Boundary | Distinction |
|---|---|
| SD-12.1 IBOR and SD-12.2 ABOR | IBOR is the intraday investment view. ABOR is the official accounting view. E-04 distinguishes them through its `book` value, and SD-12.10 reconciles them. |
| SD-12.6 Corporate Actions and SD-12.7 Income Processing | SD-12.6 owns the event terms and elections. SD-12.7 owns the resulting income receipt, accrual and withholding-tax treatment. |
| SD-12.7 Income Processing and SD-12.8 Capital Calls | SD-12.8 captures the fund event and classifies a distribution as return of capital, income or realised gain. SD-12.7 books the received cash leg using that classification. |
| SD-12.9 Fund Accounting and BD-09 Performance | SD-12.9 produces fund books and NAV. BD-09 calculates performance from NAV and cash-flow records. |
| SD-12.9 Fund Accounting and BD-08 Valuation | BD-08 values individual holdings. SD-12.9 combines those values with the rest of the fund balance sheet to strike NAV. |
| SD-13.6 Report Ingestion and BD-12 processing | SD-13.6 extracts structured facts from source documents. BD-12 books or processes the resulting operational event. |
| SD-12.9 Fund Accounting and SD-12.2 ABOR | SD-12.2 keeps the investor-side accounting book. SD-12.9 keeps books for funds or vehicles operated by the institution. |
| SD-12.11 Fee Processing and SD-12.9 Fund Accounting | SD-12.11 calculates or verifies an amount. SD-12.9 accrues that amount into the operated fund's books. |
| SD-12.6 Corporate Actions and SD-12.12 Proxy Voting | SD-12.6 captures the shareholder-meeting event. SD-12.12 owns the voting decision and ballot process. |
| SD-12.12 Proxy Voting and SD-12.13 Securities Lending | SD-12.12 decides whether a vote requires a recall. SD-12.13 executes the recall of a loaned security. |
| SD-12.13 Lending Operations and SD-11.8 Securities Finance | SD-11.8 sets the lending programme and financing policy. SD-12.13 operates individual loans and recalls. |
| SD-12.14 Derivatives Lifecycle and SD-06.6 Trade Management | SD-06.6 initiates and books the trade. SD-12.14 processes resets, novations, compression and termination after execution. |
| SD-12.14 Derivatives Lifecycle and SD-11.4 Collateral | SD-12.14 processes contract events. SD-11.4 processes margin calls and collateral movements against the relationship. |
| SD-12.5 Custody Oversight and SD-17.8 Provider Oversight | SD-12.5 reviews asset-level safekeeping. SD-17.8 manages the commercial provider relationship and outsourcing risk. |
| SD-12.15 Transfer Agency and SD-12.8 Capital Calls | SD-12.15 processes open-ended subscriptions, redemptions and switches. SD-12.8 processes closed-end calls and distributions. |
| SD-12.15 Transfer Agency and BD-15 Client Management | SD-12.15 owns register and dealing operations. BD-15 owns the commercial investor relationship. |
| SD-12.16 and SD-12.9 Fund Accounting | SD-12.9 produces an in-house NAV. SD-12.16 runs a shadow calculation to check an administrator's NAV. |
| SD-12.16 and SD-12.10 Reconciliation | SD-12.10 reconciles the firm's records. SD-12.16 reviews an administrator's reconciliation process and break handling. |
| SD-12.16 and SD-12.5 Custody Oversight | SD-12.5 reviews assets held by a custodian. SD-12.16 reviews operational output produced by an administrator. |
| SD-12.16 and SD-17.8 Provider Oversight | SD-12.16 checks delegated operational work. SD-17.8 manages the provider contract, outsourcing risk and commercial relationship. |
| SD-04.6 Deal Closing and BD-12 | SD-04.6 completes the legal transaction. BD-12 records and services the resulting holding after completion. |
| SD-12.12 Proxy Voting and SD-04.8 Portfolio Company Stewardship | SD-12.12 covers public-market shareholder voting. SD-04.8 covers active ownership of a controlled or significant direct holding. |

## Design notes

- The IBOR and ABOR remain separate because they serve different purposes and can hold different values during the day.
- Public-market operations use the `PUB` tag. Private-market fund events use `PRIV`. Capabilities shared across both use `BOTH`.
- Derivatives lifecycle processing has its own domain because the contract continues through resets, novations and other events after trade execution.
- Fund accounting applies when the institution operates vehicles. Transfer agency applies when those vehicles maintain an investor register and process open-ended subscriptions, redemptions or switches.
- Fund wind-down remains in SD-12.9 as the terminal fund-accounting lifecycle. Legal dissolution flows to SD-14.9, LPAC consent and term extensions to SD-16.1, and final audit to SD-14.8.
- Tax-lot accounting uses a finer client and acquisition grain than the position-level ABOR.

## Archetype activation

The first activation question is which books, markets and operational functions the institution runs. Operating a vehicle activates fund accounting. Transfer agency activates only for vehicles with open-ended register and dealing operations. SD-12.16 applies where the firm delegates middle- or back-office processing and retains operational oversight.

| Archetype | Typical BD-12 use |
|---|---|
| Third-party asset manager | Uses investor-side operations, activates fund accounting for operated products and usually treats SD-12.16 as core. Transfer agency applies to open-ended products with register and dealing operations. |
| Pension, sovereign or endowment | Uses investor-side books and servicing. Fund-operator capabilities apply only to internal vehicles, while SD-12.16 applies to the functions it delegates. |
| Insurer | Uses general-account books and activates fund operations for operated linked products. SD-12.16 applies to delegated functions. |
| Wealth manager or private bank | Uses client-level books and relevant pooled-product operations. SD-12.16 is partial where operations are delegated. |
| OCIO or fiduciary manager | Uses delegated portfolio operations and treats SD-12.16 as core. Vehicle capabilities depend on the service and products it operates. |
| Hedge fund | Uses operated-fund accounting and usually treats SD-12.16 as core. Investor dealing applies where it runs open-ended register and dealing operations. |

## Wider-source grounding

The domain uses external standards and bodies at its operating boundaries:

- ISO 15022 and ISO 20022 for relevant securities messages
- ISITC practices for investment operations
- Common Domain Model, under FINOS stewardship and developed from ISDA's CDM lineage, for derivatives lifecycle concepts
- custody and depositary requirements under relevant fund regimes
- ILPA templates for private-capital call and distribution reporting

Specific Service Domain files record the standards relevant to their own scope.

## How BD-12 relates to the rest of the model

### Information consumed

BD-12 uses the core portfolio, holding, transaction and cash-flow entities. It also consumes valuation, legal-entity and instrument records.

Specialised inputs include public-market settlement and asset-servicing entities, private-market fund events, and derivatives contract records. Each Service Domain file lists its exact inputs.

### Information owned

- SD-12.1 owns the IBOR partition of E-04 Holding / Position, plus E-05 Transaction and E-06 Cash Flow Event.
- SD-12.2 owns the ABOR partition of E-04.
- SD-12.4 owns PB-06 Settlement Instruction.
- SD-12.5 owns the safekeeping partition of E-25 Account.
- SD-12.6 owns PB-07 Corporate Action.
- SD-12.8 owns PM-07 Capital Call and PM-08 Distribution.
- SD-12.9 owns PM-13 Investor Capital Account.
- SD-12.10 owns E-24 Reconciliation Break.
- SD-12.12 owns PB-11 Proxy Vote.
- SD-12.13 owns PB-10 Securities Loan.

### Capabilities served

The reconciled books feed investment risk, valuation and performance capabilities. Portfolio management uses the IBOR, while treasury funds settlement and capital calls. Reporting and governance capabilities consume the resulting records.
