"""Generic, data-driven skill revision and structural scoring."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


_KINDS = {"contains", "contains_all", "contains_any", "not_contains", "regex", "max_tokens", "min_tokens"}


@dataclass(frozen=True)
class OptimizationSpec:
    id: str
    activation: Mapping[str, Any]
    revision: Mapping[str, Any]
    checks: tuple[Mapping[str, Any], ...]
    objective: Mapping[str, Any]

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "OptimizationSpec":
        if not isinstance(raw, Mapping) or not str(raw.get("id", "")).strip():
            raise ValueError("optimization spec requires an object with a non-empty id")
        checks = raw.get("checks", [])
        if not isinstance(checks, list) or not checks:
            raise ValueError("optimization spec requires a non-empty checks list")
        seen: set[str] = set()
        normalized: list[Mapping[str, Any]] = []
        for item in checks:
            check = _mapping(item, "check")
            check_id, kind = str(check.get("id", "")).strip(), str(check.get("kind", "")).strip()
            if not check_id or check_id in seen:
                raise ValueError("check ids must be non-empty and unique")
            if kind not in _KINDS:
                raise ValueError(f"unsupported check kind: {kind!r}")
            if float(check.get("weight", 1)) <= 0:
                raise ValueError("check weight must be positive")
            seen.add(check_id)
            normalized.append(dict(check))
        return cls(
            str(raw["id"]), _mapping(raw.get("activation", {}), "activation"),
            _mapping(raw.get("revision", {}), "revision"), tuple(normalized),
            _mapping(raw.get("objective", {}), "objective"),
        )


def load_optimization_spec(path: str | Path) -> OptimizationSpec:
    spec_path = Path(path)
    try:
        raw = json.loads(spec_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid optimization spec {path}: {exc}") from exc
    try:
        raw = _resolve_assets(raw, spec_path.parent)
    except OSError as exc:
        raise ValueError(f"invalid optimization spec asset: {exc}") from exc
    return OptimizationSpec.from_dict(raw)


def discover_optimization_spec(seed_path: str | Path) -> Path | None:
    seed = Path(seed_path)
    candidates = (seed.with_suffix(".optimization.json"), seed.parent / "optimization.json")
    found = [item for item in candidates if item.is_file()]
    if len(found) > 1:
        raise ValueError(f"multiple adjacent optimization specs found: {found}")
    return found[0] if found else None


def is_activated(spec: OptimizationSpec, text: str, *, source_path: str | Path | None = None) -> bool:
    lowered, activation = text.casefold(), spec.activation
    if any(value.casefold() not in lowered for value in _strings(activation.get("required_all", ()))):
        return False
    if any(value.casefold() in lowered for value in _strings(activation.get("forbidden_any", ()))):
        return False
    if activation.get("regex") and not re.search(str(activation["regex"]), text, re.I | re.S):
        return False
    suffixes = _strings(activation.get("path_suffixes", ()))
    return not suffixes or (source_path is not None and any(str(source_path).casefold().endswith(x.casefold()) for x in suffixes))


def apply_revision(text: str, spec: OptimizationSpec) -> str:
    revision = spec.revision
    if "document" in revision:
        document = revision["document"]
        if not isinstance(document, str) or not document.strip():
            raise ValueError("revision.document must be non-empty text")
        return _newline(document)
    result = text
    for key, value in _mapping(revision.get("metadata", {}), "revision.metadata").items():
        result = _set_frontmatter(result, str(key), str(value))
    sections = revision.get("sections", [])
    if not isinstance(sections, list):
        raise ValueError("revision.sections must be a list")
    for raw in sections:
        item = _mapping(raw, "revision section")
        heading, content = str(item.get("heading", "")).strip(), str(item.get("content", "")).strip()
        if not heading.startswith("#") or not content:
            raise ValueError("revision section requires a heading and content")
        result = _upsert_section(
            result, heading, content, _strings(item.get("aliases", ())), str(item.get("after", "")),
        )
    return _newline(result)


def propose_from_spec(spec: OptimizationSpec, source_path: str | Path | None = None):
    def propose(current: str, feedback: Mapping[str, Any], turn: int) -> str:
        del feedback, turn
        return apply_revision(current, spec) if is_activated(spec, current, source_path=source_path) else current
    return propose


def score_from_spec(text: str, spec: OptimizationSpec) -> dict[str, Any]:
    outcomes, evidence = {}, {}
    total = passed_weight = 0.0
    hard_passed = True
    for check in spec.checks:
        scoped = _scope(text, check.get("scope"))
        passed, detail = _evaluate(scoped, check)
        check_id, weight = str(check["id"]), float(check.get("weight", 1))
        outcomes[check_id], evidence[check_id] = passed, detail
        total += weight
        passed_weight += weight if passed else 0
        hard_passed = hard_passed and (passed or not bool(check.get("hard", True)))
    fixed_point = apply_revision(text, spec) == _newline(text)
    outcomes["revision_fixed_point"] = fixed_point
    evidence["revision_fixed_point"] = {
        "passed": fixed_point,
        "reason": "applying the declared revision again must not change the candidate",
    }
    total += 1
    passed_weight += 1 if fixed_point else 0
    hard_passed = hard_passed and fixed_point
    utility, tokens = passed_weight / total, len(text.split())
    return {
        "utility": utility, "tokens": tokens, "information_density": utility / max(tokens, 1),
        "hard_invariants_passed": hard_passed, "checks": outcomes, "check_evidence": evidence,
        "optimization_spec_id": spec.id, "evidence_tier": "structural_proxy",
        "behavioral_validation_required": True,
    }


def combine_structural_and_behavioral(structural: Mapping[str, Any], behavioral: Mapping[str, Any],
                                      spec: OptimizationSpec) -> dict[str, Any]:
    sw, bw = float(spec.objective.get("structural_weight", .25)), float(spec.objective.get("behavioral_weight", .75))
    if sw < 0 or bw <= 0:
        raise ValueError("objective weights require structural_weight >= 0 and behavioral_weight > 0")
    utility = (sw * float(structural["utility"]) + bw * float(behavioral["utility"])) / (sw + bw)
    tokens = int(structural["tokens"])
    return {
        "utility": utility, "tokens": tokens, "information_density": utility / max(tokens, 1),
        "hard_invariants_passed": structural.get("hard_invariants_passed") is True and behavioral.get("hard_invariants_passed") is True,
        "structural": dict(structural), "behavioral": dict(behavioral),
        "objective_weights": {"structural": sw, "behavioral": bw}, "optimization_spec_id": spec.id,
        "evidence_tier": "behavioral_execution", "behavioral_validation_required": False,
    }


def _evaluate(text: str, check: Mapping[str, Any]) -> tuple[bool, dict[str, Any]]:
    kind, lowered = str(check["kind"]), text.casefold()
    if kind in {"contains", "contains_all", "contains_any", "not_contains"}:
        values = _strings(check.get("values", [check.get("value")]))
        present = {value: value.casefold() in lowered for value in values}
        passed = ({"contains": len(values) == 1 and all(present.values()),
                   "contains_all": bool(values) and all(present.values()),
                   "contains_any": bool(values) and any(present.values()),
                   "not_contains": not any(present.values())})[kind]
        return passed, {"present": present}
    if kind == "regex":
        pattern = str(check.get("pattern", ""))
        matched = bool(pattern) and re.search(pattern, text, re.I | re.S) is not None
        return matched, {"pattern": pattern, "matched": matched}
    count, limit = len(text.split()), int(check.get("value", -1))
    return (count <= limit if kind == "max_tokens" else count >= limit), {"token_count": count, "limit": limit}


def _scope(text: str, raw: Any) -> str:
    if raw is None:
        return text
    heading = str(_mapping(raw, "scope").get("section", "")).strip()
    match = _section_match(text, (heading,)) if heading else None
    return match.group(0) if match else (text if not heading else "")


def _upsert_section(text: str, heading: str, content: str, aliases: tuple[str, ...], after: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "-", heading.casefold()).strip("-")
    start, end = f"<!-- prompt-opt:{key}:start -->", f"<!-- prompt-opt:{key}:end -->"
    rendered = f"{start}\n{heading}\n\n{content}\n{end}\n\n"
    managed = re.search(rf"(?ms)^{re.escape(start)}\s*$.*?^{re.escape(end)}\s*$\n*", text)
    if managed:
        return text[:managed.start()] + rendered + text[managed.end():]
    match = _section_match(text, (heading, *aliases))
    if match:
        return text[:match.start()] + rendered + text[match.end():]
    if not after or after not in text:
        raise ValueError(f"cannot insert section {heading!r}: anchor not found")
    return text.replace(after, after + "\n\n" + rendered, 1)


def _section_match(text: str, headings: tuple[str, ...]) -> re.Match[str] | None:
    for heading in headings:
        level = len(heading) - len(heading.lstrip("#"))
        if level:
            match = re.search(rf"(?ms)^{re.escape(heading)}\s*$.*?(?=^#{{1,{level}}}\s|\Z)", text)
            if match:
                return match
    return None


def _set_frontmatter(text: str, key: str, value: str) -> str:
    match = re.match(r"(?s)\A---\s*\n(.*?)\n---", text)
    if not match:
        raise ValueError("metadata revision requires YAML frontmatter")
    body, pattern = match.group(1), rf"(?m)^(\s*{re.escape(key)}\s*:\s*).*$"
    revised = re.sub(pattern, rf'\g<1>"{value}"', body, count=1) if re.search(pattern, body) else body.rstrip() + f'\n  {key}: "{value}"'
    return text[:match.start(1)] + revised + text[match.end(1):]


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _strings(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    values = (value,) if isinstance(value, str) else tuple(value) if isinstance(value, (list, tuple)) else None
    if values is None or any(not isinstance(item, str) or not item for item in values):
        raise ValueError("expected a string or list of non-empty strings")
    return values


def _newline(text: str) -> str:
    return text.rstrip() + "\n"


def _resolve_assets(raw: Any, base: Path) -> Any:
    """Resolve declared text assets locally; paths may not escape the spec directory."""
    if not isinstance(raw, Mapping):
        return raw
    copied = dict(raw)
    revision = copied.get("revision")
    if not isinstance(revision, Mapping):
        return copied
    revised = dict(revision)
    if "document_file" in revised:
        if "document" in revised:
            raise ValueError("revision cannot set both document and document_file")
        revised["document"] = _read_local_asset(base, str(revised.pop("document_file")))
    sections = revised.get("sections")
    if isinstance(sections, list):
        resolved_sections = []
        for raw_section in sections:
            section = dict(_mapping(raw_section, "revision section"))
            if "content_file" in section:
                if "content" in section:
                    raise ValueError("section cannot set both content and content_file")
                section["content"] = _read_local_asset(base, str(section.pop("content_file")))
            resolved_sections.append(section)
        revised["sections"] = resolved_sections
    copied["revision"] = revised
    return copied


def _read_local_asset(base: Path, relative: str) -> str:
    if not relative:
        raise ValueError("optimization asset path must not be empty")
    root, target = base.resolve(), (base / relative).resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"optimization asset escapes spec directory: {relative}")
    return target.read_text(encoding="utf-8")
