"""Content hashing with no internal package dependencies.

Split out from ``capability.provenance`` so it can be imported by
``graph.models`` without pulling in ``capability``'s full ``__init__``
(which imports ``capability.promotion``, which imports ``search`` — and
``search.loop`` imports ``graph``. Without this split, ``graph -> capability
-> search -> graph`` is a real circular import.) Not part of the public API;
import ``content_hash`` from ``prompt_optimization.capability`` instead.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def content_hash(value: Any) -> str:
    """SHA-256 over a canonical JSON serialization, for auditable, order-independent identity."""
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
