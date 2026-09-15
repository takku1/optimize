# Calibration input

Calibration rows use JSONL so raw ratings can be appended without rewriting a
large artifact. Each row must contain the same `artifact_id`/`rater_id` grid:

```json
{"artifact_id":"S001","rater_id":"R01","clarity_definition":7,"problem_value_validity":5,"differentiation":6,"feasibility":7,"execution_completion":4,"evidence_validation":3,"risk_exposure":5,"impact_upside":6,"stage":4,"evidence_status":"INDEPENDENT","rubric_version":"0.1"}
```

The first calibration run should use blinded artifact IDs, at least two raters,
the same frozen rubric version, and a complete artifact-by-rater crossing.
Keep raw project text and identity mapping outside the repository. Do not mix
development, calibration, and sealed-test artifacts.

Run:

```bash
python scripts/analyze_calibration.py ratings.jsonl --json-out report.json
```

`example-rehearsal.jsonl` is only a mechanics fixture. Its report must never be
quoted as independent reliability evidence.
