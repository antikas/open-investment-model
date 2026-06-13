#!/usr/bin/env python3
"""Deterministic synthetic-data generator for the BD-09 / NAV-strike seed.

Emits the ten seed CSVs in this directory. The data is SYNTHETIC — realistic in
shape and internally consistent (every holding has valuations across the quarters;
cash flows / trades are dated; the numbers tie together so a NAV and a return are
computable) — but it is NOT real and NOT production-grade. See README.md.

Run from this directory (or anywhere):

    python generate_synthetic_seed.py

The generator is seeded (a fixed RNG seed) so the CSVs are byte-stable across
runs: re-running emits identical files, so `dbt build` stays idempotent and the
diff is empty on a no-op regenerate. It conforms to the ten OpenIM entity schemas
(the schema-drift check stays green — the staging views select exactly the model
columns; the append-only entities additionally carry an operational `recorded_at`
knowledge-time column that the bi-temporal intermediate models read and the
schema-faithful staging views do not select).

Three funds, by the public/private/multi-asset split:
  FUND-PM  Evergreen Private Markets Fund  — private-markets (PE / credit / RE / infra)
  FUND-EQ  Meridian Global Equity Fund     — public equities (DM + EM)
  FUND-MA  Polaris Multi-Asset Fund        — multi-asset (the union, public + private)
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import random
from decimal import Decimal
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parent

# A fixed RNG seed so the output is byte-stable: re-running emits identical CSVs, so
# `dbt build` stays idempotent and a no-op regenerate produces an empty diff.
RNG = random.Random(20260531)

# --- the as-of (valid-time) axes -----------------------------------------------
# Two cadences, both realistic for an institutional NAV-strike substrate:
#  - MONTH_ENDS: liquid holdings (listed equity / debt / cash) are valued monthly,
#    the public NAV-strike cadence — 24 month-ends of history.
#  - QUARTER_ENDS: illiquid holdings (private fund interests, real assets) are
#    valued quarterly, the private-markets manager-mark cadence — the 8 quarter-ends
#    that fall within the 24-month window. Risk + performance run quarterly.


def _month_end(y: int, m: int) -> dt.date:
    if m == 12:
        return dt.date(y, 12, 31)
    return dt.date(y, m + 1, 1) - dt.timedelta(days=1)


def _build_month_ends(start_year: int, start_month: int, n: int) -> list[dt.date]:
    out: list[dt.date] = []
    y, m = start_year, start_month
    for _ in range(n):
        out.append(_month_end(y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


MONTH_ENDS = _build_month_ends(2024, 4, 24)            # Apr-2024 .. Mar-2026 (24 months)
QUARTER_ENDS = [d for d in MONTH_ENDS if d.month in (3, 6, 9, 12)]  # the 8 quarter-ends

# The knowledge-time (system-time) axis: each quarter's marks are first recorded a
# few days after quarter-end (the "as first struck" knowledge state). A subset of
# private-markets marks are LATER REVISED (a restatement recorded weeks later) —
# that revision is the bi-temporal case the intermediate models + the as-of-knowledge
# query exercise. `recorded_at` is an operational provenance column, NOT a model
# attribute (so it is absent from the schema-faithful staging views).
def first_recorded(q: dt.date) -> dt.date:
    return q + dt.timedelta(days=10)


def revised_recorded(q: dt.date) -> dt.date:
    return q + dt.timedelta(days=55)


def w(name: str, header: list[str], rows: list[list]) -> None:
    """Write a CSV with LF newlines (matches .gitattributes reference/**/*.csv eol=lf)."""
    path = SEED_DIR / name
    with path.open("w", newline="\n", encoding="utf-8") as fh:
        wr = csv.writer(fh, lineterminator="\n")
        wr.writerow(header)
        wr.writerows(rows)
    print(f"  wrote {name}: {len(rows)} rows")


def _write_break_labels_json(header: list[str], rows: list[list]) -> None:
    """Write the labels manifest as JSON too — the oracle the reconciliation engine /
    eval read. A list of objects keyed by the same E-24 vocabulary as the CSV header.
    Deterministic: stable key order, LF newline, trailing newline (byte-stable)."""
    records = [dict(zip(header, r, strict=True)) for r in rows]
    payload = {
        "description": (
            "Synthetic labelled-break oracle for the W2 reconciliation substrate. "
            "Each record is a deliberately-injected break between the internal book and "
            "the synthetic external comparator feed (custodian holdings/cash + "
            "administrator statement). The taxonomy is E-24 Reconciliation Break's "
            "vocabulary (reconciliation_type / cause_classification / materiality). This "
            "manifest is the zero-missed-breaks ground truth: a reconciliation engine "
            "run over the feed must detect exactly these breaks and no others."
        ),
        "count": len(records),
        "breaks": records,
    }
    path = SEED_DIR / "break_labels.json"
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    print(f"  wrote break_labels.json: {len(records)} breaks")


# ---------------------------------------------------------------------------
# E-09 Asset Class — the nine-class taxonomy (the controlled reference data).
# ---------------------------------------------------------------------------
ASSET_CLASSES = [
    (1, "PUB_EQ", "Public Equities", "DM", "", "public"),
    (2, "FIXED_INC", "Fixed Income", "GOVT", "", "public"),
    (3, "CASH_MM", "Cash & Money Markets", "TBILL", "", "public"),
    (4, "PRIV_EQ", "Private Equity", "BUYOUT", "", "private"),
    (5, "PRIV_CREDIT", "Private Credit", "DIRECT_LENDING", "", "private"),
    (6, "REAL_ESTATE", "Real Estate", "CORE", "", "private"),
    (7, "INFRA", "Infrastructure", "CORE", "", "private"),
    (8, "NAT_RES", "Natural Resources / Commodities", "TIMBERLAND", "", "both"),
    (9, "HEDGE_FUNDS", "Hedge Funds / Active Strategies", "MACRO", "", "public"),
]


def gen_e09() -> None:
    rows = [
        [k, code, label, strat, sub, mkt, "2018-01-01", ""]
        for (k, code, label, strat, sub, mkt) in ASSET_CLASSES
    ]
    w(
        "raw_e09_asset_class.csv",
        ["asset_class_key", "asset_class_code", "asset_class_label", "strategy_code",
         "sub_strategy_code", "markets", "effective_from", "effective_to"],
        rows,
    )


# ---------------------------------------------------------------------------
# Fund definitions — the three funds, their asset-class mix, and holding counts.
# ---------------------------------------------------------------------------
# Each fund: id, name, manager LE, inception, base ccy, and a list of
# (asset_class_key, n_holdings, instrument_class, method, level, source) sleeves.
FUNDS = [
    {
        "fund_id": "FUND-PM",
        "name": "Evergreen Private Markets Fund",
        "manager": "LE-0001",
        "inception": "2018-01-01",
        "sleeves": [
            (4, 8, "fund_interest", "manager_mark", "level_3", "manager_report"),     # PE
            (5, 6, "fund_interest", "manager_mark", "level_3", "manager_report"),     # private credit
            (6, 4, "real_asset", "appraisal", "level_3", "appraiser"),                # real estate
            (7, 2, "real_asset", "appraisal", "level_3", "appraiser"),                # infra
        ],
    },
    {
        "fund_id": "FUND-EQ",
        "name": "Meridian Global Equity Fund",
        "manager": "LE-0001",
        "inception": "2018-01-01",
        "sleeves": [
            (1, 16, "listed_equity", "observable_price", "level_1", "pricing_feed"),  # DM + EM equities
            (3, 2, "cash", "observable_price", "level_1", "pricing_feed"),            # cash
            (2, 2, "debt", "observable_price", "level_2", "pricing_feed"),            # short FI
        ],
    },
    {
        "fund_id": "FUND-MA",
        "name": "Polaris Multi-Asset Fund",
        "manager": "LE-0001",
        "inception": "2019-01-01",
        "sleeves": [
            (1, 8, "listed_equity", "observable_price", "level_1", "pricing_feed"),   # equities
            (2, 5, "debt", "observable_price", "level_2", "pricing_feed"),            # fixed income
            (4, 3, "fund_interest", "manager_mark", "level_3", "manager_report"),     # PE sleeve
            (6, 2, "real_asset", "appraisal", "level_3", "appraiser"),                # RE sleeve
            (9, 2, "fund_interest", "mark_to_model", "level_2", "internal_model"),    # hedge funds
            (3, 1, "cash", "observable_price", "level_1", "pricing_feed"),            # cash
        ],
    },
]


# Dedicated RNGs for the W2 additions (the IBOR divergence, the E-05/E-06 seeds and
# the comparator feed). Kept SEPARATE from the main RNG so adding the W2 layer does
# NOT shift the deterministic stream that produces the valuations / risk / performance
# — the existing eleven seeds stay byte-stable, so the W1 NAV-strike path is untouched.
# Each is fixed-seeded, so the W2 seeds are byte-stable across runs too.
RNG_DIV = random.Random(20260604)   # the IBOR/ABOR divergence pass
RNG_TXN = random.Random(20260605)   # the E-05 / E-06 generation pass
RNG_CMP = random.Random(20260606)   # the comparator feed + the labelled-break injection


# The labelled-break taxonomy — aligned 1:1 to E-24 Reconciliation Break's vocabulary
# (model/entities/core/E-24-reconciliation-break.md). The labels manifest IS the
# zero-missed-breaks oracle a reconciliation eval scores the engine against, so its
# `taxonomy_class` (cause) + `reconciliation_type` are E-24's own enums, not a parallel set.
#   - reconciliation_type ∈ position / cash / transaction / ibor_abor / custodian / counterparty
#   - cause_classification ∈ timing / pricing / missing_transaction / data_error / fx / fees / unexplained
#   - materiality         ∈ low / medium / high
# The goal's five-class taxonomy (price · quantity · missing/extra txn · timing/TD-SD · FX)
# maps onto E-24's cause_classification: price→pricing, quantity→data_error (a quantity
# mismatch with no timing cause is a data error in E-24's vocabulary), missing/extra
# txn→missing_transaction, timing/TD-SD→timing, FX→fx.
_BREAK_CAUSES = ("pricing", "data_error", "missing_transaction", "timing", "fx")


def _apply_ibor_divergence(
    holding_universe: list[dict], positions: list[list], latest_q: dt.date
) -> dict[str, list[dict]]:
    """Make the IBOR book genuinely divergent from the ABOR accounting truth.

    ABOR is the NAV-bearing book and is left UNCHANGED (so the W1 NAV-strike path is
    untouched). IBOR is rewritten in place across three characterised divergence
    classes — the differences SD-12.10's IBOR/ABOR reconciliation finds:

      1. TRADE-DATE vs SETTLEMENT-DATE TIMING. IBOR is the real-time, trade-date book;
         ABOR is the accounting, settlement-date book. A BUY agreed on/before the as-of
         date but settling AFTER it is in IBOR (trade-date recognition) but NOT yet in
         ABOR (settlement-date recognition) — so IBOR's quantity and market value are
         HIGHER than ABOR's across the TD–SD window. (A matching `pending`/`confirmed`
         E-05 transaction with settlement_date > as_of is emitted in the txn pass.)
      2. ACCRUALS. ABOR carries accrued but unpaid income (accrual-basis accounting);
         the real-time IBOR view does not. So IBOR's accrued_income is 0 where ABOR's
         is non-zero (the debt holdings).
      3. COST-BASIS / LOT TREATMENT. The two books carry the position's cost on
         different lot conventions — ABOR on an average-cost / amortised accounting
         basis, IBOR on a trade-date lot basis — so cost_basis_usd differs.

    Returns a `divergence_index`: pos_id -> list of divergence records (used by the
    transaction pass to emit the matching in-flight trades, and recorded for the report
    + the dictionary). Deterministic (RNG_DIV).
    """
    index: dict[str, list[dict]] = {}
    settleable = [h for h in holding_universe if h["ins_class"] in ("listed_equity", "debt")]
    # stable order for deterministic selection
    settleable_sorted = sorted(settleable, key=lambda h: h["pos_id"])

    # 1) TD/SD timing — pick ~6 settleable holdings with an in-flight buy.
    n_timing = min(6, len(settleable_sorted))
    timing_holdings = RNG_DIV.sample(settleable_sorted, n_timing) if n_timing else []
    for h in timing_holdings:
        row = positions[h["ibor_row_idx"]]
        abor_qty = Decimal(h["abor_qty"]) if h["abor_qty"] else Decimal(0)
        abor_mv = Decimal(h["abor_mv"]) if h["abor_mv"] else Decimal(0)
        # the in-flight trade: a buy of 5–20% of the held quantity, value pro-rata
        trade_qty = (abor_qty * Decimal(RNG_DIV.randint(5, 20)) / Decimal(100)).quantize(Decimal("1"))
        if trade_qty <= 0:
            trade_qty = Decimal(RNG_DIV.randint(500, 5000))
        unit_price = (abor_mv / abor_qty) if abor_qty > 0 else Decimal(RNG_DIV.randint(50, 200))
        trade_value = (trade_qty * unit_price).quantize(Decimal("0.01"))
        settle = latest_q + dt.timedelta(days=RNG_DIV.randint(1, 2))
        # IBOR (trade-date basis) includes the in-flight buy; ABOR (settlement) does not.
        ibor_qty = (abor_qty + trade_qty)
        ibor_mv = (abor_mv + trade_value).quantize(Decimal("0.01"))
        row[5] = str(ibor_qty)        # quantity
        row[8] = str(ibor_mv)         # market_value_usd
        index.setdefault(h["pos_id"], []).append({
            "class": "timing", "trade_qty": str(trade_qty), "trade_value": str(trade_value),
            "settlement_date": settle.isoformat(), "unit_price": str(unit_price.quantize(Decimal("0.0001"))),
            "abor_qty": str(abor_qty), "ibor_qty": str(ibor_qty),
        })

    # 2) Accruals — IBOR drops the abor accrual (already empty on the ibor row); record
    #    the divergence for every debt holding that carries an abor accrual.
    for h in holding_universe:
        if h["abor_accr"]:
            index.setdefault(h["pos_id"], []).append({
                "class": "accrual", "abor_accrued": h["abor_accr"], "ibor_accrued": "0",
            })

    # 3) Cost-basis / lot — pick ~4 holdings; IBOR cost differs from ABOR cost.
    cost_pool = sorted(
        [h for h in holding_universe if h["abor_cost"] and h["pos_id"] not in
         {th["pos_id"] for th in timing_holdings}],
        key=lambda h: h["pos_id"],
    )
    n_cost = min(4, len(cost_pool))
    cost_holdings = RNG_DIV.sample(cost_pool, n_cost) if n_cost else []
    for h in cost_holdings:
        row = positions[h["ibor_row_idx"]]
        abor_cost = Decimal(h["abor_cost"])
        # IBOR trade-date lot basis differs from ABOR average-cost by 1–4%.
        factor = Decimal(1) + Decimal(RNG_DIV.randint(-4, 4)) / Decimal(100)
        if factor == 1:
            factor = Decimal("1.02")
        ibor_cost = (abor_cost * factor).quantize(Decimal("0.01"))
        row[7] = str(ibor_cost)       # cost_basis_usd
        index.setdefault(h["pos_id"], []).append({
            "class": "cost_basis", "abor_cost": str(abor_cost), "ibor_cost": str(ibor_cost),
        })

    return index


def _gen_transactions_and_cash_flows(
    holding_universe: list[dict],
    fund_total_pf: dict[str, str],
    divergence_index: dict[str, list[dict]],
    latest_q: dt.date,
) -> tuple[list[list], list[list]]:
    """Seed E-05 Transaction + E-06 Cash Flow Event, tied to the E-04/E-07 book.

    E-05: settled historic trades + the in-flight (pending/confirmed) trades that drive
    the TD/SD divergence (settlement_date > as_of). Each transaction carries trade_date,
    settlement_date, status, type and the portfolio/instrument it touches.
    E-06: the cash consequences — dividends/coupons on holdings, fees, the cash leg of a
    settled trade — dated, signed, typed, tied to the transactions/holdings.
    Deterministic (RNG_TXN). The model files are the oracle for the columns.
    """
    transactions: list[list] = []
    cash_flows: list[list] = []
    txn_seq = 0
    cf_seq = 0
    pos_by_id = {h["pos_id"]: h for h in holding_universe}

    # a counterparty pool (the custodian + a couple of brokers for trades)
    counterparties = ["LE-0002", "LE-0001"]

    # 1) the in-flight trades behind the TD/SD divergence (status pending/confirmed,
    #    settlement_date > as_of) — one per timing-divergence record.
    for pos_id, recs in sorted(divergence_index.items()):
        h = pos_by_id[pos_id]
        for rec in recs:
            if rec["class"] != "timing":
                continue
            txn_seq += 1
            status = RNG_TXN.choice(["pending", "confirmed"])
            trade_value = Decimal(rec["trade_value"])
            transactions.append([
                f"TXN-{txn_seq:05d}", "trade", h["sleeve_pf"], h["ins_id"],
                latest_q.isoformat(), rec["settlement_date"], rec["trade_qty"],
                str(trade_value), RNG_TXN.choice(counterparties), status, "oms",
            ])
            rec["transaction_id"] = f"TXN-{txn_seq:05d}"  # link the divergence to its txn

    # 2) settled historic trades — a couple per holding over the window (the activity
    #    that built the position). Each generates a cash leg (E-06).
    for h in sorted(holding_universe, key=lambda x: x["pos_id"]):
        if h["ins_class"] not in ("listed_equity", "debt", "cash", "fund_interest"):
            continue
        n_trades = RNG_TXN.randint(1, 2)
        for _ in range(n_trades):
            txn_seq += 1
            ttype = "subscription" if h["ins_class"] == "fund_interest" else "trade"
            td = MONTH_ENDS[RNG_TXN.randint(0, len(MONTH_ENDS) - 3)]
            sd = td + dt.timedelta(days=2)
            qty = (Decimal(RNG_TXN.randint(500, 20000)) if h["ins_class"] in ("listed_equity", "debt", "cash") else "")
            amt = (h["base"] * Decimal(RNG_TXN.randint(5, 30)) / Decimal(100)).quantize(Decimal("0.01"))
            transactions.append([
                f"TXN-{txn_seq:05d}", ttype, h["sleeve_pf"], h["ins_id"],
                td.isoformat(), sd.isoformat(), str(qty) if qty != "" else "",
                str(-amt), RNG_TXN.choice(counterparties), "settled", "oms",
            ])
            # the cash leg of the settled trade (an outflow — cash paid for the buy)
            cf_seq += 1
            cash_flows.append([
                f"CF-{cf_seq:05d}", h["sleeve_pf"], h["ins_id"], f"TXN-{txn_seq:05d}",
                sd.isoformat(), "principal", "outflow", str(-amt), "USD", "custodian_feed",
            ])

    # 3) income cash flows — dividends on equities, coupons on debt, a fee per fund.
    for h in sorted(holding_universe, key=lambda x: x["pos_id"]):
        if h["ins_class"] == "listed_equity" and RNG_TXN.random() < 0.6:
            cf_seq += 1
            amt = (h["base"] * Decimal(RNG_TXN.randint(1, 4)) / Decimal(1000)).quantize(Decimal("0.01"))
            cash_flows.append([
                f"CF-{cf_seq:05d}", h["sleeve_pf"], h["ins_id"], "",
                MONTH_ENDS[-2].isoformat(), "dividend", "inflow", str(amt), "USD", "custodian_feed",
            ])
        elif h["ins_class"] == "debt":
            cf_seq += 1
            amt = (h["base"] * Decimal(RNG_TXN.randint(2, 5)) / Decimal(1000)).quantize(Decimal("0.01"))
            cash_flows.append([
                f"CF-{cf_seq:05d}", h["sleeve_pf"], h["ins_id"], "",
                MONTH_ENDS[-2].isoformat(), "coupon", "inflow", str(amt), "USD", "custodian_feed",
            ])
    # a management fee per fund (a portfolio-level outflow)
    for fund_id, total_pf in sorted(fund_total_pf.items()):
        cf_seq += 1
        amt = Decimal(RNG_TXN.randint(50_000, 250_000))
        cash_flows.append([
            f"CF-{cf_seq:05d}", total_pf, "", "", latest_q.isoformat(),
            "fee", "outflow", str(-amt), "USD", "administrator",
        ])

    return transactions, cash_flows


def _gen_comparator_feed(
    holding_universe: list[dict],
    positions: list[list],
    transactions: list[list],
    cash_flows: list[list],
    divergence_index: dict[str, list[dict]],
    fund_total_pf: dict[str, str],
    latest_q: dt.date,
) -> tuple[list[list], list[list], list[list], list[list]]:
    """Build the synthetic external comparator feed + the labelled-break oracle.

    Derives a custodian holdings file, a custodian cash file and a fund-administrator
    statement FROM the internal book (the IBOR book — the firm's real-time positions are
    what a position reconciliation matches against the custodian), so the MAJORITY of rows
    agree. Then injects N catalogued, labelled breaks across the five taxonomy classes
    (price · quantity · missing/extra txn · timing/TD-SD · FX), recording each in the
    labels manifest (`break_labels`) with its E-24 taxonomy class, cause, materiality and
    expected side. The labels manifest IS the zero-missed-breaks oracle. Deterministic
    (RNG_CMP). A clear majority of rows are left UNBROKEN (the engine must find the breaks).

    The oracle is VALUE-CORRECT and SOUND in three ways the assert_comparator tests
    enforce (every difference between the feed and the internal book reconciles to exactly
    one label whose class AND value match; every label backs a real data difference):

      - CASH is derived, not drawn independently. The custodian cash balance is the base;
        the administrator cash is set to `custodian ± labelled_delta` on the broken fund(s)
        and EXACTLY EQUAL on the unbroken funds — so the actual custodian-vs-admin
        difference equals the manifest cash label, and unbroken funds carry no unlabelled
        divergence.
      - EXACTLY ONE custodian holdings row per holding (per `position_id`). A timing-break
        holding's single row IS the broken (lagged-quantity) row — no duplicate clean twin.
      - Every TIMING break is grounded in a REAL in-flight E-05 trade: the timing targets
        are drawn from the holdings that carry a `pending`/`confirmed` trade settling after
        the as-of date (the same in-flight trades that drive the IBOR/ABOR TD/SD divergence),
        and the custodian's lag EQUALS that in-flight trade's quantity (the custodian, on a
        settlement-date basis, has not yet booked the not-yet-settled trade the internal
        trade-date book shows).
    """
    # the IBOR book rows (the firm's real-time positions the custodian recon matches)
    ibor_rows = [r for r in positions if r[1] == "ibor"]

    custodian_holdings: list[list] = []   # custodian's position record per holding
    custodian_cash: list[list] = []       # custodian's cash balances
    admin_statement: list[list] = []      # the administrator's statement lines
    break_labels: list[list] = []         # the labelled-break oracle
    brk_seq = 0

    # choose which holdings carry an injected break — a deterministic MINORITY.
    ibor_sorted = sorted(ibor_rows, key=lambda r: r[0])

    # plan: 2 breaks per per-holding class across the 4 position classes (price · quantity
    # · FX · timing/TD-SD) + the 2 transaction breaks (missing/extra) + 1 cash break.
    # PRICE + FX need a market value (every holding has one); QUANTITY + TIMING need a
    # share count (the quantity-bearing holdings only — listed_equity / debt / cash).
    #
    # TIMING is GROUNDED in real in-flight trades, not drawn at random. A custodian
    # TD/SD timing break models "the internal book booked the trade on trade-date but the
    # custodian, on a settlement-date basis, has not yet booked it" — so it is only
    # coherent on a holding that ACTUALLY carries a pending/confirmed trade settling after
    # the as-of date. Those are exactly the holdings in `divergence_index` with a `timing`
    # record (the in-flight buys that drive the IBOR/ABOR TD/SD divergence). We pick the
    # timing targets from that grounded set and use the in-flight trade's quantity as the
    # custodian lag — so the break's narrative is real, not decorative.
    ibor_by_pos = {r[0]: r for r in ibor_sorted}
    inflight: list[tuple[list, Decimal]] = []  # (ibor row, in-flight trade qty)
    for pos_id in sorted(divergence_index):
        for rec in divergence_index[pos_id]:
            if rec.get("class") == "timing" and ibor_by_pos.get(pos_id) is not None and ibor_by_pos[pos_id][5]:
                inflight.append((ibor_by_pos[pos_id], Decimal(rec["trade_qty"])))
                break
    n_timing = min(2, len(inflight))
    timing_targets = inflight[0:n_timing]                 # (row, in-flight qty) pairs
    timing_chosen = {row[0] for row, _q in timing_targets}

    value_pool = list(ibor_sorted)             # all have a market value
    qty_pool = [r for r in ibor_sorted if r[5] and r[0] not in timing_chosen]  # r[5] = quantity
    RNG_CMP.shuffle(value_pool)
    RNG_CMP.shuffle(qty_pool)
    # quantity draws distinct holdings from the quantity-bearing pool (excluding timing)
    qty_targets = qty_pool[0:2]
    qty_chosen = {r[0] for r in qty_targets} | timing_chosen
    # price + fx draw distinct holdings from the remaining value pool (avoid qty/timing ones)
    value_avail = [r for r in value_pool if r[0] not in qty_chosen]
    price_targets = value_avail[0:2]
    fx_targets = value_avail[2:4]

    def _materiality(amount: Decimal) -> str:
        a = abs(amount)
        if a >= Decimal(500_000):
            return "high"
        if a >= Decimal(50_000):
            return "medium"
        return "low"

    # the timing lag per timing-target holding == the in-flight trade's quantity (grounded).
    timing_lag_by_pos = {row[0]: lag_qty for row, lag_qty in timing_targets}

    # build the custodian holdings file from the IBOR book — EXACTLY ONE row per holding
    # (per position_id), injecting the labelled breaks IN PLACE (a timing-break holding's
    # single row IS the broken row; there is no duplicate clean twin).
    for r in ibor_sorted:
        pos_id, _book, pf, ins, asof, qty, _commit, _cost, mv, ccy, _accr = r
        cust_qty = qty
        cust_price_mv = mv
        cust_ccy = ccy
        note = ""
        # TIMING (TD/SD) break: the internal book booked an in-flight trade on trade-date;
        # the custodian, on a settlement-date basis, has NOT yet booked it — so the
        # custodian quantity LAGS the internal book by exactly the in-flight trade's
        # quantity. Grounded in a real pending/confirmed E-05 trade (timing_lag_by_pos is
        # built from divergence_index's in-flight trades). One row per holding: this IS
        # that holding's custodian row (no separate clean twin).
        if pos_id in timing_lag_by_pos and qty:
            lag = timing_lag_by_pos[pos_id]
            cust_qty = str(Decimal(qty) - lag)
            brk_seq += 1
            break_labels.append([
                f"BRK-{brk_seq:04d}", "position", "timing", pos_id, "custodian",
                "", str(lag), "low",
                f"trade booked trade-date internally but settlement-date by the custodian "
                f"for {pos_id} (TD/SD timing; custodian lags {lag} units — the in-flight "
                f"trade quantity)",
            ])
            note = "timing_break"
        # PRICE break: custodian marks the security differently (a pricing difference)
        if r in price_targets and mv:
            base_mv = Decimal(mv)
            delta = (base_mv * Decimal(RNG_CMP.randint(2, 8)) / Decimal(100)).quantize(Decimal("0.01"))
            cust_price_mv = str((base_mv + delta).quantize(Decimal("0.01")))
            brk_seq += 1
            break_labels.append([
                f"BRK-{brk_seq:04d}", "position", "pricing", pos_id, "custodian",
                str(delta), "", _materiality(delta),
                f"custodian marks {pos_id} {delta} above the internal IBOR mark",
            ])
            note = "price_break"
        # QUANTITY break: custodian holds a different share count (a data error)
        if r in qty_targets and qty:
            base_qty = Decimal(qty)
            qd = (base_qty * Decimal(RNG_CMP.randint(2, 10)) / Decimal(100)).quantize(Decimal("1"))
            if qd <= 0:
                qd = Decimal(RNG_CMP.randint(50, 500))
            cust_qty = str(base_qty - qd)
            brk_seq += 1
            break_labels.append([
                f"BRK-{brk_seq:04d}", "position", "data_error", pos_id, "custodian",
                "", str(qd), "medium",
                f"custodian share count for {pos_id} is {qd} units below the internal book",
            ])
            note = "qty_break"
        # FX break: a currency-translation difference on the custodian's USD value
        if r in fx_targets and mv:
            base_mv = Decimal(mv)
            fx_delta = (base_mv * Decimal(RNG_CMP.randint(1, 3)) / Decimal(100)).quantize(Decimal("0.01"))
            cust_price_mv = str((base_mv - fx_delta).quantize(Decimal("0.01")))
            brk_seq += 1
            break_labels.append([
                f"BRK-{brk_seq:04d}", "position", "fx", pos_id, "custodian",
                str(fx_delta), "", _materiality(fx_delta),
                f"custodian USD-translates {pos_id} at a different FX rate ({fx_delta} difference)",
            ])
            note = "fx_break"
        custodian_holdings.append([
            f"CUST-H-{pos_id}", "GCB", pos_id, pf, ins, asof, cust_qty, cust_price_mv, cust_ccy, note,
        ])

    # custodian cash balances per fund — the BASE the administrator cash is derived from.
    # One balance per fund. The administrator cash (below) is set EXACTLY EQUAL to this on
    # the unbroken funds and to `custodian ± labelled_delta` on the broken fund — so the
    # actual custodian-vs-admin cash difference EQUALS the manifest cash label (no
    # independent random draws, no unlabelled cash divergence).
    funds_sorted = sorted(fund_total_pf.values())
    custodian_cash_by_fund: dict[str, Decimal] = {}
    for total_pf in funds_sorted:
        bal = Decimal(RNG_CMP.randint(1_000_000, 10_000_000))
        custodian_cash_by_fund[total_pf] = bal
        custodian_cash.append([
            f"CUST-C-{total_pf}", "GCB", total_pf, latest_q.isoformat(), str(bal), "USD",
        ])

    # the administrator statement — NAV-level + a cash line per fund; inject a
    # MISSING-TRANSACTION break (a settled trade in the internal book absent from the
    # admin's transaction record) and a CASH break.
    settled_txns = [t for t in transactions if t[9] == "settled"]
    # MISSING TRANSACTION break: drop one settled trade from the admin's record + label it.
    missing_txn = settled_txns[len(settled_txns) // 2] if settled_txns else None
    admin_txn_ids = {t[0] for t in settled_txns}
    if missing_txn is not None:
        admin_txn_ids.discard(missing_txn[0])
        brk_seq += 1
        amt = Decimal(missing_txn[7])
        break_labels.append([
            f"BRK-{brk_seq:04d}", "transaction", "missing_transaction", missing_txn[0],
            "internal", str(amt), "", _materiality(amt),
            f"settled transaction {missing_txn[0]} present in the internal book is absent "
            f"from the administrator's transaction record",
        ])
    # EXTRA TRANSACTION break: the admin records a transaction the internal book lacks.
    brk_seq += 1
    extra_amt = Decimal(RNG_CMP.randint(80_000, 400_000))
    extra_txn_id = "ADMIN-TXN-EXTRA-01"
    break_labels.append([
        f"BRK-{brk_seq:04d}", "transaction", "missing_transaction", extra_txn_id,
        "custodian", str(extra_amt), "", _materiality(extra_amt),
        f"administrator records transaction {extra_txn_id} that is absent from the internal book",
    ])
    # admin statement transaction lines (the settled txns minus the missing one, plus the extra)
    for t in settled_txns:
        if missing_txn is not None and t[0] == missing_txn[0]:
            continue
        admin_statement.append([
            f"ADMIN-T-{t[0]}", "transaction", t[2], t[3], t[4], t[7], "USD", t[0],
        ])
    admin_statement.append([
        "ADMIN-T-EXTRA", "transaction", sorted(fund_total_pf.values())[0], "", latest_q.isoformat(),
        str(-extra_amt), "USD", extra_txn_id,
    ])
    # CASH break on the admin statement: the administrator cash balance is DERIVED from the
    # custodian cash, not drawn independently. The first fund (i == 0) carries the single
    # cash break — its admin balance is `custodian + labelled_delta`, and the manifest's
    # cash `difference_amount` is EXACTLY that delta (sign and magnitude). Every OTHER
    # fund's admin balance is set EQUAL to its custodian balance — so it carries NO
    # unlabelled cash divergence. Result: the actual custodian-vs-admin difference on every
    # fund reconciles to the manifest (exactly one cash label, value-correct; zero
    # unlabelled cash differences).
    for i, total_pf in enumerate(funds_sorted):
        cust_bal = custodian_cash_by_fund[total_pf]
        line_note = ""
        if i == 0:
            # the broken fund: admin = custodian + the labelled delta (a positive delta —
            # the administrator shows MORE cash than the custodian). A medium-band delta.
            cash_delta = Decimal(RNG_CMP.randint(50_000, 499_999))
            admin_bal = cust_bal + cash_delta
            brk_seq += 1
            break_labels.append([
                f"BRK-{brk_seq:04d}", "cash", "data_error", total_pf, "internal",
                str(cash_delta), "", _materiality(cash_delta),
                f"administrator cash balance for {total_pf} disagrees with the custodian "
                f"by {cash_delta} (cash reconciliation break)",
            ])
            line_note = "cash_break"
        else:
            # an unbroken fund: admin cash EQUALS custodian cash exactly (no divergence).
            admin_bal = cust_bal
        admin_statement.append([
            f"ADMIN-C-{total_pf}", "cash", total_pf, "", latest_q.isoformat(),
            str(admin_bal), "USD", line_note,
        ])

    return custodian_holdings, custodian_cash, admin_statement, break_labels


# The enrichment RNG — a dedicated stream so the enrichment does NOT shift the
# base streams (RNG_DIV / RNG_TXN / RNG_CMP). The base eleven breaks stay byte-stable;
# the enrichment is a SUPPLEMENT appended after them (the base labelled breaks are
# preserved, never restated).
RNG_ENR = random.Random(20260612)


def _materiality_band(amount: Decimal) -> str:
    """The oracle materiality band by absolute magnitude — matches `_materiality` above."""
    a = abs(amount)
    if a >= Decimal(500_000):
        return "high"
    if a >= Decimal(50_000):
        return "medium"
    return "low"


def _enrich_comparator_feed(
    custodian_holdings: list[list],
    custodian_cash: list[list],
    admin_statement: list[list],
    break_labels: list[list],
    positions: list[list],
    transactions: list[list],
    cash_flows: list[list],
    divergence_index: dict[str, list[dict]],
    fund_total_pf: dict[str, str],
    portfolios: list[list],
    latest_q: dt.date,
) -> tuple[list[list], list[list], list[list], list[list], list[list], list[list]]:
    """Data enrichment — make the safety machinery exercised ON DATA.

    Takes the base feed (the eleven byte-stable breaks) and SUPPLEMENTS it so the
    reconciliation engine's dual-pipeline disagreement, the cash Pipeline-B replay and the
    fx/pricing robustness paths fire on the live feed (not only on constructed test rows):

      (a) BALANCE-GRADE E-06. Adds an opening-balance cash-flow event per fund so the E-06
          replay sums to a figure of the same order/sign as the custodian balance — the cash
          Pipeline-B `_replay_is_balance_grade` gate now PASSES on data (abstention → 0), and
          the base cash break is found by BOTH pipelines (preserved, not restated).
      (b) A GENUINE A/B-DISAGREEMENT case. One holding's IBOR E-04 book value is set EQUAL to
          the custodian (Pipeline A clears) while its E-07 mark stays divergent (Pipeline B
          breaks) — `n_pipeline_disagreements > 0` on data, surfaced + labelled.
      (c) BREAK-SET EXPANSION (N=29). Three adversarial fx/pricing
          misclassification shapes (single-holding fx; a coincidental shared-ratio pricing
          pair; a pricing ratio colliding with an fx ratio) + ≥1 further instance per existing
          taxonomy class + a materiality spread — every break labelled cause + materiality.
      (d) ≥2 RULE-UNREACHABLE breaks. IBOR/ABOR residuals with NO timing/accrual/cost-basis
          class to explain them — the of-record engine classification lands `unexplained`; the
          oracle carries the TRUE cause (`pricing` / `data_error`) the
          deterministic rules cannot reach.
      (e) The ADMINISTRATOR NAV + a labelled >1 bp shadow-NAV divergence:
          a fund-level admin NAV per fund, one diverging from the internally-derivable NAV
          beyond a 1 bp band. NOT an engine surface (the engine reconciles
          position/cash/transaction/ibor_abor, not NAV) — it is the shadow-NAV oversight input,
          labelled `nav` in the oracle so that capability proves on data.

    Determinism: a dedicated RNG (`RNG_ENR`); the base streams are untouched. Every injected
    difference reconciles to its manifest label by value (the two-way value-reconciliation
    invariant, extended over the enriched feed — including the ibor_abor surface — stays green).

    Returns the six mutated lists (custodian_holdings, custodian_cash, admin_statement,
    break_labels, positions, cash_flows) — positions + cash_flows are mutated in place for the
    A/B-disagreement (IBOR book-vs-mark) and the balance-grade E-06 opening flows.
    """
    # --- index the feed for in-place edits -------------------------------------------------
    cust_by_pos = {row[2]: row for row in custodian_holdings}  # position_id -> custodian row
    ibor_idx_by_pos: dict[str, int] = {}
    for k, row in enumerate(positions):
        if row[1] == "ibor":
            ibor_idx_by_pos[row[0]] = k

    # the next break sequence number (continue the base sequence; preserve BRK-0001..0011)
    brk_seq = len(break_labels)
    cf_seq = len(cash_flows)

    def _next_brk() -> str:
        nonlocal brk_seq
        brk_seq += 1
        return f"BRK-{brk_seq:04d}"

    # the set of position_ids the base pass already broke (do not double-break them)
    already_broken = {
        lbl[3] for lbl in break_labels if lbl[1] == "position"
    }

    def _ibor_mv(pos_id: str) -> Decimal:
        return Decimal(positions[ibor_idx_by_pos[pos_id]][8])

    def _ibor_qty(pos_id: str) -> Decimal | None:
        q = positions[ibor_idx_by_pos[pos_id]][5]
        return Decimal(q) if q else None

    def _set_cust_mv(pos_id: str, mv: Decimal, note: str) -> None:
        cust_by_pos[pos_id][7] = str(mv.quantize(Decimal("0.01")))
        cust_by_pos[pos_id][9] = note

    def _set_cust_qty(pos_id: str, qty: Decimal, note: str) -> None:
        cust_by_pos[pos_id][6] = str(qty)
        cust_by_pos[pos_id][9] = note

    # ============================================================================
    # (c) BREAK-SET EXPANSION — sound (correctly-classified) per-class instances
    # ============================================================================
    # A second SHARED-RATIO fx pair (ratio 0.965, distinct from the base 0.98 pair so the
    # existing fx pins stay stable). The engine sees ≥2 holdings sharing the ratio → fx (CORRECT).
    fx_ratio = Decimal("0.965")
    for pos_id in ("POS-0005", "POS-0007"):
        base = _ibor_mv(pos_id)
        cust_mv = (base * fx_ratio).quantize(Decimal("0.01"))
        delta = base - cust_mv  # custodian translates LOWER (an fx-rate difference)
        _set_cust_mv(pos_id, cust_mv, "fx_break")
        break_labels.append([
            _next_brk(), "position", "fx", pos_id, "custodian",
            str(delta), "", _materiality_band(delta),
            f"custodian USD-translates {pos_id} at a different FX rate ({delta} difference)",
        ])

    # Two PRICING breaks with DISTINCT, idiosyncratic ratios (a single mismarked holding each →
    # unique ratio → pricing, CORRECT). The ratios (1.033 / 1.081) are chosen NOT to collide with
    # any other value break's ratio (the base pricing ratios are 1.04 / 1.07; the fx ratios are
    # 0.98 / 0.965; the adversarial pricing ratios are 1.058 / 0.965) — so the classifier sees a
    # UNIQUE ratio and correctly returns pricing.
    for pos_id, ratio in (("POS-0006", Decimal("1.033")), ("POS-0009", Decimal("1.081"))):
        base = _ibor_mv(pos_id)
        cust_mv = (base * ratio).quantize(Decimal("0.01"))
        delta = cust_mv - base
        _set_cust_mv(pos_id, cust_mv, "price_break")
        break_labels.append([
            _next_brk(), "position", "pricing", pos_id, "custodian",
            str(delta), "", _materiality_band(delta),
            f"custodian marks {pos_id} {delta} above the internal IBOR mark",
        ])

    # Two QUANTITY data_error breaks (custodian share count below the book, NO in-flight trade →
    # data_error, CORRECT).
    for pos_id, qd in (("POS-0025", Decimal("1500")), ("POS-0027", Decimal("900"))):
        base_qty = _ibor_qty(pos_id)
        assert base_qty is not None
        _set_cust_qty(pos_id, base_qty - qd, "qty_break")
        break_labels.append([
            _next_brk(), "position", "data_error", pos_id, "custodian",
            "", str(qd), "medium",
            f"custodian share count for {pos_id} is {qd} units below the internal book",
        ])

    # Two TIMING breaks grounded in spare in-flight E-05 trades (the base divergence pass
    # created ~6 in-flight timing holdings; the base comparator used the first 2 — reuse 2
    # more, so the custodian lags by exactly the in-flight quantity → timing, CORRECT).
    timing_spares: list[tuple[str, Decimal]] = []
    used_timing = {lbl[3] for lbl in break_labels if lbl[2] == "timing"}
    for pos_id in sorted(divergence_index):
        already_noted = pos_id in cust_by_pos and bool(cust_by_pos[pos_id][9])
        if pos_id in used_timing or pos_id in already_broken or already_noted:
            continue
        for rec in divergence_index[pos_id]:
            if rec.get("class") == "timing" and _ibor_qty(pos_id):
                timing_spares.append((pos_id, Decimal(rec["trade_qty"])))
                break
    for pos_id, lag in timing_spares[:2]:
        base_qty = _ibor_qty(pos_id)
        assert base_qty is not None
        _set_cust_qty(pos_id, base_qty - lag, "timing_break")
        break_labels.append([
            _next_brk(), "position", "timing", pos_id, "custodian",
            "", str(lag), "low",
            f"trade booked trade-date internally but settlement-date by the custodian for "
            f"{pos_id} (TD/SD timing; custodian lags {lag} units — the in-flight trade quantity)",
        ])

    # ============================================================================
    # (c) THE THREE ADVERSARIAL fx/pricing SHAPES — pinned KNOWN-MISCLASSIFIED
    # (designed to misclassify under the current ratio-cluster rule; these are
    #  characterised, not corrected — the classifier fix is a later refinement).
    # ============================================================================
    # ADV-1 — SINGLE-HOLDING fx: one fx-translated holding with a UNIQUE ratio. The rule needs
    # ≥2 holdings sharing a ratio to recognise fx, so a lone fx holding is misclassified PRICING.
    adv1 = "POS-0013"
    base = _ibor_mv(adv1)
    cust_mv = (base * Decimal("0.94")).quantize(Decimal("0.01"))
    delta = base - cust_mv
    _set_cust_mv(adv1, cust_mv, "fx_break")
    break_labels.append([
        _next_brk(), "position", "fx", adv1, "custodian",
        str(delta), "", _materiality_band(delta),
        f"custodian USD-translates {adv1} at a different FX rate ({delta} difference) — a "
        f"SINGLE-holding fx break (adversarial: the ratio-cluster rule needs >=2 to recognise fx)",
    ])

    # ADV-2 — COINCIDENTAL SHARED-RATIO PRICING PAIR: two genuinely-idiosyncratic pricing breaks
    # that happen to share an identical ratio. The rule reads a shared ratio as systematic → fx,
    # so both are misclassified FX (true cause pricing).
    adv2_ratio = Decimal("1.058")
    for pos_id in ("POS-0014", "POS-0015"):
        base = _ibor_mv(pos_id)
        cust_mv = (base * adv2_ratio).quantize(Decimal("0.01"))
        delta = cust_mv - base
        _set_cust_mv(pos_id, cust_mv, "price_break")
        break_labels.append([
            _next_brk(), "position", "pricing", pos_id, "custodian",
            str(delta), "", _materiality_band(delta),
            f"custodian marks {pos_id} {delta} above the internal IBOR mark — one of a pricing "
            f"PAIR that coincidentally shares a value ratio (adversarial: the rule reads a shared "
            f"ratio as systematic fx)",
        ])

    # ADV-3 — PRICING RATIO COLLIDES WITH AN fx RATIO: a pricing holding whose ratio equals the
    # (c) shared-ratio fx pair's ratio (0.965). The rule clusters it with the fx pair → fx
    # (true cause pricing).
    adv3 = "POS-0016"
    base = _ibor_mv(adv3)
    cust_mv = (base * fx_ratio).quantize(Decimal("0.01"))  # 0.965 — collides with POS-0005/0007
    delta = base - cust_mv
    _set_cust_mv(adv3, cust_mv, "price_break")
    break_labels.append([
        _next_brk(), "position", "pricing", adv3, "custodian",
        str(delta), "", _materiality_band(delta),
        f"custodian marks {adv3} {delta} away from the internal IBOR mark — a pricing break whose "
        f"value ratio COLLIDES with the fx pair's ratio (adversarial: the rule clusters it as fx)",
    ])

    # ============================================================================
    # (b) THE A/B-DISAGREEMENT CASE (on data) + its paired ibor_abor unexplained residual
    # ============================================================================
    # POS-0019 (value-only): move the IBOR E-04 market_value 6% BELOW the E-07 mark (the mark stays
    # = the ABOR market_value, so the W1 NAV path — which reads ABOR = the mark — is byte-stable;
    # only the IBOR book moves). The custodian then equals the new IBOR book value EXACTLY.
    #
    # This single divergence exercises TWO safety surfaces at once (the honest mechanics of an IBOR-
    # book-vs-mark divergence — they are NOT separable on one holding):
    #   - the POSITION dual-pipeline DISAGREEMENT: Pipeline A (book vs custodian) clears, Pipeline B
    #     (E-07 mark vs custodian) breaks, NO in-flight trade explains the book-vs-mark gap → the
    #     dual-pipeline genuinely disagrees → surfaced position break, pipeline_disagreement=True
    #     (n_pipeline_disagreements > 0 on data — the goal's A/B-disagreement case). The engine's
    #     surfaced position-break amount is custodian − book = 0 (the custodian ties the book; the
    #     divergence is the internal book-vs-mark gap). Labelled position / INTERNAL, value-verified
    #     against the book-vs-mark divergence (NOT a custodian-vs-book difference — no break_note).
    #   - the IBOR/ABOR UNEXPLAINED residual: IBOR market_value now diverges from ABOR market_value
    #     with no timing/accrual/cost-basis class → the engine lands `unexplained` (one of the >=2
    #     rule-unreachable breaks). Labelled ibor_abor / pricing (the true cause the
    #     rules can't get — the same stale-price corruption as the A/B case BRK-0024).
    ab_pos = "POS-0019"
    mark = _ibor_mv(ab_pos)  # == the E-07 current mark (IBOR mv currently equals the mark)
    ab_book = (mark * Decimal("0.94")).quantize(Decimal("0.01"))
    positions[ibor_idx_by_pos[ab_pos]][8] = str(ab_book)
    _set_cust_mv(ab_pos, ab_book, "")  # custodian == the IBOR book value (Pipeline A clears)
    ab_delta = mark - ab_book  # the book-vs-mark divergence magnitude
    break_labels.append([
        _next_brk(), "position", "pricing", ab_pos, "internal",
        str(ab_delta), "", _materiality_band(ab_delta),
        f"the internal IBOR book value and the E-07 mark for {ab_pos} diverge by {ab_delta} while "
        f"the custodian agrees with the book — the dual-independent-pipeline genuinely DISAGREES "
        f"(Pipeline A clears, Pipeline B mark breaks); surfaced as a pipeline-disagreement break",
    ])
    # the paired ibor_abor unexplained residual on the same holding (IBOR book now != ABOR book).
    # TRUE CAUSE `pricing`: this is the SAME single injected stale-price corruption
    # as BRK-0024 (the A/B case) surfacing on a second reconcile surface — one corruption, ONE true
    # cause (`pricing`), coherent with BRK-0024. `pricing` is EQUALLY rule-unreachable on the
    # ibor_abor surface (the classifier reaches only timing/accrual/cost-basis — ibor_abor_reconcile.py
    # :167-204 emits ONLY `unexplained` for any residual), so this still lands `unexplained`
    # of-record (the rule-discovery corpus).
    ab_residual = mark - ab_book  # abor(= mark) − ibor(= ab_book)
    break_labels.append([
        _next_brk(), "ibor_abor", "pricing", f"ibor:{ab_pos}", "internal",
        str(ab_residual), "", _materiality_band(ab_residual),
        f"IBOR vs ABOR market value for {ab_pos} diverges by {ab_residual} with NO timing, accrual "
        f"or cost-basis class to explain it — the of-record engine classification lands "
        f"`unexplained` (true cause `pricing`, the same stale-price corruption as the A/B case "
        f"BRK-0024 on a second surface; the rule-discovery corpus)",
    ])

    # ============================================================================
    # (d) A SECOND RULE-UNREACHABLE break → of-record `unexplained` (a QUANTITY residual)
    # ============================================================================
    # A different `unexplained` shape: an IBOR-vs-ABOR QUANTITY residual with NO in-flight trade to
    # explain it (so the engine cannot classify it `timing`) — on a quantity-bearing holding. We
    # move the IBOR quantity below the ABOR quantity (the ABOR book — NAV-bearing — is untouched;
    # NAV reads ABOR market_value, not quantity, so the W1 path stays byte-stable), and set the
    # custodian quantity = the new IBOR quantity (so NO position break — the custodian ties the IBOR
    # book on both quantity and value). The engine sees an IBOR/ABOR quantity divergence no rule
    # explains → `unexplained`. The oracle carries the true cause (`data_error` — a
    # quantity corruption with no value impact and no rule signal, which the rules cannot reach).
    unx_qty_pos = "POS-0035"  # quantity-bearing, currently unbroken
    # ibor qty == abor qty on an unbroken holding (the divergence pass left this one untouched).
    abor_qty = Decimal(positions[ibor_idx_by_pos[unx_qty_pos]][5])
    qty_resid = Decimal("1850")  # an unexplained quantity residual (no in-flight trade)
    ibor_qty_new = abor_qty - qty_resid
    positions[ibor_idx_by_pos[unx_qty_pos]][5] = str(ibor_qty_new)
    # custodian == the new IBOR qty (so NO position break — the custodian ties the IBOR book).
    _set_cust_qty(unx_qty_pos, ibor_qty_new, "")
    # TRUE CAUSE `data_error`: a quantity divergence with ZERO value impact (IBOR and
    # ABOR market values are identical) and NO in-flight trade cannot coherently be `fees` (a fee
    # taken in units would move value proportionally). It is the goal's own example — "a corruption
    # with no rule signal": a quantity data_error no deterministic rule can reach (the ibor_abor
    # classifier reaches only timing/accrual/cost-basis, and there is no in-flight trade to make it
    # timing — ibor_abor_reconcile.py:167-204 emits ONLY `unexplained`), so it stays `unexplained`
    # of-record.
    break_labels.append([
        _next_brk(), "ibor_abor", "data_error", f"ibor:{unx_qty_pos}", "internal",
        "", str(qty_resid), _materiality_band(Decimal(0)),
        f"IBOR vs ABOR QUANTITY for {unx_qty_pos} diverges by {qty_resid} units with NO value impact "
        f"and NO in-flight trade (so no timing class) and no accrual/cost-basis class — the engine "
        f"lands `unexplained` (true cause `data_error`, a quantity corruption with no rule signal; "
        f"the second rule-unreachable break)",
    ])

    # ============================================================================
    # (c) A SECOND CASH break (now both pipelines run, with balance-grade E-06 below)
    # ============================================================================
    # The base cash break is on the first fund (PF-0001). Add a SECOND on the second fund: its
    # admin balance is custodian + a labelled delta (the actual difference == the label, so the
    # two-way value invariant holds). The base first-fund break and the unbroken third fund are
    # untouched.
    funds_sorted = sorted(fund_total_pf.values())
    cust_cash_by_fund = {row[2]: Decimal(row[4]) for row in custodian_cash}
    admin_cash_rows = {row[2]: row for row in admin_statement if row[1] == "cash"}
    second_fund = funds_sorted[1]
    cash_delta2 = Decimal(RNG_ENR.randint(60_000, 480_000))
    new_admin_bal = cust_cash_by_fund[second_fund] + cash_delta2
    admin_cash_rows[second_fund][5] = str(new_admin_bal)
    admin_cash_rows[second_fund][7] = "cash_break"
    break_labels.append([
        _next_brk(), "cash", "data_error", second_fund, "internal",
        str(cash_delta2), "", _materiality_band(cash_delta2),
        f"administrator cash balance for {second_fund} disagrees with the custodian by "
        f"{cash_delta2} (cash reconciliation break)",
    ])

    # ============================================================================
    # (c) A SECOND MISSING/EXTRA-TRANSACTION break — a further instance of the
    #  missing/extra-transaction class. A SECOND extra administrator transaction the internal book lacks
    #  (the same shape as ADMIN-TXN-EXTRA-01) — the transaction matcher's Pipeline B surfaces it as
    #  a `missing_transaction` break (transaction_match.py:131-146), record_a_ref = the admin ref.
    # ============================================================================
    extra2_amt = Decimal(RNG_ENR.randint(90_000, 420_000))
    extra2_txn_id = "ADMIN-TXN-EXTRA-02"
    admin_statement.append([
        "ADMIN-T-EXTRA-02", "transaction", funds_sorted[1], "", latest_q.isoformat(),
        str(-extra2_amt), "USD", extra2_txn_id,
    ])
    break_labels.append([
        _next_brk(), "transaction", "missing_transaction", extra2_txn_id, "custodian",
        str(extra2_amt), "", _materiality_band(extra2_amt),
        f"administrator records transaction {extra2_txn_id} that is absent from the internal book "
        f"(a second missing/extra-transaction instance — the engine surfaces it via the "
        f"transaction matcher's external-only direction)",
    ])

    # ============================================================================
    # (a) BALANCE-GRADE E-06 — opening-balance flows so the cash Pipeline-B replay is balance-grade
    # ============================================================================
    # The base E-06 seed is illustrative flows, so the replay sum is a small flow-delta, not a
    # balance — Pipeline B abstained (`n_pipeline_b_abstained`). Add ONE opening-balance cash-flow
    # event per fund so the replay (Σ all E-06 flows up to the as-of) reconstructs a figure of the
    # same order/sign as the custodian balance — the `_replay_is_balance_grade` gate (same sign,
    # within an order of magnitude) now PASSES, and Pipeline B runs on data (abstention → 0).
    #
    # The opening balance is set so the FULL replay (opening + Σ the existing flows) equals the
    # custodian cash balance per fund — a true balance ledger: opening + flows = closing(= the
    # custodian balance). So the replay-derived balance reconciles to the custodian EXACTLY (the
    # base cash break is a custodian-vs-ADMIN disagreement; Pipeline B — replay vs custodian —
    # agrees with the custodian, so on the broken fund A breaks and B agrees with custodian → the
    # break is found by BOTH pipelines, as the of-record dual-pipeline cash reconcile).
    existing_flow_sum_by_fund: dict[str, Decimal] = {}
    for cf in cash_flows:
        fund = cf[1]
        prev = existing_flow_sum_by_fund.get(fund, Decimal(0))
        existing_flow_sum_by_fund[fund] = prev + Decimal(cf[7])
    opening_flows: list[list] = []
    for fund in funds_sorted:
        custodian_bal = cust_cash_by_fund.get(fund)
        if custodian_bal is None:
            continue
        existing = existing_flow_sum_by_fund.get(fund, Decimal(0))
        # opening so that opening + existing flows == the custodian balance (closing).
        opening = (custodian_bal - existing).quantize(Decimal("0.01"))
        cf_seq += 1
        # `contribution` (a valid E-06 cash_flow_type) carries the opening capital position — the
        # as-of-window opening balance the replay ledger builds on (opening + flows = closing).
        direction = "inflow" if opening >= 0 else "outflow"
        opening_flows.append([
            f"CF-{cf_seq:05d}", fund, "", "", latest_q.isoformat(),
            "contribution", direction, str(opening), "USD", "custodian_feed",
        ])
    # opening-balance flows go FIRST in the ledger (they are the as-of-window opening position).
    cash_flows = opening_flows + cash_flows

    # ============================================================================
    # (e) THE ADMINISTRATOR NAV + a labelled >1 bp shadow-NAV divergence
    # ============================================================================
    # A fund-level administrator NAV per fund on the admin statement (record_type='nav'). The
    # internally-derivable NAV is Σ the ABOR market values per fund (the NAV-bearing book) at the
    # as-of. The admin NAV equals that on the agreeing funds, and DIVERGES beyond a 1 bp band on
    # ONE fund (the labelled shadow-NAV divergence case). This is the SD-12.16 shadow-NAV
    # oversight input — NOT an engine surface (the engine reconciles
    # position/cash/transaction/ibor_abor, not NAV), so the engine correctly does not surface it.
    # map each sleeve (asset_class_portfolio) to its parent total fund — the ABOR marks live on
    # the sleeve portfolios; the fund-level NAV rolls them up to the total fund.
    sleeve_to_total = {row[0]: row[3] for row in portfolios if row[3]}
    # The internally-derivable NAV is computed under the repo's CANONICAL NAV identity
    # (mart_fund_nav.sql:5) — NAV = Sigma(position market values) + accrued income - fees — so the
    # admin NAV oracle and the W1 NAV-strike path read ONE NAV truth (SSOT).
    # Sigma the ABOR market values AND Sigma the ABOR accrued income, per total fund; fees
    # are STRUCTURALLY ZERO on this seed (no fee/management-charge source is seeded — the same
    # fees = 0 assumption mart_fund_nav.sql:48-53 states), so the fee term is omitted but named.
    # (Sigma ABOR mv ties the E-07 current marks via assert_marts_reconcile_holdings_to_nav, so this
    # equals the canonical mart's gross_market_value + accrued_income.)
    abor_nav_by_fund: dict[str, Decimal] = {}
    for row in positions:
        if row[1] == "abor":
            fund = sleeve_to_total.get(row[2], row[2])
            mv = Decimal(row[8]) if row[8] else Decimal(0)
            accrued = Decimal(row[10]) if len(row) > 10 and row[10] else Decimal(0)
            abor_nav_by_fund[fund] = abor_nav_by_fund.get(fund, Decimal(0)) + mv + accrued
    # the fund the admin NAV diverges on (a different fund from the cash breaks for clarity)
    nav_divergent_fund = funds_sorted[2] if len(funds_sorted) >= 3 else funds_sorted[-1]
    for fund in funds_sorted:
        internal_nav = abor_nav_by_fund.get(fund, Decimal(0)).quantize(Decimal("0.01"))
        if fund == nav_divergent_fund:
            # diverge by ~12 bp (well beyond the 1 bp band) — a labelled shadow-NAV divergence.
            # The divergence is sized off the CANONICAL internal NAV, so the labelled magnitude and
            # the bp figure are TRUE under the canonical identity and remain > 1 bp.
            nav_delta = (internal_nav * Decimal("0.0012")).quantize(Decimal("0.01"))
            admin_nav = internal_nav + nav_delta
            admin_statement.append([
                f"ADMIN-NAV-{fund}", "nav", fund, "", latest_q.isoformat(),
                str(admin_nav), "USD", "nav_break",
            ])
            break_labels.append([
                _next_brk(), "nav", "data_error", fund, "internal",
                str(nav_delta), "", _materiality_band(nav_delta),
                f"the administrator's fund-level NAV for {fund} diverges from the internally-derivable "
                f"NAV (Sigma the ABOR marks + accrued income, the canonical NAV identity) by "
                f"{nav_delta} (~12 bp, beyond the 1 bp band) — a shadow-NAV divergence case (the "
                f"SD-12.16 oversight input; NOT a reconcile surface)",
            ])
        else:
            # a non-divergent fund: admin NAV EQUALS the canonical internal NAV exactly (no
            # accrual offset).
            admin_statement.append([
                f"ADMIN-NAV-{fund}", "nav", fund, "", latest_q.isoformat(),
                str(internal_nav), "USD", "",
            ])

    return (
        custodian_holdings, custodian_cash, admin_statement, break_labels, positions, cash_flows,
    )


def main() -> None:
    print("Generating synthetic BD-09 / NAV-strike seed (synthetic data — see README.md):")

    gen_e09()

    # ----- build the holdings universe first (drives instruments, valuations, etc.)
    # legal entities: a manager, a custodian, the funds' own vehicles, issuers, GPs.
    le_rows: list[list] = [
        ["LE-0001", "Acme Asset Management LLP", "partnership", "5493001KJTIIGC8Y1R12",
         "GB", "", "Acme AM;Acme Asset Mgmt", '{"LEI":"5493001KJTIIGC8Y1R12"}', "active", "2018-01-15"],
        ["LE-0002", "Global Custody Bank NA", "corporation", "7H6GLXDRUGQFU57RNE97",
         "US", "", "GCB;Global Custody", '{"LEI":"7H6GLXDRUGQFU57RNE97"}', "active", "2018-02-01"],
        ["LE-0003", "Treasury of the United States", "government body", "254900HROIFWPRGM1V77",
         "US", "", "US Treasury;UST", "{}", "active", "2018-03-10"],
    ]

    instruments: list[list] = []   # E-02 rows
    positions: list[list] = []     # E-04 rows (ibor + abor)
    valuations: list[list] = []    # E-07 rows (append-only, bi-temporal)
    aliases: list[list] = []       # E-13
    ext_ids: list[list] = []       # E-14
    portfolios: list[list] = []    # E-03

    ins_seq = 0
    le_seq = 3       # issuers/GPs continue after the fixed three above
    pos_seq = 0
    val_seq = 0
    alias_seq = 0
    ext_seq = 0

    # the funds' total-fund + sub-portfolios
    pf_seq = 0
    fund_total_pf: dict[str, str] = {}
    # benchmark ids are referenced but E-10 is out of the ten-entity scope — leave the
    # FK value present (the masters that DO exist resolve; benchmark_id is a soft ref).
    for fund in FUNDS:
        pf_seq += 1
        total_pf = f"PF-{pf_seq:04d}"
        fund_total_pf[fund["fund_id"]] = total_pf
        portfolios.append([
            total_pf, fund["name"], "total_fund", "", "",
            "Long-term real return above the policy benchmark",
            f"BM-{pf_seq:04d}", "USD", fund["manager"], fund["inception"], "active",
        ])

    # holdings per sleeve, with sub-portfolios per asset class within each fund
    holding_universe: list[dict] = []
    for fund in FUNDS:
        total_pf = fund_total_pf[fund["fund_id"]]
        for (ac_key, n, ins_class, method, level, source) in fund["sleeves"]:
            pf_seq += 1
            sleeve_pf = f"PF-{pf_seq:04d}"
            portfolios.append([
                sleeve_pf, f"{fund['name']} — {ASSET_CLASSES[ac_key - 1][2]}",
                "asset_class_portfolio", total_pf, ac_key,
                f"Outperform the {ASSET_CLASSES[ac_key - 1][2]} policy benchmark",
                f"BM-{pf_seq:04d}", "USD", fund["manager"], fund["inception"], "active",
            ])
            for _ in range(n):
                ins_seq += 1
                pos_seq += 1
                ins_id = f"INS-{ins_seq:04d}"
                pos_id = f"POS-{pos_seq:04d}"
                # an issuer LE for equity/debt; GP for fund interests; none for cash
                issuer = ""
                if ins_class in ("listed_equity", "debt"):
                    le_seq += 1
                    issuer = f"LE-{le_seq:04d}"
                    le_rows.append([
                        issuer, f"Issuer {issuer} Corp", "corporation", "", "US", "",
                        "", "{}", "active",
                        f"201{RNG.randint(8, 9)}-0{RNG.randint(1, 9)}-1{RNG.randint(0, 5)}",
                    ])
                elif ins_class == "fund_interest":
                    le_seq += 1
                    issuer = f"LE-{le_seq:04d}"
                    le_rows.append([
                        issuer, f"{ASSET_CLASSES[ac_key - 1][2]} GP {issuer} Ltd",
                        "partnership", "", "KY", "LE-0001", "", "{}", "active",
                        fund["inception"],
                    ])
                isin = f"US{RNG.randint(10**8, 10**9 - 1)}07" if ins_class in ("listed_equity", "debt") else ""
                figi = f"BBG00{RNG.randint(10**5, 10**6 - 1):06d}X" if ins_class == "listed_equity" else ""
                instruments.append([
                    ins_id, f"{ASSET_CLASSES[ac_key - 1][2]} {ins_id}", ins_class, ac_key,
                    issuer, "USD", isin, figi, "{}", "active",
                ])
                # a couple of aliases + external identifiers for the masters
                if ins_class == "fund_interest":
                    alias_seq += 1
                    aliases.append([
                        f"ALIAS-{alias_seq:04d}", "fund", ins_id, f"{ins_id} (short)",
                        "2020-09-30", "administrator_statement", "steward.patel",
                    ])
                    ext_seq += 1
                    ext_ids.append([
                        f"EXTID-{ext_seq:04d}", "fund", ins_id, "InternalScheme",
                        f"PRIV{ins_seq:05d}", "private_cusip", "false",
                    ])
                elif isin:
                    ext_seq += 1
                    ext_ids.append([
                        f"EXTID-{ext_seq:04d}", "instrument", ins_id, "ISIN_registry",
                        isin, "ISIN", "true",
                    ])

                # a base value and a per-quarter drift; private marks get revisions
                base = Decimal(RNG.randint(1_000_000, 8_000_000))
                holding_universe.append({
                    "pos_id": pos_id, "ins_id": ins_id, "sleeve_pf": sleeve_pf,
                    "ins_class": ins_class, "method": method, "level": level,
                    "source": source, "ac_key": ac_key, "base": base,
                    "is_private": method in ("manager_mark", "appraisal", "mark_to_model"),
                })

    # custody + GLEIF ext ids for the fixed LEs
    ext_seq += 1
    ext_ids.append([f"EXTID-{ext_seq:04d}", "legal_entity", "LE-0001", "GLEIF",
                    "5493001KJTIIGC8Y1R12", "LEI", "true"])
    alias_seq += 1
    aliases.append(["ALIAS-%04d" % alias_seq, "legal_entity", "LE-0001", "Acme AM",
                    "2018-01-15", "data_vendor", "steward.jones"])
    # Learned aliases for the no-universal-identifier private masters (the E-13 mechanism the
    # model names: a private portfolio company accumulates the names it has been seen under, and
    # the next resolution cycle matches them automatically). These are the realistic name surfaces
    # the inbound entity-resolution feed resolves against by alias + metadata — NOT the
    # internal LE-NNNN golden key, which never appears on a real inbound feed. Each is a name a
    # steward confirmed maps to the master after a prior unresolved record landed in the queue.
    for _le, _alias, _src in (
        ("LE-0004", "Bolt Rides", "gp_manager_report"),
        ("LE-0004", "Bolt Technologies", "administrator_statement"),
        ("LE-0012", "Helios Renewables", "gp_manager_report"),
        ("LE-0018", "Cardinal Pipeline", "data_vendor"),
        ("LE-0048", "Sterling Foods", "data_vendor"),
        ("LE-0052", "Vanta Strategies", "gp_manager_report"),
    ):
        alias_seq += 1
        aliases.append(["ALIAS-%04d" % alias_seq, "legal_entity", _le, _alias,
                        "2021-06-30", _src, "steward.jones"])

    # ----- valuations (append-only, bi-temporal) + the E-04 positions per quarter
    # E-04 is the holding STATE at the latest as_of_date (one ibor + one abor row per
    # logical holding). E-07 is the full append-only valuation trajectory across the
    # four quarters, with knowledge-time revisions on the private marks.
    latest_q = MONTH_ENDS[-1]
    for h in holding_universe:
        last_val_for_pos: Decimal = h["base"]
        # liquid holdings strike monthly; illiquid (private) strike quarterly
        cadence = MONTH_ENDS if not h["is_private"] else QUARTER_ENDS
        for di, d in enumerate(cadence):
            # a gentle period-on-period drift (compounding-ish trajectory)
            drift = Decimal(1) + Decimal(RNG.randint(-4, 7)) / Decimal(100)
            val = (h["base"] * drift * (Decimal(1) + Decimal(di) / Decimal(50))).quantize(Decimal("0.01"))
            # first-struck mark (knowledge state 1)
            val_seq += 1
            conf = ""
            if h["method"] == "manager_mark":
                conf = f"0.{RNG.randint(75, 88)}"
            elif h["method"] == "mark_to_model":
                conf = f"0.{RNG.randint(60, 74)}"
            valuations.append([
                f"VAL-{val_seq:05d}", h["pos_id"],
                h["ins_id"] if h["ins_class"] in ("fund_interest", "real_asset") else "",
                d.isoformat(), str(val), h["method"], h["level"], h["source"],
                conf, first_recorded(d).isoformat(),
            ])
            last_val_for_pos = val
            # a knowledge-time REVISION for a subset of private marks (restatement):
            # same (position_id, valuation_date), later recorded_at, revised value.
            # The two most-recent illiquid marks get restated (a late manager NAV).
            if h["is_private"] and di >= len(cadence) - 2:
                val_seq += 1
                revised = (val * (Decimal(1) + Decimal(RNG.randint(2, 9)) / Decimal(100))).quantize(Decimal("0.01"))
                rconf = f"0.{RNG.randint(85, 95)}" if conf else ""
                valuations.append([
                    f"VAL-{val_seq:05d}", h["pos_id"],
                    h["ins_id"] if h["ins_class"] in ("fund_interest", "real_asset") else "",
                    d.isoformat(), str(revised), h["method"], h["level"], h["source"],
                    rconf, revised_recorded(d).isoformat(),
                ])
                last_val_for_pos = revised

        # the E-04 state rows (ibor + abor) at the latest quarter-end.
        #
        # ABOR IS THE NAV-BEARING ACCOUNTING TRUTH. The abor row's market_value IS the
        # mark (the same E-07 Valuation feeds the market_value_usd of both books — per
        # E-07:28 the mark applies to the logical holding; the marts/NAV invariant tie
        # the abor market_value to the mark). The abor book is built here, internally
        # consistent and UNCHANGED from the prior seed, so the W1 NAV-strike path is
        # untouched (NAV = Σ marks + abor accruals − fees is byte-stable).
        #
        # IBOR DIVERGES FROM ABOR — but the divergence is applied in a SEPARATE,
        # deterministic post-pass (`_apply_ibor_divergence`, run after this loop on its
        # own RNG) so it does NOT perturb the existing RNG stream that produced the
        # valuations / risk / performance. Here both rows start identical (the ibor row
        # is the divergence pass's input); the post-pass rewrites the ibor row in place
        # and records what diverged + why (the characterised IBOR/ABOR reconciliation
        # ground truth SD-12.10 finds).
        qty = str(Decimal(RNG.randint(1000, 50000))) if h["ins_class"] in ("listed_equity", "debt", "cash") else ""
        commitment = str((h["base"] * Decimal("1.5")).quantize(Decimal("0.01"))) if h["ins_class"] == "fund_interest" else ""
        cost = str((h["base"] * Decimal("0.9")).quantize(Decimal("0.01")))
        mv = str(last_val_for_pos)
        accr = str(Decimal(RNG.randint(0, 25000))) if h["ins_class"] == "debt" else ""
        # consume the same draw the prior seed consumed, to hold the RNG stream stable
        # for every value generated AFTER this point (the existing seed is byte-stable).
        RNG.randint(0, 3)
        # ibor starts identical to abor; the post-pass diverges it (and sets ibor accr = 0).
        ibor_idx = len(positions)
        positions.append([h["pos_id"], "ibor", h["sleeve_pf"], h["ins_id"],
                          latest_q.isoformat(), qty, commitment, cost, mv, "USD", ""])
        positions.append([h["pos_id"], "abor", h["sleeve_pf"], h["ins_id"],
                          latest_q.isoformat(), qty, commitment, cost, mv, "USD", accr])
        # record the holding + its ibor-row index for the divergence + transaction passes
        h["ibor_row_idx"] = ibor_idx
        h["abor_qty"] = qty
        h["abor_commitment"] = commitment
        h["abor_cost"] = cost
        h["abor_mv"] = mv
        h["abor_accr"] = accr

    # ----- IBOR/ABOR divergence (item 1) + E-05 transactions + E-06 cash flows +
    # the external comparator feed + the labelled-break oracle. All driven off a
    # DEDICATED RNG so the existing valuation/risk/performance values stay byte-stable.
    divergence_index = _apply_ibor_divergence(holding_universe, positions, latest_q)
    transactions, cash_flows = _gen_transactions_and_cash_flows(
        holding_universe, fund_total_pf, divergence_index, latest_q
    )
    custodian_holdings, custodian_cash, admin_statement, break_labels = _gen_comparator_feed(
        holding_universe, positions, transactions, cash_flows, divergence_index,
        fund_total_pf, latest_q
    )
    # enrichment — SUPPLEMENT the base feed (the eleven byte-stable breaks are
    # preserved) so the safety machinery is exercised ON DATA: balance-grade E-06, a genuine
    # A/B-disagreement case, break-set expansion (N=29) incl. the three adversarial fx/pricing
    # shapes, >=2 rule-unreachable `unexplained` breaks, the admin NAV + a labelled shadow-NAV
    # divergence. Mutates positions + cash_flows in place (the IBOR book-vs-mark divergence + the
    # opening-balance ledger), so it runs BEFORE the seeds are written.
    (
        custodian_holdings, custodian_cash, admin_statement, break_labels, positions, cash_flows,
    ) = _enrich_comparator_feed(
        custodian_holdings, custodian_cash, admin_statement, break_labels, positions,
        transactions, cash_flows, divergence_index, fund_total_pf, portfolios, latest_q
    )

    # ----- risk measurements (~10/quarter) — append-only, bi-temporal
    risk_rows: list[list] = []
    risk_seq = 0
    risk_specs = [
        ("market", "total_fund", "var", "historical_simulation", "MDL-VAR-01"),
        ("market", "portfolio", "var", "parametric", "MDL-VAR-01"),
        ("market", "portfolio", "expected_shortfall", "historical_simulation", "MDL-VAR-01"),
        ("credit", "counterparty", "exposure", "full_revaluation", "MDL-CCR-02"),
        ("counterparty", "counterparty", "exposure", "full_revaluation", "MDL-CCR-02"),
        ("stress", "portfolio", "stress_loss", "scenario_application", "MDL-STRESS-03"),
        ("liquidity", "holding", "liquidity_tier_classification", "factor_model", "MDL-LIQ-04"),
        ("concentration", "portfolio", "concentration", "factor_model", "MDL-CONC-05"),
        ("scenario", "total_fund", "stress_loss", "scenario_application", "MDL-STRESS-03"),
        ("climate", "portfolio", "exposure", "factor_model", "MDL-CLIM-06"),
    ]
    fund_pfs = list(fund_total_pf.values())
    sleeve_pfs = [r[0] for r in portfolios if r[2] == "asset_class_portfolio"]
    sample_pos = [h["pos_id"] for h in holding_universe[:6]]
    # Risk is struck MONTHLY (institutional risk dashboards strike monthly VaR /
    # exposure / liquidity), per fund — so E-19 carries a realistic monthly risk
    # trajectory across the 24-month window, with quarterly model-recalibration
    # restatements (the bi-temporal case).
    for q in MONTH_ENDS:
        for (rtype, stype, mtype, method, mdl) in risk_specs:
            risk_seq += 1
            if stype == "total_fund":
                subj = fund_pfs[risk_seq % len(fund_pfs)]
            elif stype == "portfolio":
                subj = sleeve_pfs[risk_seq % len(sleeve_pfs)]
            elif stype == "counterparty":
                subj = "LE-0002"
            else:
                subj = sample_pos[risk_seq % len(sample_pos)]
            if mtype == "liquidity_tier_classification":
                value = str(RNG.randint(1, 4))
                ccy = ""
            else:
                value = str(Decimal(RNG.randint(500_000, 60_000_000)))
                ccy = "USD"
            scen = "SCN-0001" if rtype in ("stress", "scenario") else ""
            conf = f"0.{RNG.randint(75, 92)}" if mtype in ("var", "expected_shortfall") else ""
            risk_rows.append([
                f"RISK-{risk_seq:05d}", rtype, stype, subj, mtype, q.isoformat(),
                value, ccy, method, scen, mdl, conf, first_recorded(q).isoformat(),
            ])
            # a knowledge-time revision for the VaR figures at quarter-ends (a
            # model recalibration restatement — the bi-temporal case for E-19)
            if mtype == "var" and q.month in (3, 6, 9, 12):
                risk_seq += 1
                rvalue = str(Decimal(int(Decimal(value) * Decimal("1.04"))))
                risk_rows.append([
                    f"RISK-{risk_seq:05d}", rtype, stype, subj, mtype, q.isoformat(),
                    rvalue, ccy, method, scen, mdl, f"0.{RNG.randint(88, 95)}",
                    revised_recorded(q).isoformat(),
                ])

    # ----- performance results (quarterly windows) — append-only, bi-temporal
    perf_rows: list[list] = []
    perf_seq = 0
    perf_subjects = [(pf, "portfolio") for pf in fund_pfs] + [(pf, "total_fund") for pf in fund_pfs]
    # remember the (subj, period_start, period_end) of the latest-quarter net TWR for
    # the first fund, so the restatement below matches its logical key exactly.
    restate_target: tuple[str, str, str] | None = None
    for q in QUARTER_ENDS:
        # the calendar quarter the window covers (period_start = first day of quarter)
        ps = dt.date(q.year, ((q.month - 1) // 3) * 3 + 1, 1)
        for (subj, stype) in perf_subjects[:3]:
            for basis in ("gross", "net"):
                perf_seq += 1
                rv = f"0.0{RNG.randint(200, 750):03d}"[:6]
                perf_rows.append([
                    f"PERF-{perf_seq:05d}", stype, subj, ps.isoformat(), q.isoformat(),
                    basis, "time_weighted", rv, "USD", "MDEF-TWR-01", "", "abor",
                    "", first_recorded(q).isoformat(),
                ])
                if q == latest_q and subj == perf_subjects[0][0] and basis == "net":
                    restate_target = (subj, ps.isoformat(), q.isoformat())
    # a since-inception MWR per fund
    for fund in FUNDS:
        perf_seq += 1
        perf_rows.append([
            f"PERF-{perf_seq:05d}", "total_fund", fund_total_pf[fund["fund_id"]],
            fund["inception"], latest_q.isoformat(), "net", "since_inception",
            f"0.1{RNG.randint(200, 850):03d}"[:6], "USD", "MDEF-MWR-03", "", "abor",
            f"0.{RNG.randint(75, 85)}", first_recorded(latest_q).isoformat(),
        ])
    # one performance RESTATEMENT (a revised net TWR for the latest quarter — a late
    # valuation arrived, so the return was recomputed). Same logical key as the
    # original net TWR row (subject, basis=net, method=time_weighted, period), later
    # recorded_at, revised return_value — the bi-temporal case for E-20.
    assert restate_target is not None
    rsubj, rps, rpe = restate_target
    perf_seq += 1
    perf_rows.append([
        f"PERF-{perf_seq:05d}", "portfolio", rsubj, rps, rpe, "net", "time_weighted",
        "0.0455", "USD", "MDEF-TWR-01", "", "abor", "", revised_recorded(latest_q).isoformat(),
    ])

    # ---- write everything --------------------------------------------------
    w("raw_e01_legal_entity.csv",
      ["entity_id", "entity_name", "entity_type", "lei", "domicile", "parent_entity_id",
       "known_aliases", "external_ids", "status", "first_seen_at"], le_rows)
    w("raw_e02_instrument_asset.csv",
      ["instrument_id", "instrument_name", "instrument_class", "asset_class",
       "issuer_entity_id", "currency", "isin", "figi", "external_ids", "status"], instruments)
    w("raw_e03_portfolio_mandate.csv",
      ["portfolio_id", "portfolio_name", "portfolio_type", "parent_portfolio_id",
       "asset_class", "mandate_objective", "benchmark_id", "base_currency",
       "managed_by_entity_id", "inception_date", "status"], portfolios)
    w("raw_e04_holding_position.csv",
      ["position_id", "book", "portfolio_id", "instrument_id", "as_of_date", "quantity",
       "commitment_usd", "cost_basis_usd", "market_value_usd", "currency",
       "accrued_income_usd"], positions)
    w("raw_e07_valuation.csv",
      ["valuation_id", "position_id", "instrument_id", "valuation_date", "value_usd",
       "method", "valuation_level", "source", "confidence_score", "recorded_at"], valuations)
    w("raw_e13_entity_alias.csv",
      ["alias_id", "subject_type", "subject_id", "alias_name", "first_seen_at",
       "source", "confirmed_by"], aliases)
    w("raw_e14_external_identifier.csv",
      ["external_id_record", "subject_type", "subject_id", "external_system",
       "external_id", "id_type", "verified"], ext_ids)
    w("raw_e19_risk_measurement.csv",
      ["measurement_id", "risk_type", "subject_type", "subject_id", "measure_type",
       "as_of_date", "value", "currency", "method", "scenario_id", "model_id",
       "confidence_score", "recorded_at"], risk_rows)
    w("raw_e20_performance_result.csv",
      ["performance_result_id", "subject_type", "subject_id", "period_start", "period_end",
       "return_basis", "return_method", "return_value", "currency", "metric_definition_id",
       "composite_id", "valuation_source", "confidence_score", "recorded_at"], perf_rows)

    # ---- the W2 reconciliation substrate (E-05/E-06 + the comparator feed + oracle) ----
    w("raw_e05_transaction.csv",
      ["transaction_id", "transaction_type", "portfolio_id", "instrument_id", "trade_date",
       "settlement_date", "quantity", "amount_usd", "counterparty_entity_id", "status",
       "source"], transactions)
    w("raw_e06_cash_flow_event.csv",
      ["cash_flow_id", "portfolio_id", "instrument_id", "transaction_id", "cash_flow_date",
       "cash_flow_type", "direction", "amount", "currency", "source"], cash_flows)
    # the external comparator feed — the custodian + administrator records the firm
    # reconciles its internal book against. SYNTHETIC: derived from the internal book so
    # the majority of rows agree, with deliberately-injected labelled breaks (see the
    # labels manifest). These are NOT canonical OpenIM entities — they are an external
    # feed, so they carry no stg_eNN_* staging model and are out of the schema-drift scope.
    w("raw_custodian_holdings.csv",
      ["custodian_record_id", "custodian", "position_id", "portfolio_id", "instrument_id",
       "as_of_date", "quantity", "market_value_usd", "currency", "break_note"],
      custodian_holdings)
    w("raw_custodian_cash.csv",
      ["custodian_cash_id", "custodian", "portfolio_id", "as_of_date", "balance_usd",
       "currency"], custodian_cash)
    w("raw_admin_statement.csv",
      ["admin_record_id", "record_type", "portfolio_id", "instrument_id", "as_of_date",
       "amount_usd", "currency", "ref"], admin_statement)
    # the labels manifest — the zero-missed-breaks ORACLE. Emitted as BOTH CSV (analyst /
    # dbt-readable) and JSON (the reconciliation engine / eval read either). The columns
    # are E-24 Reconciliation Break's vocabulary (reconciliation_type / cause_classification
    # / materiality), so the eval scores the engine's E-24 output against this directly.
    break_header = [
        "break_id", "reconciliation_type", "cause_classification", "record_ref",
        "expected_side", "difference_amount", "difference_qty", "materiality",
        "description",
    ]
    w("break_labels.csv", break_header, break_labels)
    _write_break_labels_json(break_header, break_labels)

    total = (len(le_rows) + len(instruments) + len(portfolios) + len(positions)
             + len(valuations) + len(aliases) + len(ext_ids) + len(risk_rows)
             + len(perf_rows) + len(ASSET_CLASSES))
    print(f"  TOTAL across the ten core entities: {total} rows")
    print(f"  W2 substrate: {len(transactions)} transactions (E-05), "
          f"{len(cash_flows)} cash flows (E-06)")
    print(f"  comparator feed: {len(custodian_holdings)} custodian holdings, "
          f"{len(custodian_cash)} custodian cash, {len(admin_statement)} admin lines")
    print(f"  labelled-break oracle: {len(break_labels)} breaks")


if __name__ == "__main__":
    main()
