"""Verifiable-claims checking: makes a doc's factual assertions checkable
against live data, instead of trusted the way a context-window summary or
``/compact`` output has to be trusted.

A :class:`Claim` pairs one factual assertion made in a doc (e.g. "the
no_skill run's utility is 0.9325") with the value actually recomputed from
the underlying content-addressed graph or JSON artifact at verification
time. Unlike a one-shot prose paraphrase -- which has no way to check itself
against the data it summarizes, and where a dropped or misremembered number
looks identical to a correct one -- a claim is re-checkable any time the
source data changes, and a mismatch is a hard, reportable failure rather
than something a reader has to happen to notice.

This module deliberately does not parse prose to invent claims automatically
(unreliable, and it would just move the "trust me" problem into an
extraction step, undermining the whole point). A doc's author registers
each checkable assertion explicitly, as plain Python, alongside the doc --
see e.g. a ``verify_claims.py`` next to a ``REPORT.md``. Claims this module
can't express (a narrative judgment call like "this is the more likely
explanation") stay prose by nature; that's a feature, not a gap -- it keeps
the checkable/interpretive boundary visible instead of pretending everything
is equally verifiable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Claim:
    """One checkable factual assertion made in a doc.

    ``actual`` must already be recomputed live by the caller from the
    underlying source (a ``GraphStore`` query, a JSON artifact read, a
    metric function call, ...) before constructing the ``Claim`` -- this
    module only compares ``actual`` against ``expected`` (the value the doc
    states), it never fetches data itself. That keeps it decoupled from any
    particular storage format and keeps "what was recomputed and how"
    visible in the calling script rather than hidden in this module.
    """

    description: str
    doc: str
    expected: Any
    actual: Any
    tolerance: float = 0.0


@dataclass(frozen=True)
class ClaimResult:
    """The outcome of checking one :class:`Claim`."""

    claim: Claim
    passed: bool
    delta: float | None = None


def verify_claim(claim: Claim) -> ClaimResult:
    """Check one claim's ``actual`` against its ``expected`` value.

    Bools compare by identity (bool is a subclass of int in Python, so this
    check must precede the numeric branch or ``True``/``1`` would silently
    conflate with a numeric tolerance check). Numbers compare within
    ``tolerance``. Everything else (strings, dicts, tuples, ...) compares by
    equality.
    """
    expected, actual = claim.expected, claim.actual
    if isinstance(expected, bool) or isinstance(actual, bool):
        return ClaimResult(claim, passed=bool(expected) == bool(actual))
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        delta = abs(float(actual) - float(expected))
        return ClaimResult(claim, passed=delta <= claim.tolerance, delta=delta)
    return ClaimResult(claim, passed=expected == actual)


def verify_claims(claims: list[Claim]) -> list[ClaimResult]:
    """Check a batch of claims, preserving order."""
    return [verify_claim(claim) for claim in claims]


def all_passed(results: list[ClaimResult]) -> bool:
    return all(result.passed for result in results)


def format_report(results: list[ClaimResult]) -> str:
    """Render a human-readable pass/fail report, one line per claim."""
    n_passed = sum(1 for result in results if result.passed)
    lines = [f"{n_passed}/{len(results)} claims verified"]
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        delta = f"  delta={result.delta:.4g}" if result.delta is not None else ""
        lines.append(
            f"[{status}] {result.claim.doc}: {result.claim.description} "
            f"expected={result.claim.expected!r} actual={result.claim.actual!r}{delta}"
        )
    return "\n".join(lines)
