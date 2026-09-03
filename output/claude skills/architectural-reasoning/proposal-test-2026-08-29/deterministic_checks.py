"""Deterministic, mechanical checks over this run's 8 freshly-executed transcripts.

Companion to ../empirical-run-2026-08-29/deterministic_checks.py -- same
word-count/phrase-presence approach, extended with a weak deterministic proxy
for 04-output-routing's 'used ADR vocabulary' expectation (success_band in
tests/fixtures/scenarios/architectural-reasoning-v1.json). No proxy is
defined for 03a/03b (matches the empirical run's precedent -- lens-selection
is semantic-only) or 05 (whether a claim is fabricated/attributed to an
unread reference is not mechanically checkable).
"""
import json
import re
from pathlib import Path

RUN_DIR = Path(__file__).parent

# (version, scenario) pairs actually freshly executed in this run.
UNITS = [
    ("v1_3_0", "04-output-routing"),
    ("v1_3_0", "05-reference-unavailable"),
    ("v1_3_1", "01-stop-when-supported"),
    ("v1_3_1", "02-reaudit-catches-regression"),
    ("v1_3_1", "03a-lens-wording-security"),
    ("v1_3_1", "03b-lens-wording-sociotechnical"),
    ("v1_3_1", "04-output-routing"),
    ("v1_3_1", "05-reference-unavailable"),
]

ESCALATION_PHRASES = ("focused design", "full architecture")
STATUS_LABELS = ("resolved", "regressed", "still open", "new")
ADR_VOCAB = ("context", "decision", "consequences", "forces", "options", "status")


def word_count(text: str) -> int:
    return len(text.split())


def mentions_any(text: str, phrases: tuple) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in phrases)


def count_status_labels(text: str) -> int:
    lowered = text.lower()
    return sum(1 for label in STATUS_LABELS if re.search(rf"\b{re.escape(label)}\b", lowered))


def count_adr_vocab(text: str) -> int:
    lowered = text.lower()
    return sum(1 for word in ADR_VOCAB if re.search(rf"\b{re.escape(word)}\b", lowered))


def main() -> None:
    results = {}
    for version, scenario in UNITS:
        path = RUN_DIR / "transcripts" / version / scenario / "rollout_01.md"
        if not path.exists():
            print(f"MISSING transcript: {path}")
            continue
        text = path.read_text(encoding="utf-8")
        entry = {"word_count": word_count(text)}

        if scenario == "01-stop-when-supported":
            entry["mentions_escalation_phrase"] = mentions_any(text, ESCALATION_PHRASES)
            entry["calibrated_effort_deterministic"] = (
                entry["word_count"] <= 400 and not entry["mentions_escalation_phrase"]
            )
        if scenario == "02-reaudit-catches-regression":
            entry["status_label_count"] = count_status_labels(text)
            entry["reaudit_reclassifies_deterministic_proxy"] = entry["status_label_count"] >= 2
        if scenario == "04-output-routing":
            entry["adr_vocab_count"] = count_adr_vocab(text)
            entry["output_routing_deterministic_proxy"] = entry["adr_vocab_count"] >= 3

        results[f"{version}:{scenario}"] = entry

    out_path = RUN_DIR / "deterministic_checks.json"
    out_path.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {out_path} ({len(results)} entries)")
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
