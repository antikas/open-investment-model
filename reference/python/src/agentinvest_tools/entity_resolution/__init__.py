"""The deterministic entity-resolution capability — the three-tier cascade + golden records.

OpenIM's signature differentiator made runnable: the no-universal-identifier reality + the
deterministic three-tier resolution cascade (exact external-id -> deterministic name/alias key ->
steward review queue) + golden-record survivorship, producing canonical records keyed by the
internal golden key and quarantining the genuinely-ambiguous to a human, never force-merging.

THE DETERMINISTIC SPINE. The of-record resolve path (``cascade`` + ``normaliser``) imports NO LLM /
proposer / model module — the resolution decision is a pure function of the feed record's observable
evidence + the standing reference data. The probabilistic / LLM-proposer tier is deliberately out of
scope here. The module-graph spine assertion enforces the import-closure cleanliness.

The two append-only stores (``review_queue_store`` + ``golden_record_store``) are the
``break_store`` pattern verbatim — insert-only, immutable, engine-owned, ``dbt build``-safe.
"""

from __future__ import annotations

from agentinvest_tools.entity_resolution.cascade import (
    TIER2_THRESHOLD,
    FeedRecord,
    GoldenFieldProvenance,
    GoldenRecord,
    MasterEntity,
    ResolutionResult,
    build_golden_record,
    resolve_batch,
    resolve_record,
)
from agentinvest_tools.entity_resolution.golden_record_store import (
    GoldenRecordRow,
    GoldenRecordStoreUnavailableError,
    StoredGoldenRecord,
    append_golden_records,
    count_golden_records,
    provenance_to_json,
    read_golden_records,
    resolve_golden_store_path,
)
from agentinvest_tools.entity_resolution.normaliser import normalise_name
from agentinvest_tools.entity_resolution.review_queue_store import (
    ResolutionReviewStoreUnavailableError,
    ReviewItem,
    StoredReviewItem,
    append_review_items,
    count_review_items,
    read_review_items,
    resolve_review_store_path,
)

__all__ = [
    "TIER2_THRESHOLD",
    "FeedRecord",
    "GoldenFieldProvenance",
    "GoldenRecord",
    "GoldenRecordRow",
    "GoldenRecordStoreUnavailableError",
    "MasterEntity",
    "ResolutionResult",
    "ResolutionReviewStoreUnavailableError",
    "ReviewItem",
    "StoredGoldenRecord",
    "StoredReviewItem",
    "append_golden_records",
    "append_review_items",
    "build_golden_record",
    "count_golden_records",
    "count_review_items",
    "normalise_name",
    "provenance_to_json",
    "read_golden_records",
    "read_review_items",
    "resolve_batch",
    "resolve_golden_store_path",
    "resolve_record",
    "resolve_review_store_path",
]
