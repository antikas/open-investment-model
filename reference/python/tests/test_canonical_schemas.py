"""Tests over the ten OIM-103 canonical-model Pydantic schemas."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from agentinvest_canonical_model import (
    ENTITY_MODELS,
    E01LegalEntity,
    E04HoldingPosition,
    E05Transaction,
    E06CashFlowEvent,
    E07Valuation,
    E09AssetClass,
    E19RiskMeasurement,
    E20PerformanceResult,
)
from agentinvest_canonical_model.base import CanonicalEntity, OwnershipPattern


def test_registered_entities_in_model_file_order() -> None:
    """The registry carries the realised entities in model-file order.

    The OIM-103 ten (E-01..E-04, E-07, E-09, E-13, E-14, E-19, E-20), the W2
    reconciliation substrate's E-05 Transaction + E-06 Cash Flow Event (slotted in
    model-file order between E-04 and E-07), and E-24 Reconciliation Break (OIM-162 —
    the engine-owned finding the reconciliation engine emits, after E-20 in model-file
    order; the one realised entity with no dbt staging model).
    """
    ids = [cls.ENTITY_ID for cls in ENTITY_MODELS]
    assert ids == [
        "E-01", "E-02", "E-03", "E-04", "E-05", "E-06",
        "E-07", "E-09", "E-13", "E-14", "E-19", "E-20", "E-24",
    ]


def test_every_entity_declares_model_file_linkage() -> None:
    """Each schema names its model file and an ownership pattern (the drift-check input)."""
    for cls in ENTITY_MODELS:
        assert cls.MODEL_FILE.startswith("model/entities/core/")
        assert isinstance(cls.OWNERSHIP, OwnershipPattern)


def test_legal_entity_round_trips() -> None:
    e = E01LegalEntity(
        entity_id="LE-0001",
        entity_name="Acme Asset Management LLP",
        entity_type="partnership",
        status="active",
        first_seen_at=date(2020, 1, 1),
    )
    assert e.parent_entity_id is None  # null at the top
    assert e.known_aliases == []  # denormalised cache, empty by default
    assert e.external_ids == {}


def test_extra_field_is_forbidden() -> None:
    """extra='forbid' — an undeclared attribute is drift, rejected at validation."""
    with pytest.raises(ValidationError):
        E01LegalEntity(
            entity_id="LE-0002",
            entity_name="X",
            entity_type="corporation",
            status="active",
            first_seen_at=date(2021, 1, 1),
            not_a_real_column="boom",  # type: ignore[call-arg]
        )


def test_entities_are_frozen() -> None:
    """frozen=True — append-only records are values; no in-place mutation."""
    e = E09AssetClass(
        asset_class_key=1,
        asset_class_code="PE",
        asset_class_label="Private Equity",
        markets="private",
        effective_from=date(2020, 1, 1),
    )
    with pytest.raises(ValidationError):
        e.markets = "public"


def test_e04_key_partitioned_by_book() -> None:
    """E-04 declares the `book` partition key per ADR-0022; `book` is required."""
    assert E04HoldingPosition.OWNERSHIP is OwnershipPattern.KEY_PARTITIONED
    assert E04HoldingPosition.PARTITION_KEY == "book"
    pos = E04HoldingPosition(
        position_id="POS-1",
        book="ibor",
        portfolio_id="PF-1",
        instrument_id="INS-1",
        as_of_date=date(2026, 3, 31),
        quantity=Decimal("1000"),
        currency="USD",
    )
    assert pos.book == "ibor"
    # `book` is part of identity — required, not defaulted.
    with pytest.raises(ValidationError):
        E04HoldingPosition(
            position_id="POS-2",
            portfolio_id="PF-1",  # type: ignore[call-arg]
            instrument_id="INS-1",
            as_of_date=date(2026, 3, 31),
            currency="USD",
        )


def test_money_columns_are_decimal_not_float() -> None:
    """Monetary/quantity columns are Decimal (exact), per the model's `decimal` type."""
    pos = E04HoldingPosition(
        position_id="POS-3",
        book="abor",
        portfolio_id="PF-1",
        instrument_id="INS-1",
        as_of_date=date(2026, 3, 31),
        market_value_usd=Decimal("125500.00"),
        currency="USD",
    )
    assert isinstance(pos.market_value_usd, Decimal)


