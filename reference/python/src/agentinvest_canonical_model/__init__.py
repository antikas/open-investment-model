"""agentINVEST canonical model — typed Pydantic schemas for the OpenIM entities.

This is the **`@agentinvest/canonical-model`** package: the OpenIM canonical
entity model (`model/entities/E-NN-*.md`) realised as typed Pydantic v2 schemas,
shared across the BD-09 tools, the orchestrator and the canonical-data layer. The
OpenIM **model files are the single source of truth**; these schemas are a
faithful realisation of them, and the schema-drift check (``drift.py``) fails the
build if they diverge.

The package realises the BD-09-relevant entities plus the W2 reconciliation
transaction + cash records:

- ``E01LegalEntity``      — E-01 Legal Entity (the universal party master)
- ``E02InstrumentAsset``  — E-02 Instrument / Asset (the holdable-thing master)
- ``E03PortfolioMandate`` — E-03 Portfolio / Mandate (the container; faceted)
- ``E04HoldingPosition``  — E-04 Holding / Position (key-partitioned by ``book``)
- ``E05Transaction``      — E-05 Transaction (the universal investment event)
- ``E06CashFlowEvent``    — E-06 Cash Flow Event (the granular cash record)
- ``E07Valuation``        — E-07 Valuation (as-of / append-only)
- ``E09AssetClass``       — E-09 Asset Class (effective-dated reference taxonomy)
- ``E13EntityAlias``      — E-13 Entity Alias (append-only; key-partitioned)
- ``E14ExternalIdentifier`` — E-14 External Identifier (key-partitioned)
- ``E19RiskMeasurement``  — E-19 Risk Measurement (as-of / append-only)
- ``E20PerformanceResult`` — E-20 Performance Result (as-of / append-only)

The as-of/append-only **grain** of the bi-temporal entities (E-07 Valuation,
E-19 Risk Measurement, E-20 Performance Result) is declared on the schema and
named in ``BITEMPORAL_GRAIN``; it is **materialised** in the canonical-data layer
as an incremental, two-axis (valid-time + knowledge-time) append-only log with
derived system-time bounds (current and as-of-knowledge access). The remaining
entities of the wider model are realised incrementally as they are needed.
"""

from __future__ import annotations

from agentinvest_canonical_model.entities import (
    ENTITY_MODELS,
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
)

__all__ = [
    "ENTITY_MODELS",
    "E01LegalEntity",
    "E02InstrumentAsset",
    "E03PortfolioMandate",
    "E04HoldingPosition",
    "E05Transaction",
    "E06CashFlowEvent",
    "E07Valuation",
    "E09AssetClass",
    "E13EntityAlias",
    "E14ExternalIdentifier",
    "E19RiskMeasurement",
    "E20PerformanceResult",
    "__version__",
]

__version__ = "0.1.0"
