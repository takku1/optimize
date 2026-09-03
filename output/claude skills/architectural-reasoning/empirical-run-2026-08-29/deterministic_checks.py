"""Deterministic, mechanical checks over the 8 subject transcripts.

Run after transcripts are saved, before judging results are combined.
These are the checks that don't require semantic judgment -- word count,
literal phrase presence -- computed the same way every time given the same
input, per requirement #5 (evaluate deterministic criteria deterministically
wherever possible).
"""
import json
import re
from pathlib import Path

RUN_DIR = Path(__file__).parent
VERSIONS = ("v1_2_4", "v1_3_0")
SCENARIOS = (
    "01-stop-when-supported",
    "02-reaudit-catches-regression",
    "03a-lens-wording-security",
    "03b-lens-wording-sociotechnical",
)

ESCALATION_PHRASES = ("focused design", "full architecture")
STATUS_LABELS = ("resolved", "regressed", "still open", "new")


def word_count(text: str) -> int:
    return len(text.split())


def mentions_any(text: str, phrases: tuple) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in phrases)


def count_status_labels(text: str) -> int:
    lowered = text.lower()
    return sum(1 for label in STATUS_LABELS if re.search(rf"\b{re.escape(label)}\b", lowered))


def main() -> None:
    results = {}
    for version in VERSIONS:
        for scenario in SCENARIOS:
            path = RUN_DIR / "transcripts" / version / scenario / "rollout_01.md"
            if not path.exists():
                print(f"MISSING transcript: {path}")
                continue
            text = path.read_text(encoding="utf-8")
            entry = {
                "word_count": word_count(text),
            }
            if scenario == "01-stop-when-supported":
                entry["mentions_escalation_phrase"] = mentions_any(text, ESCALATION_PHRASES)
                entry["calibrated_effort_deterministic"] = (
                    entry["word_count"] <= 400 and not entry["mentions_escalation_phrase"]
                )
            if scenario == "02-reaudit-catches-regression":
                entry["status_label_count"] = count_status_labels(text)
                entry["reaudit_reclassifies_deterministic_proxy"] = entry["status_label_count"] >= 2
            results[f"{version}:{scenario}"] = entry

    out_path = RUN_DIR / "deterministic_checks.json"
    out_path.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {out_path} ({len(results)} entries)")


if __name__ == "__main__":
    main()
