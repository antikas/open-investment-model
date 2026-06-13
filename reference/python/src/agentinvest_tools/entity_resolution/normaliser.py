"""Deterministic legal-entity name normalisation — the Tier-2 match key.

The deterministic core of the resolution cascade's Tier-2 (alias / normalised-name match). A pure,
total function ``normalise_name`` that maps a raw legal-entity name string to a canonical
normalised form, so two records that name the SAME entity under typographic / suffix / case /
diacritic variation collapse to the SAME key — and two records that name DIFFERENT entities do not.

THE DETERMINISTIC SPINE (the load-bearing design point). This is rule-based string normalisation —
case-folding, whitespace collapse, diacritic stripping, punctuation removal, legal-suffix
stripping — NOT a model. There is no LLM, no learned embedding, no fuzzy edit-distance threshold:
the normalised form is an EXACT, reproducible function of the input. Two names match at Tier-2 iff
their normalised forms are byte-equal. The probabilistic / LLM-proposer tier (a model proposing a
candidate match for steward review) is deliberately out of scope here — it is NOT present, and the
resolve-of-record path imports none of it (the module-graph spine assertion enforces that).

WHY DETERMINISTIC NORMALISATION, NOT FUZZY MATCHING. A mis-merge silently corrupts the golden
master, so the of-record match bar is exactness AFTER a declared, auditable normalisation — never a
similarity score that could merge two genuinely-distinct entities. Everything the normaliser cannot
collapse to an exact key falls THROUGH to the steward review queue (Tier-3), where a human decides.
That is the honest boundary: deterministic normalisation is the floor the model's ``## Resolution``
section names; anything subtler is quarantined, never force-merged.

SYNTHETIC, DETERMINISTIC. The suffix list + the diacritic map are a documented, illustrative
rule set tuned to the synthetic resolution oracle — not a benchmarked real-world
name-normalisation distribution. A real deployment would extend the suffix list and the
transliteration map; the SEAM (a pure normalise function the cascade keys on) is what is
load-bearing.
"""

from __future__ import annotations

import re
import unicodedata

# The legal-form suffixes stripped from the END of a normalised name. A declared, auditable list —
# extend it for new jurisdictions; never make it a learned/fuzzy threshold. The
# longer multi-token forms are listed first so "limited" is stripped before a bare "ltd" rule could
# leave a dangling token (the strip is longest-match-first within each pass).
_LEGAL_SUFFIXES: tuple[str, ...] = (
    "limited liability partnership",
    "limited liability company",
    "incorporated",
    "corporation",
    "company",
    "limited",
    "holdings",
    "partners",
    "associates",
    "advisors",
    "advisers",
    "capital",
    "group",
    "llp",
    "llc",
    "ltd",
    "inc",
    "corp",
    "co",
    "plc",
    "lp",
    "llp",
    "sa",
    "ag",
    "nv",
    "bv",
    "gmbh",
    "pte",
    "pty",
    "ou",  # Estonian OÜ (osaühing) — a private limited company; "oü" -> "ou" after diacritic strip
    "oy",  # Finnish Oy — a private limited company
    "as",  # Norwegian/Danish AS (aksjeselskap) — a private limited company
    "sarl",  # French SARL — a private limited company
    "srl",  # Italian / Spanish SRL — a private limited company
)

# Punctuation collapsed to a single space before suffix stripping (so "L.L.P." -> "llp", "A/S" ->
# two tokens) — every non-alphanumeric run becomes one space. Deterministic, total.
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_WS = re.compile(r"\s+")


def _strip_diacritics(text: str) -> str:
    """Strip diacritics via NFKD decomposition, dropping the combining marks — deterministic, total.

    "Crédit Agricole" -> "credit agricole". A pure Unicode normalisation: decompose to base char +
    combining marks, then drop the marks. No locale, no model — the same input always maps to the
    same output.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _strip_legal_suffixes(tokens: list[str]) -> list[str]:
    """Strip trailing legal-form suffix tokens, repeatedly, until none remains — deterministic.

    Repeated so a doubled suffix ("... GP Ltd Co") collapses fully. Only strips from the END so an
    interior word that happens to equal a suffix (rare, but e.g. "Capital" inside a real name) is
    preserved unless it is genuinely trailing. Never strips the last remaining token (a name made up
    ONLY of suffix words keeps its final token — there is always a non-empty key).
    """
    changed = True
    while changed and len(tokens) > 1:
        changed = False
        if tokens[-1] in _LEGAL_SUFFIXES:
            tokens = tokens[:-1]
            changed = True
    return tokens


def normalise_name(raw: str | None) -> str:
    """Map a raw legal-entity name to its canonical normalised form — pure, total, deterministic.

    The pipeline (each step deterministic): casefold -> strip diacritics -> collapse punctuation to
    spaces -> collapse whitespace -> drop trailing legal-form suffix tokens -> re-join with single
    spaces. Two names normalise EQUAL iff they are the same entity name under case / whitespace /
    punctuation / diacritic / legal-suffix variation. A ``None`` or all-noise input normalises to
    the
    empty string (which never matches a real master — it falls through to review).

    Examples (the synthetic oracle variants):
      "Private Equity GP LE-0004 Ltd"     -> "private equity gp le-0004"
      "Private Equity GP LE-0004 Limited" -> "private equity gp le-0004"   (suffix variant)
      "ISSUER LE-0048 CORP"               -> "issuer le-0048"              (case + suffix)
      "Issuer LE-0018 Corporation"        -> "issuer le-0018"             (Corp/Corporation)
    """
    if raw is None:
        return ""
    folded = raw.casefold()
    deaccented = _strip_diacritics(folded)
    spaced = _NON_ALNUM.sub(" ", deaccented)
    collapsed = _WS.sub(" ", spaced).strip()
    if not collapsed:
        return ""
    tokens = collapsed.split(" ")
    kept = _strip_legal_suffixes(tokens)
    return " ".join(kept)
