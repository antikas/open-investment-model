"""The shared malformed-body-safe pass-through request serde — the one SSOT for every handler.

Every registered Restate request handler in the agentINVEST polyglot split (the four
``agentinvest_tools`` data/tool services — ``pyTools`` / ``navData`` ×2 / ``argResolver`` /
``canonicalData`` — and the ``agentinvest_orchestrator`` ``agentinvestPlanner.planTask``) shares the
SAME ingress request-validation discipline:

1. a **permissive pass-through** ``input_serde`` that parses the JSON body and returns the raw value
   WITHOUT validating (so a raised validation error never reaches the SDK's serde layer), and
2. an in-**handler** ``_coerce_request`` that runs the typed ``extra="forbid"`` validation in the
   handler body — where a raised ``TerminalError`` keeps its 400 (the SDK does NOT re-wrap a
   handler-body error to a status-less 500).

The catch this serde is built around (the bd09 precedent): the Restate SDK **re-wraps any
exception raised inside a serde's** ``deserialize`` **as its own status-less** ``TerminalError`` —
surfaced HTTP **500**, discarding the 400 the in-handler guard wants. So the serde must NEVER raise.

The malformed-body invariant (why this is its own SSOT module): a bare ``json.loads(buf)``
**raises** on a malformed-JSON or non-UTF8 transport body (``json.JSONDecodeError`` — a subclass of
``ValueError`` — or ``UnicodeDecodeError``), so a garbage *body* used to surface as a status-less
500 from every handler, where a garbage *key* surfaced as a clean 400. This serde makes the
never-raise invariant **structural** — it catches the WHOLE parse-failure class (``except
Exception``, not an enumerable tuple) and returns the raw decoded text as a ``str`` — a non-dict
value that every handler's ``_coerce_request`` already rejects as a clean ``TerminalError(400)``
("request body must be a JSON object — got str"). The structural catch is required because an
enumerated tuple (``json.JSONDecodeError`` / ``ValueError`` / ``UnicodeDecodeError``) missed
``RecursionError`` — raised by ``json.loads`` on a deeply-nested body, a ``RuntimeError`` subclass,
not a ``ValueError`` — which escaped to a status-less 500. Result: a malformed
body (malformed JSON, non-UTF8, OR a deeply-nested/huge body) is a clean 400 on the wire, consistent
with the unknown-key handling, and the serde keeps its pass-through invariant (it never raises).

The handlers keep their typed Pydantic ``req:`` annotations, so the auto-generated OpenAPI/MCP
surface still derives a typed request schema (``additionalProperties: false``) — only the
``input_serde`` instance is shared from here; the typed schema is derived from the annotation,
independently of the serde.

This module imports only the stdlib and the Restate serde base — it has NO dependency on the
orchestrator package, so ``agentinvest_orchestrator`` importing it (orchestrator → tools, the
direction the orchestrator already depends on) introduces no circular import.
"""

from __future__ import annotations

import json
from typing import Any

import restate.serde


class PassThroughJsonSerde(restate.serde.Serde[Any]):
    """A permissive, malformed-body-safe pass-through JSON deserialiser — the one SSOT serde.

    ``deserialize`` NEVER raises (the pass-through invariant the in-handler 400 status depends on):

    - an empty body → ``{}`` (the handler's ``_coerce_request`` then validates the empty object);
    - a parseable JSON body → the raw parsed value, unchanged (a dict, or a non-dict the handler's
      ``_coerce_request`` rejects as a clean 400);
    - ANY parse failure — a **malformed-JSON / non-UTF8 body**, a **deeply-nested body** (which
      makes ``json.loads`` raise ``RecursionError``), a **huge body** (``MemoryError``) — → the raw
      text decoded with ``errors="replace"`` (a ``str``), which the handler's ``_coerce_request``
      rejects as a clean ``TerminalError(400)`` via its existing non-dict branch — never a
      status-less 500, never an uncaught exception. The catch is ``except Exception`` (the
      structural never-raise invariant), not an enumerable tuple (which missed ``RecursionError``).
    """

    def deserialize(self, buf: bytes) -> Any:
        if not buf:
            return {}
        try:
            return json.loads(buf)
        except Exception:
            # The pass-through serde must NEVER raise — that is the whole point of the pass-through:
            # any parse failure must return the raw text so the in-handler ``_coerce_request`` owns
            # the clean ``TerminalError(400)``; the SDK never re-wraps a serde-raised exception to a
            # status-less 500. ``except Exception`` (NOT ``BaseException`` — ``KeyboardInterrupt`` /
            # ``SystemExit`` keep propagating) makes the never-raise invariant STRUCTURALLY TRUE: an
            # enumerated tuple (``json.JSONDecodeError``, ``ValueError``, ``UnicodeDecodeError``)
            # missed ``RecursionError`` (raised by ``json.loads`` on a deeply-nested body, e.g.
            # ``b"[" * 20000 + b"]" * 20000`` — a ``RuntimeError`` subclass, not a ``ValueError``)
            # which escaped → a status-less 500. The serde does NOTHING but parse,
            # so a blanket catch can mask no logic. Any parse failure — malformed JSON, non-UTF8,
            # RecursionError on a deeply-nested body, MemoryError on a huge body — returns the raw
            # decoded text as a non-dict ``str`` that ``_coerce_request`` rejects as a clean 400
            # ("request body must be a JSON object — got str"). ``errors="replace"`` makes the
            # decode itself total (a non-UTF8 byte cannot raise here).
            return buf.decode("utf-8", errors="replace")

    def serialize(self, obj: Any) -> bytes:
        if obj is None:
            return b""
        return json.dumps(obj).encode("utf-8")