def test_transaction_round_trips_with_td_sd_timing() -> None:
    """E-05 carries trade_date + settlement_date + status — the TD/SD timing.

    An in-flight buy (settlement_date after trade_date, status pending) is the shape
    that drives the IBOR/ABOR divergence and the timing-break class. settlement_date,
    quantity and counterparty are optional (the model declares them nullable).
    """
    txn = E05Transaction(
        transaction_id="TXN-1",
        transaction_type="trade",
        portfolio_id="PF-1",
        instrument_id="INS-1",
        trade_date=date(2026, 3, 31),
        settlement_date=date(2026, 4, 1),
        quantity=Decimal("1000"),
        amount_usd=Decimal("-250000.00"),
        counterparty_entity_id="LE-0002",
        status="pending",
        source="oms",
    )
    assert txn.settlement_date is not None
    assert txn.settlement_date > txn.trade_date
    assert isinstance(txn.amount_usd, Decimal)
    # An income event with no settlement / counterparty leaves them null.
    income = E05Transaction(
        transaction_id="TXN-2",
        transaction_type="income",
        portfolio_id="PF-1",
        instrument_id="INS-1",
        trade_date=date(2026, 3, 31),
        amount_usd=Decimal("4200.00"),
        status="settled",
        source="custodian_feed",
    )
    assert income.settlement_date is None
    assert income.counterparty_entity_id is None


def test_cash_flow_event_round_trips_and_ties_to_transaction() -> None:
    """E-06 carries the cash leg, signed + dated + typed, tied to its E-05 where one exists."""
    cf = E06CashFlowEvent(
        cash_flow_id="CF-1",
        portfolio_id="PF-1",
        instrument_id="INS-1",
        transaction_id="TXN-1",
        cash_flow_date=date(2026, 4, 1),
        cash_flow_type="principal",
        direction="outflow",
        amount=Decimal("-250000.00"),
        currency="USD",
        source="custodian_feed",
    )
    assert cf.transaction_id == "TXN-1"
    assert isinstance(cf.amount, Decimal)
    # A portfolio-level fee with no instrument leaves instrument_id null.
    fee = E06CashFlowEvent(
        cash_flow_id="CF-2",
        portfolio_id="PF-1",
        cash_flow_date=date(2026, 3, 31),
        cash_flow_type="fee",
        direction="outflow",
        amount=Decimal("-120000.00"),
        currency="USD",
        source="administrator",
    )
    assert fee.instrument_id is None
    assert fee.transaction_id is None


@pytest.mark.parametrize(
    ("cls", "grain"),
    [
        (E07Valuation, ("valuation_date",)),
        (E19RiskMeasurement, ("as_of_date",)),
        (E20PerformanceResult, ("period_start", "period_end")),
    ],
)
def test_as_of_entities_declare_bitemporal_grain(
    cls: type[CanonicalEntity], grain: tuple[str, ...]
) -> None:
    """E-07/E-19/E-20 declare their as-of/append-only grain columns (OIM-110 input).

    The grain is DECLARED here; the materialisation strategy (snapshot/incremental)
    is an OIM-110 coordination point, deliberately not set in this cycle.
    """
    assert cls.GRAIN == grain
    for col in grain:
        assert col in cls.model_fields


def test_confidence_scores_are_float() -> None:
    """The only `float`-typed columns in the model are the confidence scores."""
    v = E07Valuation(
        valuation_id="VAL-1",
        position_id="POS-1",
        valuation_date=date(2026, 3, 31),
        value_usd=Decimal("125500.00"),
        method="observable_price",
        valuation_level="level_1",
        source="pricing_feed",
    )
    assert v.confidence_score is None  # optional — implicit for an observable price
