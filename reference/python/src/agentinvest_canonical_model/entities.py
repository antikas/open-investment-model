"""The ten canonical-model entity schemas (E-01 ... E-20).

Each schema is a faithful realisation of its OpenIM model file's **Attribute
schema** table — same column names, the model's declared types, the declared
nullability, the key, and the ownership/partition shape. The model files are the
single source of truth; the schema-drift check (``drift.py``) parses each model
file's attribute table and fails the build on any drift (a missing, renamed or
retyped column). Walk each schema against ``model/entities/core/E-NN-*.md``.

Type mapping (model-file type -> Python/Pydantic):

- ``varchar`` / ``char`` -> ``str``
- ``decimal``            -> ``Decimal``   (exact money/quantity; never float)
- ``float``              -> ``float``     (only the confidence scores are float)
- ``int``                -> ``int``
- ``date``               -> ``datetime.date``
- ``boolean``            -> ``bool``
- ``array``              -> ``list[str]``
- ``map``                -> ``dict[str, str]``

Nullability: a column the model file declares as "null at the top" / "where one
exists" / "where applicable" / "null otherwise" is ``Optional`` (``| None``);
every other column is required. The primary key and partition key are always
required.

The append-only / as-of entities (E-07, E-19, E-20) carry their bi-temporal
grain columns (``GRAIN``); the materialisation strategy lives in the dbt layer (the
bi-temporal intermediate models), not in these schemas.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import ClassVar

from pydantic import Field

from agentinvest_canonical_model.base import CanonicalEntity, OwnershipPattern

# ---------------------------------------------------------------------------
# E-01 Legal Entity — the universal party master. Single owner (SD-13.2).
# ---------------------------------------------------------------------------


class E01LegalEntity(CanonicalEntity):
    """E-01 Legal Entity — ``model/entities/core/E-01-legal-entity.md``.

    The universal party master: every organisation (the investor, issuers,
    counterparties, managers, custodians, portfolio companies) is one record,
    distinguished by the role it plays. Golden-keyed on ``entity_id``.
    """

    entity_id: str = Field(description="Golden key. OpenIM-assigned canonical identifier.")
    entity_name: str = Field(description="Canonical legal name.")
    entity_type: str = Field(
        description="corporation / partnership / fund / government body / trust ..."
    )
    lei: str | None = Field(default=None, description="Legal Entity Identifier, where one exists.")
    domicile: str | None = Field(default=None, description="Primary jurisdiction.")
    parent_entity_id: str | None = Field(
        default=None,
        description="FK -> self. Parent in a corporate group; null at the top.",
    )
    known_aliases: list[str] = Field(
        default_factory=list,
        description="Denormalised read-cache view of E-13 Entity Alias.",
    )
    external_ids: dict[str, str] = Field(
        default_factory=dict,
        description="Denormalised read-cache view of E-14 External Identifier.",
    )
    status: str = Field(description="active / inactive / merged / dissolved.")
    first_seen_at: date = Field(description="When the investor first encountered this entity.")

    ENTITY_ID: ClassVar[str] = "E-01"
    MODEL_FILE: ClassVar[str] = "model/entities/core/E-01-legal-entity.md"
    OWNERSHIP: ClassVar[OwnershipPattern] = OwnershipPattern.SINGLE
    PARTITION_KEY: ClassVar[str | None] = None
    GRAIN: ClassVar[tuple[str, ...]] = ()


# ---------------------------------------------------------------------------
# E-02 Instrument / Asset — the holdable-thing master. Single owner (SD-13.1).
# ---------------------------------------------------------------------------


class E02InstrumentAsset(CanonicalEntity):
    """E-02 Instrument / Asset — ``model/entities/core/E-02-instrument-asset.md``.

    The universal "thing an investor can hold," asset-class-subtyped. Golden-keyed
    on ``instrument_id``; the specialisation packs carry the per-class depth.
    """

    instrument_id: str = Field(description="Golden key. OpenIM-assigned canonical identifier.")
    instrument_name: str = Field(description="Canonical name.")
    instrument_class: str = Field(
        description="listed_equity / debt / listed_derivative / otc_derivative / "
        "fund_interest / loan / real_asset / cash / structured_product."
    )
    asset_class: int = Field(
        description="FK -> E-09 (asset_class_key int surrogate). The asset class."
    )
    issuer_entity_id: str | None = Field(
        default=None,
        description="FK -> E-01. Issuing legal entity; null where the instrument has no issuer.",
    )
    currency: str = Field(description="Denomination / trading currency.")
    isin: str | None = Field(default=None, description="ISIN, where one exists.")
    figi: str | None = Field(
        default=None, description="FIGI / OpenFIGI identifier, where one exists."
    )
    external_ids: dict[str, str] = Field(
        default_factory=dict,
        description="Denormalised read-cache view of E-14 (CUSIP, SEDOL, vendor IDs).",
    )
    status: str = Field(description="active / matured / redeemed / delisted.")

    ENTITY_ID: ClassVar[str] = "E-02"
    MODEL_FILE: ClassVar[str] = "model/entities/core/E-02-instrument-asset.md"
    OWNERSHIP: ClassVar[OwnershipPattern] = OwnershipPattern.SINGLE
    PARTITION_KEY: ClassVar[str | None] = None
    GRAIN: ClassVar[tuple[str, ...]] = ()


# ---------------------------------------------------------------------------
# E-03 Portfolio / Mandate — the container. Faceted (SD-05.2 + SD-01.2).
# ---------------------------------------------------------------------------


class E03PortfolioMandate(CanonicalEntity):
    """E-03 Portfolio / Mandate — ``model/entities/core/E-03-portfolio-mandate.md``.

    The capital container governed by a mandate. Faceted ownership: the portfolio
    facet (SD-05.2) and the mandate facet (SD-01.2) live on one record. Golden-keyed
    on ``portfolio_id``.
    """

    portfolio_id: str = Field(
        description="Golden key. OpenIM-assigned identifier for the portfolio."
    )
    portfolio_name: str = Field(description="Canonical name.")
    portfolio_type: str = Field(
        description="total_fund / asset_class_portfolio / mandate / sleeve / sma / account."
    )
    parent_portfolio_id: str | None = Field(
        default=None,
        description="FK -> self. Parent in a portfolio hierarchy; null at the top.",
    )
    asset_class: int | None = Field(
        default=None,
        description="FK -> E-09 (asset_class_key int surrogate). Asset class for an "
        "asset-class portfolio; null for the total fund.",
    )
    mandate_objective: str = Field(
        description="The portfolio's investment objective (mandate facet)."
    )
    benchmark_id: str | None = Field(
        default=None,
        description="FK -> E-10. The benchmark the portfolio is measured against.",
    )
    base_currency: str = Field(description="The portfolio's reporting currency.")
    managed_by_entity_id: str | None = Field(
        default=None,
        description="FK -> E-01 (manager role). Internal, or an external manager "
        "for an SMA/mandate.",
    )
    inception_date: date = Field(description="When the portfolio was established.")
    status: str = Field(description="active / closed / in_transition.")

    ENTITY_ID: ClassVar[str] = "E-03"
    MODEL_FILE: ClassVar[str] = "model/entities/core/E-03-portfolio-mandate.md"
    OWNERSHIP: ClassVar[OwnershipPattern] = OwnershipPattern.FACETED
    PARTITION_KEY: ClassVar[str | None] = None
    GRAIN: ClassVar[tuple[str, ...]] = ()


# ---------------------------------------------------------------------------
# E-04 Holding / Position — key-partitioned by `book` (ADR-0022).
# ---------------------------------------------------------------------------


class E04HoldingPosition(CanonicalEntity):
    """E-04 Holding / Position — ``model/entities/core/E-04-holding-position.md``.

    What the investor owns, at two books of record. **Key-partitioned by ``book``**:
    SD-12.1 IBOR owns ``book = ibor``, SD-12.2 ABOR owns ``book = abor``,
    co-equally; ``book`` is part of identity. The identity is the composite
    ``(position_id, book)`` (enforced by ``assert_e04_position_book_unique.sql``);
    ``position_id`` is the within-book id and the logical-holding handle shared
    across both books, ``book`` the partition key. The model frames the holding as
    the *state* a transaction leaves behind (with ``as_of_date``), not an
    append-only history — so it carries an as-of date but is NOT one of the
    append-only/computed-metric entities.
    """

    position_id: str = Field(
        description="Part of the composite PK (position_id, book); the logical-holding "
        "identity shared across both books."
    )
    book: str = Field(
        description="ibor or abor — the book of record (partition key, part of identity)."
    )
    portfolio_id: str = Field(description="FK -> E-03. The portfolio the position sits in.")
    instrument_id: str = Field(description="FK -> E-02. The instrument or asset held.")
    as_of_date: date = Field(description="The date the position is as of.")
    quantity: Decimal | None = Field(
        default=None,
        description="Units held, where the instrument is quantity-denominated.",
    )
    commitment_usd: Decimal | None = Field(
        default=None,
        description="Committed amount, where the instrument is a fund interest "
        "with an undrawn commitment.",
    )
    cost_basis_usd: Decimal | None = Field(
        default=None, description="The cost basis of the position."
    )
    market_value_usd: Decimal | None = Field(
        default=None,
        description="Current value of the position (from the latest E-07 Valuation).",
    )
    currency: str = Field(description="The position's currency.")
    accrued_income_usd: Decimal | None = Field(
        default=None,
        description="Accrued but unpaid income (coupon, dividend) on the ABOR book.",
    )

    ENTITY_ID: ClassVar[str] = "E-04"
    MODEL_FILE: ClassVar[str] = "model/entities/core/E-04-holding-position.md"
    OWNERSHIP: ClassVar[OwnershipPattern] = OwnershipPattern.KEY_PARTITIONED
    PARTITION_KEY: ClassVar[str | None] = "book"
    GRAIN: ClassVar[tuple[str, ...]] = ()


# ---------------------------------------------------------------------------
# E-07 Valuation — as-of / APPEND-ONLY; key-partitioned by `method`.
# ---------------------------------------------------------------------------


class E07Valuation(CanonicalEntity):
    """E-07 Valuation — ``model/entities/core/E-07-valuation.md``.

    A point-in-time value of a holding, with how it was arrived at. **Append-only**
    (the set of valuations for a holding is its value trajectory; a restatement is a
    new row). Bi-temporal grain: ``valuation_date`` is the as-of axis (see ``GRAIN``).
    The ownership map key-partitions on ``method`` using the same attribute-schema
    enum the column carries (``observable_price`` / ``mark_to_model`` /
    ``manager_mark`` / ``appraisal`` / ``amortised_cost``); the prior ownership-map
    vs attribute-schema vocabulary divergence is now reconciled in the model (the
    ownership map adopted the enum vocabulary; the column itself is unchanged).
    """

    valuation_id: str = Field(description="Primary key.")
    position_id: str = Field(description="FK -> E-04. The holding being valued.")
    instrument_id: str | None = Field(
        default=None,
        description="FK -> E-02, where the valuation is at instrument rather than position grain.",
    )
    valuation_date: date = Field(
        description="The date the valuation is as of (append-only as-of axis)."
    )
    value_usd: Decimal = Field(description="The valuation.")
    method: str = Field(
        description="observable_price / mark_to_model / manager_mark / appraisal / amortised_cost."
    )
    valuation_level: str = Field(
        description="Fair-value hierarchy level — level_1 / level_2 / level_3."
    )
    source: str = Field(
        description="Pricing feed / internal model / manager report / administrator / appraiser."
    )
    confidence_score: float | None = Field(
        default=None,
        description="Confidence score, where the value was modelled or extracted "
        "rather than observed.",
    )

    ENTITY_ID: ClassVar[str] = "E-07"
    MODEL_FILE: ClassVar[str] = "model/entities/core/E-07-valuation.md"
    OWNERSHIP: ClassVar[OwnershipPattern] = OwnershipPattern.KEY_PARTITIONED
    # E-07 is key-partitioned by `method`. The ownership map and the attribute
    # schema now share one vocabulary (the enum: observable_price / mark_to_model /
    # manager_mark / appraisal / amortised_cost) — the prior divergence is
    # reconciled in the model. The column realised is the schema's enum.
    PARTITION_KEY: ClassVar[str | None] = "method"
    # Append-only / as-of: the valid-time axis the bi-temporal materialisation
    # keys on. Materialised in the canonical-data layer as an incremental,
    # two-axis append-only log (valid-time here + knowledge-time provenance).
    GRAIN: ClassVar[tuple[str, ...]] = ("valuation_date",)


# ---------------------------------------------------------------------------
# E-09 Asset Class — effective-dated reference taxonomy. Single owner (SD-13.4).
# ---------------------------------------------------------------------------


class E09AssetClass(CanonicalEntity):
    """E-09 Asset Class — ``model/entities/core/E-09-asset-class.md``.

    The controlled asset-class -> strategy -> sub-strategy taxonomy. Effective-dated
    reference data (``effective_from`` / ``effective_to``), integer-keyed.
    """

    asset_class_key: int = Field(description="Primary key.")
    asset_class_code: str = Field(description="The asset-class code.")
    asset_class_label: str = Field(description="The display label.")
    strategy_code: str | None = Field(
        default=None, description="The strategy within the asset class."
    )
    sub_strategy_code: str | None = Field(
        default=None, description="The sub-strategy, where applicable."
    )
    markets: str = Field(
        description="public / private / both — the class's dominant market structure."
    )
    effective_from: date = Field(description="When this taxonomy entry became valid.")
    effective_to: date | None = Field(
        default=None, description="When it was retired; null while active."
    )

    ENTITY_ID: ClassVar[str] = "E-09"
    MODEL_FILE: ClassVar[str] = "model/entities/core/E-09-asset-class.md"
    OWNERSHIP: ClassVar[OwnershipPattern] = OwnershipPattern.SINGLE
    PARTITION_KEY: ClassVar[str | None] = None
    GRAIN: ClassVar[tuple[str, ...]] = ()


# ---------------------------------------------------------------------------
# E-13 Entity Alias — APPEND-ONLY; key-partitioned by master kind.
# ---------------------------------------------------------------------------


class E13EntityAlias(CanonicalEntity):
    """E-13 Entity Alias — ``model/entities/core/E-13-entity-alias.md``.

    A name a master record has been seen under. **Append-only** (an alias, once
    learned, is kept). Key-partitioned by the master kind it attaches to
    (``subject_type``). Canonical for aliases; the masters' ``known_aliases`` arrays
    are a denormalised read-cache (the model's denormalisation principle —
    ``model/ownership-map.md``).
    """

    alias_id: str = Field(description="Primary key.")
    subject_type: str = Field(
        description="legal_entity (E-01) / instrument (E-02) / fund (PM-01) / "
        "portfolio_company (PM-04)."
    )
    subject_id: str = Field(description="The golden key of the master record.")
    alias_name: str = Field(description="The name the record was seen under.")
    first_seen_at: date = Field(description="When this alias was first encountered.")
    source: str = Field(
        description="Manager report / administrator statement / data vendor / market-data feed."
    )
    confirmed_by: str | None = Field(
        default=None,
        description="The data steward who confirmed the alias maps to this record.",
    )

    ENTITY_ID: ClassVar[str] = "E-13"
    MODEL_FILE: ClassVar[str] = "model/entities/core/E-13-entity-alias.md"
    OWNERSHIP: ClassVar[OwnershipPattern] = OwnershipPattern.KEY_PARTITIONED
    # Key-partitioned by "master kind" — realised on the `subject_type` column the
    # attribute schema carries (the discriminator the model file names).
    PARTITION_KEY: ClassVar[str | None] = "subject_type"
    GRAIN: ClassVar[tuple[str, ...]] = ("first_seen_at",)


# ---------------------------------------------------------------------------
# E-14 External Identifier — key-partitioned by master kind.
# ---------------------------------------------------------------------------


class E14ExternalIdentifier(CanonicalEntity):
    """E-14 External Identifier — ``model/entities/core/E-14-external-identifier.md``.

    A cross-reference from a master's golden key to an identifier in an external
    system. Key-partitioned by the master kind it attaches to (``subject_type``).
    Canonical for external identifiers; the masters' ``external_ids`` maps are a
    denormalised read-cache (the model's denormalisation principle —
    ``model/ownership-map.md``).
    """

    external_id_record: str = Field(description="Primary key.")
    subject_type: str = Field(
        description="legal_entity (E-01) / instrument (E-02) / fund (PM-01) / "
        "portfolio_company (PM-04)."
    )
    subject_id: str = Field(description="The golden key of the master record.")
    external_system: str = Field(
        description="The system, vendor or scheme the identifier belongs to."
    )
    external_id: str = Field(description="The identifier value in that system.")
    id_type: str = Field(
        description="LEI / ISIN / CUSIP / SEDOL / FIGI / private_cusip / "
        "registry no / filing ID / vendor ID."
    )
    verified: bool = Field(
        description="Whether the mapping has been verified, or is a candidate match."
    )

    ENTITY_ID: ClassVar[str] = "E-14"
    MODEL_FILE: ClassVar[str] = "model/entities/core/E-14-external-identifier.md"
    OWNERSHIP: ClassVar[OwnershipPattern] = OwnershipPattern.KEY_PARTITIONED
    PARTITION_KEY: ClassVar[str | None] = "subject_type"
    GRAIN: ClassVar[tuple[str, ...]] = ()


# ---------------------------------------------------------------------------
# E-19 Risk Measurement — as-of / APPEND-ONLY; key-partitioned by risk_type.
# ---------------------------------------------------------------------------


class E19RiskMeasurement(CanonicalEntity):
    """E-19 Risk Measurement — ``model/entities/core/E-19-risk-measurement.md``.

    A point-in-time risk result with its method and provenance. **Append-only**
    (the risk analogue of E-07; a re-run is a new row). Bi-temporal grain:
    ``as_of_date`` is the as-of axis (see ``GRAIN``). Key-partitioned by
    ``risk_type`` (market / credit / counterparty / liquidity / concentration /
    scenario / stress / climate) — the risk *domain*, which determines the single
    producing capability. ``measure_type`` (the *kind of number* — var /
    expected_shortfall / sensitivity / exposure / …) is the orthogonal axis and
    is kept alongside: a measure_type can appear under more than one risk_type and
    a risk_type carries several measure_types, so neither subsumes the other. Both
    columns are realised here, faithful to the model file's attribute schema.
    """

    measurement_id: str = Field(description="Primary key — the surrogate row identity.")
    risk_type: str = Field(
        description="The risk domain (the partition key) — market / credit / "
        "counterparty / liquidity / concentration / scenario / stress / climate. "
        "Determines the single authoritative producing capability."
    )
    subject_type: str = Field(
        description="total_fund / portfolio (E-03) / holding (E-04) / "
        "counterparty (E-01) / asset_class (E-09)."
    )
    subject_id: str = Field(description="The identifier of the thing measured.")
    measure_type: str = Field(
        description="The kind of number (orthogonal to risk_type) — var / "
        "expected_shortfall / sensitivity / exposure / concentration / "
        "stress_loss / liquidity_coverage / liquidity_tier_classification."
    )
    as_of_date: date = Field(
        description="The date the measurement is as of (append-only as-of axis)."
    )
    value: Decimal = Field(description="The measured value.")
    currency: str | None = Field(
        default=None, description="The currency, where the measure is monetary."
    )
    method: str = Field(
        description="historical simulation / parametric / Monte Carlo / full revaluation / "
        "factor model / scenario application."
    )
    scenario_id: str | None = Field(
        default=None,
        description="FK -> E-17, where the measurement is a stress/scenario "
        "result; null otherwise.",
    )
    model_id: str = Field(
        description="The risk model that produced the measurement (link to SD-14.4 governance)."
    )
    confidence_score: float | None = Field(
        default=None, description="Confidence score, where the method warrants one."
    )

    ENTITY_ID: ClassVar[str] = "E-19"
    MODEL_FILE: ClassVar[str] = "model/entities/core/E-19-risk-measurement.md"
    OWNERSHIP: ClassVar[OwnershipPattern] = OwnershipPattern.KEY_PARTITIONED
    # Key-partitioned by `risk_type` (ADR-0022 / ownership-map). The model's E-19
    # attribute schema now carries the `risk_type` column — the partition is backed
    # by a real column, matching `measurement_id` as the surrogate row-handle and
    # `risk_type` as the partition discriminator that is part of the logical
    # identity. `measure_type` is the orthogonal axis (kind of number), kept too.
    PARTITION_KEY: ClassVar[str | None] = "risk_type"
    GRAIN: ClassVar[tuple[str, ...]] = ("as_of_date",)


# ---------------------------------------------------------------------------
# E-20 Performance Result — as-of period / APPEND-ONLY. Single owner (SD-09.1).
# ---------------------------------------------------------------------------


class E20PerformanceResult(CanonicalEntity):
    """E-20 Performance Result — ``model/entities/core/E-20-performance-result.md``.

    A stored point-in-time return figure with inputs, methodology version and
    provenance. **Append-only** (the performance analogue of E-07/E-19). Bi-temporal
    grain: the ``period_start`` / ``period_end`` period (see ``GRAIN``); ``period_end``
    is the as-of date. Single owner (SD-09.1 Performance Measurement).
    """

    performance_result_id: str = Field(description="Primary key.")
    subject_type: str = Field(
        description="portfolio (E-03) / mandate (E-03) / composite / total_fund / "
        "asset_class (E-09)."
    )
    subject_id: str = Field(description="The identifier of the subject.")
    period_start: date = Field(description="The start of the measurement period.")
    period_end: date = Field(
        description="The end of the measurement period; the date the return is as of."
    )
    return_basis: str = Field(description="gross / net — gross of fees or net of fees.")
    return_method: str = Field(
        description="time_weighted / money_weighted / modified_dietz / since_inception."
    )
    return_value: Decimal = Field(description="The return, as a rate over the period.")
    currency: str | None = Field(
        default=None,
        description="The currency the return is expressed in, where a currency basis applies.",
    )
    metric_definition_id: str = Field(
        description="FK -> E-22. The governed Metric Definition / methodology version in force."
    )
    composite_id: str | None = Field(
        default=None,
        description="The GIPS composite, where subject_type = composite; null otherwise.",
    )
    valuation_source: str = Field(
        description="The valuation basis the return was computed from — the E-07 "
        "valuations underlying the period."
    )
    confidence_score: float | None = Field(
        default=None,
        description="Confidence score, where the inputs warrant one "
        "(an interim return on incomplete valuations).",
    )

    ENTITY_ID: ClassVar[str] = "E-20"
    MODEL_FILE: ClassVar[str] = "model/entities/core/E-20-performance-result.md"
    OWNERSHIP: ClassVar[OwnershipPattern] = OwnershipPattern.SINGLE
    PARTITION_KEY: ClassVar[str | None] = None
    GRAIN: ClassVar[tuple[str, ...]] = ("period_start", "period_end")


# ---------------------------------------------------------------------------
# E-05 Transaction — the universal investment event. Single owner (SD-12.1 IBOR).
# ---------------------------------------------------------------------------


class E05Transaction(CanonicalEntity):
    """E-05 Transaction — ``model/entities/core/E-05-transaction.md``.

    The universal investment event — anything that changes a holding (a trade, a
    subscription, a capital call, a distribution, a corporate action, a transfer).
    The event record from which positions (E-04) are derived and cash flows (E-06)
    arise. **Immutable** (a correction is a new transaction, not an edit). Single
    owner (SD-12.1 IBOR — transactions update the book of record).

    ``trade_date`` / ``settlement_date`` / ``status`` carry the TD–SD timing that
    drives the IBOR/ABOR book divergence (a trade is in IBOR on trade date, in ABOR
    on settlement date) and the timing-break class in the comparator feed.
    """

    transaction_id: str = Field(description="Primary key.")
    transaction_type: str = Field(
        description="trade / subscription / redemption / capital_call / distribution / "
        "corporate_action / transfer / fee / income."
    )
    portfolio_id: str = Field(description="FK -> E-03. The portfolio affected.")
    instrument_id: str = Field(description="FK -> E-02. The instrument or asset transacted.")
    trade_date: date = Field(description="When the transaction was agreed.")
    settlement_date: date | None = Field(
        default=None,
        description="When it settles; null for events without a settlement.",
    )
    quantity: Decimal | None = Field(
        default=None, description="Units transacted, where applicable."
    )
    amount_usd: Decimal = Field(
        description="The cash amount of the transaction, signed by direction."
    )
    counterparty_entity_id: str | None = Field(
        default=None,
        description="FK -> E-01. The legal entity faced (counterparty role); null where "
        "there is no counterparty.",
    )
    status: str = Field(description="pending / confirmed / settled / cancelled.")
    source: str = Field(description="The source the transaction was captured from.")

    ENTITY_ID: ClassVar[str] = "E-05"
    MODEL_FILE: ClassVar[str] = "model/entities/core/E-05-transaction.md"
    OWNERSHIP: ClassVar[OwnershipPattern] = OwnershipPattern.SINGLE
    PARTITION_KEY: ClassVar[str | None] = None
    GRAIN: ClassVar[tuple[str, ...]] = ()


# ---------------------------------------------------------------------------
# E-06 Cash Flow Event — the granular cash record. Single owner (SD-12.1 IBOR).
# ---------------------------------------------------------------------------


class E06CashFlowEvent(CanonicalEntity):
    """E-06 Cash Flow Event — ``model/entities/core/E-06-cash-flow-event.md``.

    A dated movement of cash between the investor and a portfolio / instrument /
    fund / counterparty — the granular cash record performance (especially
    money-weighted return) is computed from. **Immutable** (a correction is a new
    event). The cash *consequence* of a Transaction (E-05), kept separate because
    not every cash flow is a discrete transaction and not every transaction is a
    single cash flow. Single owner (SD-12.1 IBOR).
    """

    cash_flow_id: str = Field(description="Primary key.")
    portfolio_id: str = Field(description="FK -> E-03. The portfolio the cash flow occurs in.")
    instrument_id: str | None = Field(
        default=None,
        description="FK -> E-02; null for a portfolio-level flow.",
    )
    transaction_id: str | None = Field(
        default=None,
        description="FK -> E-05. The transaction that generated this cash flow, where "
        "there is one.",
    )
    cash_flow_date: date = Field(description="The date of the cash movement.")
    cash_flow_type: str = Field(
        description="contribution / distribution / coupon / dividend / fee / expense / "
        "income / principal / tax."
    )
    direction: str = Field(description="inflow or outflow, from the investor's perspective.")
    amount: Decimal = Field(description="The amount, signed by direction.")
    currency: str = Field(description="The cash-flow currency.")
    source: str = Field(description="The source the cash flow was captured from.")

    ENTITY_ID: ClassVar[str] = "E-06"
    MODEL_FILE: ClassVar[str] = "model/entities/core/E-06-cash-flow-event.md"
    OWNERSHIP: ClassVar[OwnershipPattern] = OwnershipPattern.SINGLE
    PARTITION_KEY: ClassVar[str | None] = None
    GRAIN: ClassVar[tuple[str, ...]] = ()


# ---------------------------------------------------------------------------
# E-24 Reconciliation Break — the owned, aged reconciliation finding. Single owner
# (SD-12.10 Reconciliation). Append-only-as-event (the disagreement happened on a
# date; the break is never deleted). ENGINE-OWNED, NOT a dbt staging entity — it is
# emitted by the OIM-162 reconciliation engine into a separate engine-owned break
# store (a distinct duckdb file), so it has NO `stg_e24_*.sql` staging model and is
# the one realised entity legitimately unstaged on the dbt staging surface (a
# surfaced coverage gap, never a drift). It IS registered here so `drift.py`
# substantively validates its Pydantic schema against the E-24 model file (the
# E-05/E-06 precedent — the schema cross-check is the contract enforcer).
# ---------------------------------------------------------------------------


class E24ReconciliationBreak(CanonicalEntity):
    """E-24 Reconciliation Break — ``model/entities/core/E-24-reconciliation-break.md``.

    The owned, aged record of a reconciliation difference — which two records
    disagreed, by how much, why, how serious, how long open, and how resolved.
    Shaped like a Limit Breach (E-18): an identified event with a ``status`` moving
    through investigation and escalation to resolution, the event itself never
    deleted. The *difference* is recomputable from the two source records; the
    *cause classification*, the *ageing* and the *resolution trail* are not, which is
    why the break is stored rather than computed as a transient view.

    OIM-162 cycle-1 emits these **append-only, insert-only, immutable** at
    ``status = open``, ``identified_date = as_of``, ``age_days = 0``, with a
    deterministic of-record ``cause_classification`` (or ``unexplained`` on a
    rule-miss). The ``status`` transition / ``resolved_date`` / ``resolution_note`` /
    ``correcting_entry_ref`` fields are the resolution lifecycle the entity carries —
    they are **never written this cycle** (the correcting entry + the lifecycle update
    are OIM-163, behind the breach gate). ``frozen=True`` (inherited) realises the
    immutable-as-event property: a break instance is a value, never mutated in place.
    """

    break_id: str = Field(description="Primary key.")
    reconciliation_type: str = Field(
        description="What was reconciled — position / cash / transaction / ibor_abor / "
        "custodian / counterparty."
    )
    record_a_ref: str = Field(
        description="The first record compared — the OpenIM-side record (E-04 / E-06 / E-05)."
    )
    record_b_ref: str = Field(
        description="The second record — the counter-record it disagreed with."
    )
    as_of_date: date = Field(description="The date the two records are compared as of.")
    identified_date: date = Field(description="The date the break was identified.")
    difference_amount: Decimal | None = Field(
        default=None, description="The monetary difference, where applicable."
    )
    difference_qty: Decimal | None = Field(
        default=None, description="The quantity difference, where the break is a position quantity."
    )
    cause_classification: str = Field(
        description="The classified root cause — timing / pricing / missing_transaction / "
        "data_error / fx / fees / unexplained."
    )
    materiality: str = Field(description="low / medium / high.")
    age_days: int = Field(description="Days since identified_date; derived, for ageing/escalation.")
    status: str = Field(
        description="open / investigated / escalated / resolved / accepted."
    )
    resolved_date: date | None = Field(
        default=None, description="When the break was resolved or accepted; null while open."
    )
    resolution_note: str | None = Field(
        default=None, description="How the break was resolved, or the rationale for acceptance."
    )
    correcting_entry_ref: str | None = Field(
        default=None,
        description="A reference to the transaction/adjustment that resolved the break.",
    )

    ENTITY_ID: ClassVar[str] = "E-24"
    MODEL_FILE: ClassVar[str] = "model/entities/core/E-24-reconciliation-break.md"
    OWNERSHIP: ClassVar[OwnershipPattern] = OwnershipPattern.SINGLE
    PARTITION_KEY: ClassVar[str | None] = None
    # Append-only as an event: the disagreement happened on a date. The set of breaks
    # is the reconciliation's finding log; a break is never deleted (the model's
    # immutable-as-event declaration). The grain's as-of axis is `identified_date`.
    GRAIN: ClassVar[tuple[str, ...]] = ("identified_date",)


# ---------------------------------------------------------------------------
# Registry — the realised entities, in model-file order. The drift check iterates this.
# The W2 reconciliation substrate adds E-05 Transaction + E-06 Cash Flow Event (the
# transaction-matching and cash-leg records the reconciliation tools consume) and, at
# OIM-162, E-24 Reconciliation Break (the owned finding the reconciliation engine
# emits — engine-owned + append-only, the one realised entity legitimately unstaged
# on the dbt staging surface; its Pydantic schema is still drift-checked here).
# ---------------------------------------------------------------------------

ENTITY_MODELS: tuple[type[CanonicalEntity], ...] = (
    E01LegalEntity,
    E02InstrumentAsset,
    E03PortfolioMandate,
    E04HoldingPosition,
    E05Transaction,
    E06CashFlowEvent,
    E07Valuation,
    E09AssetClass,
    E13EntityAlias,
    E14ExternalIdentifier,
    E19RiskMeasurement,
    E20PerformanceResult,
    E24ReconciliationBreak,
)
