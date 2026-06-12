# PM-09 — Fund Investment

A fund's holding in something it has deployed capital into — a portfolio company, or, for a fund-of-funds, another fund. One row per (fund, holding) pair. The entity that connects a fund (PM-01) to what it holds, and the unit at which look-through exposure is computed.

**Specialises:** E-04 Holding / Position. Where the core Holding is the *investor's* position in a fund interest, the Fund Investment is the *fund's* own position — the layer below, reached by look-through.

## Purpose

When an investor commits to a fund, the fund deploys that capital. A direct fund deploys it into **portfolio companies**. A **fund-of-funds** deploys it into **other funds**. The Fund Investment is the record of one such holding either way: the fund's stake in one company, or one fund's stake in another fund.

Look-through exposure analysis (SD-07.5) decomposes Fund Investments to answer "what is our total exposure to this company across every vehicle?" — the question the core Holding entity alone cannot answer, because the investor's own holding is a position in a *fund*, not in the underlying. For a direct fund this is one decomposition step. For a fund-of-funds it is **recursive**: investor → fund-of-funds → underlying funds → portfolio companies. The Fund Investment entity supports that recursion because its target may itself be a fund.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `investment_id` | varchar | Primary key. |
| `fund_id` | varchar (FK → PM-01) | The fund holding the position. |
| `holding_type` | varchar | What the position is in: `portfolio_company` (a direct fund's holding) or `fund` (a fund-of-funds' holding in an underlying fund). |
| `target_id` | varchar | The thing held — a PM-04 Portfolio Company when `holding_type = portfolio_company`, a PM-01 Fund when `holding_type = fund`. |
| `investment_type` | varchar | The structure of the exposure: `fund` / `jv` / `co_invest` / `sma` / `blind_pool` / `fund_of_funds`. |
| `entry_date` | date | When the position was taken. |
| `exit_date` | date | When the position was realised; null while held. |
| `invested_usd` | decimal | Cost basis — capital deployed into the position. |
| `realised_usd` | decimal | Capital returned through realisations. |
| `unrealised_nav_usd` | decimal | Current unrealised net asset value of the position. |
| `moic` | float | Multiple on invested capital. |
| `gross_irr` | float | Gross internal rate of return on the position. |
| `exit_route` | varchar | Trade sale, IPO, secondary, recapitalisation. |

## Notes

- **Fund-of-funds.** A fund-of-funds is, structurally, a fund whose Fund Investment rows have `holding_type = fund` — it holds positions in other funds rather than in companies. No separate entity is needed for the fund-of-funds itself; it is a PM-01 Fund (its strategy recorded as fund-of-funds), and its holdings are Fund Investments that target funds. Distinguish this from a **master-feeder** structure, which is intra-family (a feeder vehicle channelling into a master *of the same fund family*) and is handled by PM-01's `fund_family_id` + `vehicle_type = feeder` — a fund-of-funds holds *unrelated, third-party* funds.
- **Look-through is recursive.** Because `target_id` can point to a fund, SD-07.5 Look-Through Exposure Analysis must traverse the holding graph to arbitrary depth — investor holding → fund → (fund →)* → portfolio company — to compute true exposure. The entity model supports the recursion; the traversal is the service domain's.
- The `investment_type` discriminator makes co-investment amplification visible: an investor may hold exposure to one company through the main fund *and* a co-investment vehicle *and* another manager's fund. Each is a separate Fund Investment row; look-through aggregation sums them.
- The position is held through one or more Legal Vehicles (PM-05); cash flows record at vehicle grain and roll up here.
- A fund-of-funds also makes **commitments** to the underlying funds it holds — see PM-06 LP Commitment, where the committing LP may itself be a fund.

## Out of scope

- The investor's own position in a fund interest — that is the core E-04 Holding / Position; PM-09 is the *fund's* own position, the layer below, reached by look-through.
- The portfolio company or underlying fund a position is in — those are PM-04 Portfolio Company and PM-01 Fund & Vehicle, referenced through `target_id`.
- The legal vehicle a position is held through — that is PM-05 Legal Vehicle / SPV; cash flows record at vehicle grain and roll up to PM-09.
- A fund-of-funds' commitment to an underlying fund — that is PM-06 LP Commitment, where the committing LP is itself a fund.

## Owned and consumed by

- **Owned by:** SD-12.1 Investment Book of Record (IBOR).
- **Consumed by:** SD-07.5 Look-Through Exposure Analysis, SD-07.4 Concentration & Exposure Risk, SD-09.8 Private-Markets Performance Analytics, SD-05.2 Portfolio Management & Monitoring, SD-04.8 Portfolio-Company Stewardship & Value Creation.

## Open extensions

- The relationship between Fund Investment and PM-05 Legal Vehicle when a position is held through multiple vehicles.
- The ownership-percentage attribution needed to compute the investor's attributed NAV from the fund's position NAV — applied at each level of a recursive fund-of-funds look-through.
- The recursive look-through traversal and its termination — formalised in SD-07.5 when the service domain is expanded.
