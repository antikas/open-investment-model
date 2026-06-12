# E-02 — Instrument / Asset

The universal "thing an investor can hold." Every position (E-04) is a position in an Instrument / Asset. The entity spans the full span of what an institutional investor holds — listed equity, government and corporate debt, structured credit, listed and OTC derivatives, fund interests, loans, real assets held directly, cash and money-market instruments.

## Why one holdable-thing master

The first cut of OpenIM treated "Instrument" as a thin public-markets stub and modelled the private-markets holdings (funds, portfolio companies) as the centre of gravity. That inverts the real shape. *Every* institutional investor holds positions in things; the things differ by asset class. The generalised model has **one Instrument / Asset master** with **asset-class subtyping**: a listed equity, a bond, a fund interest and a directly-held building are all instruments/assets, distinguished by `instrument_class` and by the specialisation entity that carries each one's specific structure.

A **fund interest** — an LP's stake in a private fund — is, in this model, one kind of instrument/asset among many. That is the move that lets the closed-end-fund-vehicle form of holding sit as a *specialisation* rather than as the spine.

## FIBO alignment

This is, with E-01 Legal Entity, where OpenIM most directly **builds on FIBO**. FIBO's Securities and Derivatives domains already model what an equity, a bond, a derivative *are*. OpenIM does not re-define instrument semantics — E-02 and its public-markets / derivatives specialisations align to the FIBO concepts and add only what the buy-side operating model needs. The per-class FIBO mapping is recorded in [`../../fibo-alignment.md`](../../fibo-alignment.md).

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `instrument_id` | varchar | **Golden key.** The OpenIM-assigned canonical identifier. |
| `instrument_name` | varchar | Canonical name. |
| `instrument_class` | varchar | The top-level kind — `listed_equity` / `debt` / `listed_derivative` / `otc_derivative` / `fund_interest` / `loan` / `real_asset` / `cash` / `structured_product`. |
| `asset_class` | int (FK → E-09) | The asset class — the integer surrogate key `asset_class_key` of the E-09 entry. |
| `issuer_entity_id` | varchar (FK → E-01) | The issuing legal entity, where the instrument has an issuer (debt, equity); null where it does not (a directly-held real asset). |
| `currency` | char | Denomination / trading currency. |
| `isin` | varchar | ISIN, where one exists. |
| `figi` | varchar | FIGI / OpenFIGI identifier, where one exists. |
| `external_ids` | map | Other identifiers — CUSIP, SEDOL, Private CUSIP, vendor instrument IDs (the in-record view of E-14). |
| `status` | varchar | `active` / `matured` / `redeemed` / `delisted`. |

## Subtyping — the specialisation hand-off

`instrument_class` says what kind of thing this is; the **specialisation entity** carries the structure that kind needs:

- A `fund_interest` is specified by **PM-01 Fund & Vehicle** in the private-markets pack — the fund's strategy, vintage, vehicle type, terms.
- A `listed_equity` or `debt` instrument is specified by the **public-markets pack** (`PB-NN`) — issue and maturity detail, coupon structure, the issuer relationship.
- A `listed_derivative` or `otc_derivative` is specified by the **derivatives pack** (`DR-NN`) — underlying, terms, the master-agreement reference.
- A `real_asset` is specified by the **real-assets pack** (`RA-NN`).

The core E-02 record is what every position points to; the specialisation is where the asset-class-specific depth lives.

## Identifier reality

Liquid instruments largely *have* universal identifiers — ISIN, CUSIP, SEDOL, FIGI — so for the public-markets and derivatives classes the master-data problem is normalisation across vendor feeds, not entity resolution. A `fund_interest`, by contrast, inherits the no-universal-identifier reality of private markets; its resolution is the hard case handled in the private-markets pack.

## Out of scope

- The asset-class-specific depth of an instrument — issue and maturity detail, fund terms, derivative legs, real-asset attributes — that is the specialisation entity (`PB-NN` / `PM-NN` / `DR-NN` / `RA-NN`) the `instrument_class` hands off to, not the core E-02 record.
- The *position* the investor holds in an instrument — that is E-04 Holding / Position; E-02 is the thing held, not the holding of it.
- The issuing legal entity itself — that is E-01 Legal Entity in the `issuer` role; E-02 references it through `issuer_entity_id`.
- The asset-class taxonomy an instrument is classified against — that is E-09 Asset Class, which E-02 references through `asset_class`.

## Owned and consumed by

- **Owned by:** SD-13.1 Instrument & Security Master.
- **Consumed by:** E-04 Holding / Position (every position references an instrument); SD-06 Trading & Execution, SD-07.1 Market Risk Management, SD-08 Valuation & Pricing, SD-09 Performance & Analytics.

## Open extensions

- **External-identifier canonicality.** E-14 External Identifier is canonical for an instrument's external identifiers; the in-record `external_ids` map on E-02 (and the dedicated `isin` / `figi` columns) is a declared denormalised read-cache, derivable from E-14 and regenerated from it, not an independent source.
- The full per-class attribute depth, delivered through the public-markets, derivatives and real-assets specialisation packs.
- The instrument-issuer relationship modelled fully for debt (the issuer is the credit).
- The concrete FIBO Securities / Derivatives concept mapping.
