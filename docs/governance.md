# Governance

Last verified: 2026-08-29. Versioning, contamination, and retirement policy
for the benchmark described in `docs/bcso-bench.md`. This is
process documentation, not code — see `capability.provenance` for the typed
records (`BenchmarkVersion`, `ProvenanceRecord`, `content_hash`) this policy
governs.

## Versioning

`capability.provenance.CURRENT_BENCHMARK_VERSION` independently versions
five components: `task_suite`, `rubric`, `judge_profile`, `reference_corpus`,
`optimizer_protocol`. Bump the relevant component's version string whenever
a change would make results incomparable to a prior run — e.g. adding a new
required rubric criterion, changing a hard-invariant's minimum pass rate, or
adding/removing a reference-corpus specimen. Results across incompatible
major versions of any one component should not be directly compared; a
report should always carry the `BenchmarkVersion` (and a `ProvenanceRecord`)
that produced it.

Every result bundle (skill text + contract + scenarios + config) should be
identified by `capability.content_hash()` so two runs can be checked for
byte-identical inputs without re-diffing the whole payload.

## Scenario/contract status

Every `Scenario` and `IntentContract` may carry a `metadata["status"]` tag
with one of four values — an additive convention (no schema change), not
yet enforced by code:

- `PRIVATE` — held out, never exposed in scan/plan/search output.
- `ACTIVE` — in normal rotation across `D_fitness`/`D_select`.
- `EXPOSED` — has appeared in printed output, a report, or been inspected
  by someone iterating on the optimizer or the skill; no longer trustworthy
  as a held-out signal.
- `RETIRED` — no longer used for scoring; kept for provenance only.

**The rule that matters**: once a `D_test` scenario has been repeatedly
inspected while modifying BCSO itself, it has become `D_dev` in practice —
re-tag it `EXPOSED` (or `RETIRED`) rather than continuing to treat it as a
pristine one-shot holdout. This project's `search.loop.run_bcso` already
enforces sealed-`D_test` structurally (one evaluation, after freeze) for a
single run; this tagging convention is what extends that guarantee across
*repeated* runs and sessions, which code alone cannot track.

## Contamination

For any scenario or reference specimen sourced from outside this repo
(a public benchmark, a shared corpus), record known exposure risk in its
`metadata["contamination_note"]`. This does not prove or disprove
contamination — it documents uncertainty rather than silently assuming
none. See `docs/benchmark-card.md`'s "Contamination risks" section
for the current corpus's status (not yet assessed; low prior risk since the
five specimens are this project's own working files, not scraped from a
public benchmark).

## Dynamic regeneration

New scenarios (from failure clusters, new skill families, adversarial
generators, or human submissions) should enter a *future* benchmark version,
never the currently-active `D_test`/`D_select` split being scored — mixing
them in destroys comparability with prior runs. This project does not yet
have an automated scenario-generation pipeline; when one exists, its output
should land in `D_author` for human review before promotion to `D_fitness`.

## Retirement

A scenario set's lifecycle mirrors the status tags above:
`PRIVATE → ACTIVE → EXPOSED → RETIRED`. There is no automatic transition —
retiring a scenario set is a deliberate editorial decision (typically: it
has been inspected too many times to trust as a holdout, or the skill
family it covers no longer exists), recorded by updating the relevant
fixture's `metadata["status"]` and noting the change in this file's history
below.

## Independent calibration protocol (planned, not yet executed)

**The risk**: circular benchmark construction. This project's synthetic
scoring pipeline was originally developed and manually calibrated against
one specimen (`project-artifact` — see `docs/benchmark-card.md`'s
contamination-risk note). If BCSO's metric definitions were shaped by that
one skill's traits, and the benchmark later scores that skill (or things
like it) favorably, the benchmark has its thumb on the scale — not
evidence, a mirror.

**The fix**: demote the original scan from evidence to inspiration, and
rebuild calibration independently, in phases:

