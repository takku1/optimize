"""Conservative, model-free judging primitives."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .deterministic import SuccessBand, check_success_band


def judge_internally(text: str, scenario: Any) -> dict[str, Any]:
    """Certify only pre-registered observable properties of a response.

    Missing executable rules are unresolved, never a pass.  Phrase and shape
    checks do not claim semantic correctness; that limitation is explicit in
    the result for downstream promotion logic.
    """
    metadata = getattr(scenario, "metadata", None) or {}
    if isinstance(scenario, dict):
        metadata = scenario.get("metadata", {})
    raw_band = metadata.get("success_band") if isinstance(metadata, Mapping) else None
    if not isinstance(raw_band, Mapping):
        return {"status": "unresolved", "passed": None,
                "reason": "scenario has no executable success_band",
                "semantic_review_required": True}
    result = check_success_band(text, SuccessBand.from_dict(dict(raw_band)))
    return {"status": "certified" if result["passed"] else "failed",
            "passed": result["passed"], "checks": result,
            "semantic_review_required": True,
            "reason": "mechanical checks do not establish semantic correctness"}
