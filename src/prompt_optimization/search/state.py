"""The BCSO search state machine: two gates, not one fuzzy "looks good enough."

``BASELINE -> SEARCHING -> QUALIFIED -> SATURATION_CHECK -> {FROZEN | back to
SEARCHING} -> TESTED -> RELEASED``. Gate 1 (qualification) asks whether the
candidate clears benchmark floors; gate 2 (saturation) asks whether the
search can still find material improvement (``Δ_opt``). Both must pass before
freezing — a candidate can qualify long before the search saturates.
"""
from __future__ import annotations

from enum import Enum


class SearchState(str, Enum):
    BASELINE = "baseline"
    SEARCHING = "searching"
    QUALIFIED = "qualified"
    SATURATION_CHECK = "saturation_check"
    FROZEN = "frozen"
    TESTED = "tested"
    RELEASED = "released"


def next_state(current: SearchState, *, qualified: bool, saturated: bool, tested: bool = False) -> SearchState:
    """One transition step of the state machine; returns ``current`` unchanged when no gate fires.

    - ``BASELINE -> SEARCHING`` unconditionally (search always begins).
    - ``SEARCHING -> QUALIFIED`` once the qualification gate passes; otherwise
      stays ``SEARCHING``.
    - ``QUALIFIED -> SATURATION_CHECK`` unconditionally (every qualified
      checkpoint is re-examined for saturation).
    - ``SATURATION_CHECK -> FROZEN`` once ``Δ_opt <= ε_opt``; otherwise back
      to ``SEARCHING`` (still finding material gains).
    - ``FROZEN -> TESTED`` after the one-shot ``D_test`` run (``tested=True``).
    - ``TESTED -> RELEASED``.
    """
    if current == SearchState.BASELINE:
        return SearchState.SEARCHING
    if current == SearchState.SEARCHING:
        return SearchState.QUALIFIED if qualified else SearchState.SEARCHING
    if current == SearchState.QUALIFIED:
        return SearchState.SATURATION_CHECK
    if current == SearchState.SATURATION_CHECK:
        return SearchState.FROZEN if saturated else SearchState.SEARCHING
    if current == SearchState.FROZEN:
        return SearchState.TESTED if tested else SearchState.FROZEN
    if current == SearchState.TESTED:
        return SearchState.RELEASED
    return SearchState.RELEASED
