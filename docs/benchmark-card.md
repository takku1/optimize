# BCSO-Bench card

Last verified: 2026-08-29.

## Purpose

BCSO-Bench evaluates natural-language skill programs as behavioral policies.
It asks whether a skill activates in the right situations, satisfies a declared
capability contract, remains robust under controlled transformations, and can
be shortened or changed without violating hard constraints.

## Implemented measurement boundary

The repository implements contract and scenario schemas, evaluator seams,
deterministic and statistical metrics, candidate comparison, promotion,
lineage, provenance, maturity, and claim verification. The built-in synthetic
attractor backend and default mutation operators demonstrate these mechanics;
they do not measure production-model behavior.

Real judgments may enter through rubric files, callable evaluators, paired
scenario results, or the programmatic empirical-run API. The package ships no
vendor-specific network adapter.

## Corpus and coverage

Four official skill specimens (`claude-md-management`, `hookify`,
`frontend-design`, and `project-artifact`) were used during early development.
An independently maintained `architectural-reasoning` skill supplies the first
contract/capability/scenario fixture set. The suite contains four scenarios and
only 53.3% of the taxonomy coverage tracked by the report command; important
negative, ambiguous, noisy, adversarial, and impossible-constraint cells are
missing.

This corpus is far below the 32-cell coverage target in the full specification.
Reference-envelope and cross-skill results are illustrative only.

## Empirical evidence

One real-model pilot was completed on 2026-08-29:

- two `architectural-reasoning` skill versions;
- four scenarios;
- one rollout per version/scenario;
- deterministic checks and blinded rubric-grounded judging;
- real `compare_contract_results` and promotion evaluation.

The promotion verdict was `REJECTED` because both versions failed the same
hard-invariant floor. The candidate nevertheless led on measured utility and
token cost. See
`output/claude skills/architectural-reasoning/empirical-run-2026-08-29/REPORT.md`.

The subsequent damaged-skill and no-skill controls showed that the targeted
binary invariants were also satisfied without the intended skill behavior.
That null effect exposes weak benchmark resolution for the scenario rather
than proving equivalence. See
`output/claude skills/architectural-reasoning/negative-control-2026-08-29/REPORT.md`.

## Contamination risks

- `project-artifact` influenced manual calibration of the original synthetic
  pipeline, so its synthetic results are not independent evidence.
- The architectural-reasoning scenarios were derived from that skill's own
  evaluation suite. They are grounded but not an independent task population.
- The real-model pilot is too small for stable variance, power, or transfer
  estimates.
- The same project produced the tooling and interpreted the pilot; independent
  calibration and reproduction remain outstanding.

## Unsupported claims

Current evidence does not support claims of:

- general improvement of real prompts or skills;
- cross-model or cross-domain transfer;
- calibrated human/judge agreement;
- statistically powered promotion rates;
- semantic correctness of rule-based mutations;
- a trained neural optimizer or reliable learned transition model.

## Promotion policy

Synthetic-only evidence can produce a candidate, never a validated
improvement. Validation requires a versioned contract, held-out paired results,
hard-invariant success, an uncertainty-aware non-inferiority result, and clear
provenance. See [governance.md](governance.md).

## Next validity milestone

Improve scenario resolution using graded or more discriminating invariants,
demonstrate skill-attributable margin against no-skill and damaged-skill
controls, independently calibrate the evaluator, and only then fund repeated
rollouts or a broader multi-model study.

## Version history

- **2026-08-29 (current)** — reconciled the card with the completed empirical
  pilot and negative-control follow-up.
- **2026-08-29 (initial)** — adopted the BCSO-Bench contract, taxonomy,
  evaluator-stack, and maturity framing. The superseded status is archived in
  `docs/archive/2026-08-29-bcso-bench-adoption/`.
