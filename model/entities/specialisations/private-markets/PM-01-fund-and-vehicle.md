# PM-01 — Fund & Vehicle

The golden record of an investment fund and the legal vehicles that make it up — the primary commitment vehicle for an investor that invests through external managers. Includes the **Fund Family / Group** grouping that ties the related vehicles of a single raise together.

**Specialises:** E-02 Instrument / Asset. An LP's stake in a fund is a Holding (E-04) in an Instrument of `instrument_class = fund_interest`; PM-01 is the entity that specifies the fund behind that instrument.

## What the master covers

A "fund" as an investor experiences it is rarely a single legal entity. A single raise is commonly three to five or more vehicles:

- **Main fund** — the primary vehicle.
- **Parallel vehicles** — investing alongside the main fund pro-rata, as separate legal entities for regulatory, tax or investor-type reasons. Legally distinct, economically equivalent.
- **Feeder funds** — channelling capital into a master fund structure.
- **Co-investment vehicles** — deal-specific, outside the main fund.
- **Continuation vehicles** — manager-led secondaries moving assets from a maturing fund into a new vehicle.

The investor needs both individual-vehicle tracking *and* a family hierarchy: "what is my position in this specific vehicle?" and "what is my total commitment across every vehicle of this fund family?"

## Why it is hard

The difficulty is **not** managers calling the same fund different things — a manager knows its own fund's name. The real challenges: **cross-source naming variation** (the same fund appears differently across a capital-call notice, a manager report, an administrator statement, a data vendor and the investor's own system); **structure complexity** (the main / parallel / feeder / co-invest / continuation set); and **vintage-series ambiguity** (Roman versus Arabic numerals, regional suffixes).

## Attribute schema — Fund

| Column | Type | Definition |
|---|---|---|
| `fund_id` | varchar | **Golden key.** The OpenIM-assigned canonical identifier for the vehicle. |
| `fund_name` | varchar | Canonical name. |
| `fund_family_id` | varchar (FK → Fund Family) | Links the vehicle to its family. |
| `vehicle_type` | varchar | `main` / `parallel` / `feeder` / `co_invest` / `continuation`. |
| `gp_id` | varchar (FK → PM-02) | The managing GP / management company. |
| `administrator_id` | varchar (FK → PM-03) | The fund administrator. |
| `asset_class` | varchar (FK → E-09) | Private equity, real estate, infrastructure, private credit, natural resources, secondaries. |
| `strategy` | varchar | Buyout, growth, venture, distressed, core, value-add, direct lending, etc. |
| `vintage_year` | int | Fund inception year. |
| `committed_capital_usd` | decimal | The investor's commitment to *this specific vehicle*. |
| `currency` | char | The fund's base currency. |
| `domicile` | varchar | The fund's jurisdiction. |
| `fund_status` | varchar | `active` / `harvesting` / `fully_realised`. |
| `known_aliases` | array | Every name the fund has been seen under (the in-record view of E-13). |
| `lei` | varchar | Legal Entity Identifier, where one exists. |
| `external_ids` | map | Data-vendor fund IDs — PitchBook, Preqin, Burgiss (the in-record view of E-14). |
| `last_reviewed_at` | date | Date of the last steward review. |

## Attribute schema — Fund Family / Group

| Column | Type | Definition |
|---|---|---|
| `fund_family_id` | varchar | **Golden key** for the family. |
| `family_name` | varchar | Canonical family name. |
| `gp_id` | varchar (FK → PM-02) | The managing GP. |
| `total_committed_usd` | decimal | Sum of the investor's commitments across every vehicle in the family. |
| `vehicle_count` | int | Number of vehicles in the family. |

## Structures the fund model carries

Three fund structures are distinct and the model keeps them so:

- **Master-feeder** — a feeder vehicle channels capital into a master fund *of the same raise*. Intra-family. Handled by `fund_family_id` + `vehicle_type = feeder`.
- **Parallel vehicles** — separate legal entities investing alongside the main fund pro-rata. Intra-family. Handled by `fund_family_id` + `vehicle_type = parallel`.
- **Fund-of-funds** — a fund that holds positions in *unrelated, third-party* funds rather than in portfolio companies. This is **not** a family structure and **not** a vehicle type — it is recorded as the fund's `strategy`, and its structural expression is that its PM-09 Fund Investment rows have `holding_type = fund`. A fund-of-funds also commits to the funds it holds: it appears as the committing LP on those PM-06 LP Commitments, in the Legal Entity LP role. See PM-09 and PM-06.

## Resolution

Three-tier matching — exact external-ID match, alias / normalised-name match, steward review queue. Funds carry **lower unresolved volume** than portfolio companies: most are onboarded proactively by investment operations before the manager's data flows. Unresolved cases are usually naming variations or genuinely new parallel / feeder vehicles within a known family.

## Out of scope

- The generic instrument record a fund interest specialises — that is E-02 Instrument / Asset of `instrument_class = fund_interest`; PM-01 specifies the fund behind that instrument.
- The investor's *position* in a fund — that is E-04 Holding / Position; PM-01 is the fund, not the holding of its interest.
- A fund's own holdings in portfolio companies or underlying funds — that is PM-09 Fund Investment, reached by look-through.
- The fund's economic terms — hurdle, fee, carry, clawback — that is PM-10 Fund Terms, one versioned record per fund.
- The LP's commitment to the fund — that is PM-06 LP Commitment; PM-01 is the fund itself, not the commitment relationship.
- **The manager's issued-product view of the same fund.** PM-01 is the *allocator's commitment-vehicle view* — the institution as an LP or outside investor committing capital to a fund. The *manager's issued-product view* of that same fund — the registered, priced and distributed collective investment vehicle from the issuing manager's perspective — is FO-01 Fund Product (fund-operations pack). The two are discriminated on the issuance axis: PM-01 records `committed_capital_usd` (the investor's own obligation to the fund); FO-01 records the product-lifecycle, dealing-terms and regulatory-authorisation attributes that govern how the fund operates as an issued product. An institution that both invests in funds and operates its own carries both records for the same fund.

## Owned and consumed by

- **Owned by:** SD-13.3 Investment Vehicle & Fund Master.
- **Populated via:** SD-03.5 Fund Commitment & Subscription, SD-13.6 GP & Manager Report Ingestion.
- **Consumed by:** SD-03.6 GP & Manager Monitoring, SD-09.8 Private-Markets Performance Analytics, SD-11.6 Fund Finance & Capital-Call Liquidity, SD-12.8 Capital Call & Distribution Processing, SD-12.9 Fund Accounting & NAV, SD-12.15 Transfer Agency & Investor Dealing (the fund vehicle record anchors the investor register).

## Open extensions

- **Alias / external-identifier canonicality.** E-13 Entity Alias and E-14 External Identifier are canonical for the fund's aliases and external identifiers; the in-record `known_aliases` array and `external_ids` map on PM-01 are a declared denormalised read-cache, derivable from E-13 / E-14 and regenerated from them, not an independent source.
- The relationship to PM-10 Fund Terms — one Fund Terms record per fund, versioned by effective date.
- The master / feeder nesting and SPV-nesting depth.
- The fund-interest instrument (E-02) and how a fund's lifecycle attributes flow to it.