1. **Freeze measurement definitions before collecting calibration results.**
   Decide what `U`, `R`, `A_prec`, `A_rec`, invariant adherence, rate-
   distortion behavior, and optimization resistance mean from theoretical
   reasoning and published evaluation practice — not because one specimen
   happened to score a certain way.
2. **Discard the old numeric calibration; keep the concepts.** Any specific
   value produced by the synthetic pipeline to date (a reliability number, a
   distortion number, a rewrite's word count) has zero authority as a
   calibration target. It was always labeled synthetic/non-empirical; that
   label was correct.
3. **Build an independent reference corpus before running BCSO on it.**
   Stratify across sources and skill families — official vendor skills,
   respected open-source agent instructions, manually authored high-quality
   skills, deliberately mediocre skills, deliberately corrupted skills — and
   select them without looking at BCSO scores.
4. **Blind the benchmark where possible.** Evaluators see `S017`, not
   "official Anthropic skill X" — authority/position bias is a documented
   LLM-judge failure mode (see `bcso-bench.md` §7's judge-calibration
   discussion), and blinding is one of the cheaper defenses against it.
5. **Include negative controls.** Take good skills and deliberately damage
   them (delete a hard invariant, inject a conflicting instruction,
   over-compress, broaden a trigger past its intent, add irrelevant
   verbosity) — see `contracts.DefectType` / `search.mutate.inject_defect`,
   already implemented for exactly this. BCSO-Bench should reliably score
   these worse; if it can't, it isn't measuring what it claims.
6. **Include positive controls.** Construct cases with a known, meaningful
   fix (restore a missing mandatory step, repair a broken schema
   requirement). The benchmark should detect the gain.
7. **Use baselines that did not influence benchmark design.**
   `search.baselines.BASELINES` already names `no_skill`/`original`/
   `simple_rewrite`/`random_mutation`/`compression_only`/
   `evolution_no_gradient`/`textual_gradient` alongside `full_bcso` for
   exactly this reason — if BCSO only beats the baseline whose assumptions
   inspired it, that's a red flag, not a result.
8. **Pre-register before looking at reference results.** Freeze scoring
   equations, stopping rules, acceptable evaluator disagreement, the
   statistical test, minimum meaningful improvement `Δ_min`, and what counts
   as success, before the calibration run happens.
9. **Seal the final benchmark after the framework is frozen.** Build/tune
   BCSO using development tasks; once frozen, commission or generate a *new*
   task suite nobody used while designing it. That new suite is `D_test` in
   the real sense — see §2's data hierarchy — and is the cleanest available
   defense against the origin-story bias in point 1.
10. **Make reproducibility part of validity, not optional polish.** Pin
    model version, prompts, temperature, tokenizer, evaluator, seeds, task
    hashes, and benchmark version (`capability.provenance`) for every
    reference-corpus run.

**What "mature" should not mean**: "looks like `project-artifact`."
Maturity (`capability.maturity.classify_maturity`) is defined independently
via its own gates — capable, robust, correctly scoped, efficient,
generalizing, optimization-saturated — and only *then* does it make sense to
ask where any particular specimen, including `project-artifact`, happens to
land. The legitimizing result would be BCSO correctly identifying a
weakness in an official, well-regarded skill with a reproducible, smaller
counter-example — not BCSO agreeing with every skill it was partly designed
around.

This protocol is not automated by any code in this repo today. It requires
a real reference corpus beyond the current four/five specimens, real human
or model judgments outside this pipeline, and a deliberate pre-registration
step this project has not yet taken.

## History

- **2026-08-29** — Governance policy introduced alongside the BCSO-Bench
  adoption (`docs/bcso-bench.md`). No scenario has been
  retired yet; the reviewed fixtures in `tests/fixtures/` are `ACTIVE`.
  Independent calibration protocol added after identifying that the
  synthetic scoring pipeline's origin (calibrated against `project-artifact`)
  creates a circularity risk — see the section above and
  `docs/benchmark-card.md`'s contamination-risk note.
