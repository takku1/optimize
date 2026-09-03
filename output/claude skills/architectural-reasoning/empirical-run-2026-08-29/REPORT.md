# architectural-reasoning empirical evaluation: v1.2.4 vs current (v1.3.0)

Run id: `empirical-run-2026-08-29`. Split: `fitness` (first empirical development pass — not `D_test`, not final certification). Rollouts per unit: 1 (smoke pass; storage format supports more).

## What this is

The smallest legitimate real-evaluation pipeline for the two frozen skill versions on the existing 4-scenario `architectural-reasoning-v1` suite: real model execution for every transcript, blinded rubric-grounded scoring, deterministic checks where mechanically possible, real `ScenarioResult`s, and a real `PromotionVerdict` — no synthetic score treated as behavioral evidence anywhere in the chain.

## Exact commands / steps

```
# 1. Read both frozen skill versions
Read Z:\archetect\skills\architectural-reasoning\SKILL.md
Read Z:\archetect\skills\architectural-reasoning\archive\v1.2.4\SKILL.md

# 2. Freeze the run config and scenario inputs (before any execution)
output/claude skills/architectural-reasoning/empirical-run-2026-08-29/config.json
output/claude skills/architectural-reasoning/empirical-run-2026-08-29/inputs/**

# 3. Generate the sealed blind-id mapping (before any transcripts exist)
python -c "from prompt_optimization.evaluators import generate_blind_ids; ..." \
  -> judging/blind_map.json  (seed=2026829)

# 4. Execute 8 subject transcripts (2 versions x 4 scenarios x 1 rollout),
#    each a fresh Claude agent given the skill as inline instructions plus
#    the scenario request, with scenario files on disk for Read/Glob/Grep
#    (Claude Code Agent tool, subagent_type general-purpose) -> saved to
transcripts/{v1_2_4,v1_3_0}/<scenario>/rollout_01.md

# 5. Deterministic checks (word count, escalation-phrase / status-label presence)
python deterministic_checks.py -> deterministic_checks.json

# 6. 8 blinded judge agents (fresh spawns, no memory of this session, given
#    only an opaque run id + the rubric + the transcript -- never a version
#    label) -> raw scores relayed via mailbox, saved to judging/raw_scores.json

# 7. Assemble ScenarioResults, run the real library pipeline
python assemble_results.py
#    -> contracts.compare_contract_results(...)
#    -> capability.compare_versions(...)
#    -> final_results.json
```

## Run directory layout

```
empirical-run-2026-08-29/
  config.json                    # frozen before execution: versions, method, commitments
  inputs/<scenario>/...          # real files given to the 01/02 subject agents
  transcripts/{v1_2_4,v1_3_0}/<scenario>/rollout_01.md   # immutable raw outputs
  deterministic_checks.py, deterministic_checks.json
  judging/
    blind_map.json                # opaque id <-> {version:scenario:rollout}, seed 2026829
    raw_scores.json                # all 8 blinded judge outputs, verbatim
  assemble_results.py
  final_results.json               # ScenarioResults + compare_contract_results + PromotionVerdict
  REPORT.md                          # this file
```

## Results

| Scenario | Invariant(s) tested | v1.2.4 pass | v1.3.0 pass | v1.2.4 Ω (T/C/I/Cal) | v1.3.0 Ω (T/C/I/Cal) | v1.2.4 utility | v1.3.0 utility |
|---|---|---|---|---|---|---|---|
| 01-stop-when-supported | calibrated-effort, grounded-evidence | **FAIL** calibrated-effort | **FAIL** calibrated-effort | .30/.85/.30/.20 | .45/.90/.40/.20 | 0.478 | 0.560 |
| 02-reaudit-catches-regression | reaudit-reclassifies, grounded-evidence | pass | pass | 1.0/.95/1.0/.85 | 1.0/.95/1.0/.90 | 0.960 | 0.968 |
| 03a-lens-wording-security | lens-grounded-in-force | pass | pass | 1.0/.95/1.0/.85 | 1.0/.95/1.0/.90 | 0.960 | 0.968 |
| 03b-lens-wording-sociotechnical | lens-grounded-in-force | pass | pass | .95/.90/1.0/.90 | 1.0/.90/1.0/.90 | 0.935 | 0.950 |

Ω dimensions: Task_success / Correctness / Invariant_adherence / Calibration (per `evaluators.profiles`, weighted with the `reasoning` capability-family profile: .30/.35/.20/.15).

**Aggregate** (n=4 scenarios, split=fitness, not statistically powered):

| Metric | v1.2.4 (baseline) | v1.3.0 (candidate) | Δ |
|---|---|---|---|
| Mean utility | 0.833 | 0.861 | +0.028, 95% CI [0.008, 0.064] (bootstrap, n=4 — wide/uninformative at this sample size, treat as directional only) |
| Skill token cost | 1651 | 844 | −807 (−49%) |
| Mean response length | 740 words | 623 words | −117 (−16%) |
| Pareto dominance (U, R-proxy, tokens) | — | **candidate dominates** | |
| `calibrated-effort` invariant pass rate | 0.75 (3/4, vacuous-pass on 3 untested scenarios + 1 real fail) | 0.75 (same) | **no difference — both fail the same absolute floor (min 0.9) on scenario 01** |
| All other invariants | 1.0 | 1.0 | no difference |

**`PromotionVerdict`: REJECTED** — reason: `"lost a hard invariant"` (`calibrated-effort`, candidate_pass_rate 0.75 < required 0.9).

## The result is more nuanced than "REJECTED" alone suggests

`compare_contract_results` gates on whether the **candidate** clears each invariant's **absolute** preregistered floor — not on whether it regressed relative to baseline. Here, `calibrated-effort`'s floor (0.9) is failed by *both* versions, at the *identical* rate (0.75), for the *same* reason: both responses to scenario 01 (a small, low-ambiguity parameter-threading question) ran 470-580 words — several times the "~15-20 lines" the scenario expects — with unprompted Tradeoffs/Ownership/fault-containment framing a `Quick decision` response wasn't supposed to need. Both the deterministic proxy (word count vs. an escalation-phrase check) and the independent blinded judge agree on this, for both versions.

So: on every dimension that differs between the two versions (utility, cost, response length, Pareto position), v1.3.0 comes out ahead or equal. On the one dimension that blocks promotion, neither version is compliant, and v1.3.0 didn't make it worse. `REJECTED` is the methodologically honest verdict given the absolute-floor policy — but it should not be read as "v1.3.0 regressed"; it should be read as "the calibrated-effort floor isn't cleared by this skill (either version) on this scenario shape, and the tool correctly declines to certify an improvement past a floor nothing has cleared."

## Addendum (2026-08-29, benchmark hardening pass)

`contracts.compare_contract_results` now classifies each failed invariant as
``"regression"`` (baseline held it, candidate lost it) or ``"floor_not_met"``
(neither version clears it) instead of one undifferentiated "failed" flag.
Re-running `assemble_results.py` against this fix reclassifies this run's
rejection reason from the ambiguous *"lost a hard invariant"* to the precise
*"pre-existing floor not met by baseline or candidate:
[calibrated-effort] (not a candidate-caused regression)"* — confirming, with
code now, the qualitative reading already given above. See
`docs/governance.md`'s independent calibration protocol (point 8,
pre-registration) for the calibrated-effort success-band fixture that
replaces this report's ad hoc 400-word runner constant, defined in
`tests/fixtures/scenarios/architectural-reasoning-v1.json`.

## Finding classification

1. **Execution-pipeline defects**: none found. All 8 transcripts and all 8 judgments were produced, saved, and traced end-to-end without fabrication. Minor operational friction only: two judge agents' first reply attempts triggered an auto-JSON-parse validation error in the mailbox layer (unrelated to this pipeline's own logic) and self-corrected by prefixing plain text before the JSON.
2. **Evaluator/rubric defects**: the `calibrated-effort` deterministic proxy (400-word threshold, chosen before seeing any output) is a rough translation of the scenario's "~15-20 lines" language — it was never given a precise token/word definition in the scenario fixture itself. The `R` (robustness) value fed to `capability.compare_versions` here is a placeholder (min utility across the 4 scenarios), not the hierarchical-bootstrap-based robustness the BCSO-Bench spec defines — adequate for pipeline validation, not for a real robustness claim.
3. **Benchmark coverage gaps**: unchanged from before this run — 53.3% taxonomy coverage; still missing negative/ambiguous activation, noisy context, adversarial intent, conflicting/impossible constraints. This run used exactly the 4 existing scenarios, as instructed.
4. **Genuine behavioral differences observed**: v1.3.0 is ~49% cheaper in skill tokens and produced ~16% shorter responses while scoring equal-or-higher utility on every scenario (largest gap on scenario 01, still within both versions' shared failure of that scenario's compactness bar). No invariant regressed. Both versions share the same weakness on scenario 01's compactness expectation — this is a property of the skill (both versions) relative to this scenario, not something introduced or fixed by the 1.2.4 -> 1.3.0 change.

## Limitations

- **K=1 rollout per unit.** No within-version variance is estimable yet; a single unlucky/lucky generation could move any one cell. `search`/this pipeline's storage format already supports more rollouts (`rollout_02.md`, etc.) — increasing K is the natural next step, not a redesign.
- **Execution fidelity.** Subject transcripts came from a fresh Claude agent given the skill as inline instructions, not the native `~/.claude/skills/` auto-trigger mechanism. Model identity/version and sampling parameters were whatever the Agent tool's `general-purpose` subagent type resolved to at spawn time and were not independently controllable or recorded beyond "the harness's default at time of run."
- **n=4 scenarios.** The utility CI, the invariant pass-rate denominators, and any "aggregate" number here are not statistically powered — this is pipeline validation and an initial empirical comparison, not publication-grade evidence. Do not compare this run's numbers against a future, larger run as if they were on the same footing without re-checking the taxonomy coverage and sample size.
- **Absolute-vs-relative invariant gating is a real open design question**, surfaced (not resolved) by this run: `compare_contract_results` currently answers "does the candidate clear the floor," not "did the candidate regress relative to baseline." Both are defensible; this run shows they can disagree sharply. Left unchanged per the no-mid-run-tuning constraint; worth a deliberate governance decision before the next run, not a silent code change.
- **No independent calibration pass yet.** Per `docs/governance.md`'s calibration protocol, this run's rubric and thresholds came from the project's own contract/scenario design, not a pre-registered, blinded process independently validated against negative/positive controls. That protocol remains future work.

## What the next empirical experiment should be

Not a bigger version of this one yet. In priority order:

1. **K>1 rollouts** on the same 4 scenarios (say K=3) to get a first real within-version variance estimate — cheap, uses the exact same pipeline, directly answers "was scenario 01's result a fluke."
2. **Tighten the `calibrated-effort` rubric**: define "roughly 15-20 lines" as an explicit, pre-registered token/word bound in the scenario fixture itself (not a runner-script constant), ideally derived from a few independently-authored reference "good" and "bad" responses (the negative/positive-control idea from the calibration protocol) rather than one guess.
3. **Negative-control run**: use `contracts.DefectType`/`search.mutate.inject_defect` to deliberately damage one of the two versions (e.g. strip the re-audit reclassification instruction) and confirm this same pipeline reliably scores the damaged version worse — the cheapest available check that the pipeline measures what it claims to.
4. Only after 1-3: expand taxonomy coverage (negative/ambiguous activation, adversarial intent, noisy context) per the known 53.3%-coverage gap, and consider the independent-calibration-corpus work in `docs/governance.md` before treating any future run as more than a fitness-split signal.
