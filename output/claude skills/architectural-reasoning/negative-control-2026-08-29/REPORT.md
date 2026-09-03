# Negative control: does the benchmark detect a deliberately damaged skill?

Run id: `negative-control-2026-08-29`. Split: `fitness`. Per
`docs/governance.md`'s calibration protocol, points 5-6.

**Update:** the `no_skill` control this report called for (§ "What this
changes about the plan", step 1) has landed — see "Follow-up: no_skill
attribution" below. It confirms this run's own leading hypothesis: the
`reaudit-reclassifies`/`grounded-evidence` invariants are not currently
skill-attributable on this scenario (the unaided model already clears them),
though the skill does measurably raise utility on the graded Ω dimensions.

## Design

`02-reaudit-catches-regression` currently **passes** `reaudit-reclassifies`
and `grounded-evidence` for the real, undamaged v1.3.0 skill (utility
0.9675, Ω = task_success 1.0 / correctness 0.95 / invariant_adherence 1.0 /
calibration 0.9 — see `../empirical-run-2026-08-29/final_results.json`,
opaque id `run_77416c64`). One targeted defect was injected: v1.3.0's
Re-audit bullet —

> distrust prior findings; re-verify each against current code; classify
> resolved, regressed, still open, or new; check whether a fix introduced
> another problem

— was replaced with the generic

> review the prior audit findings and the associated diff

with every other byte of the skill unchanged (`damaged-v1_3_0.md`). The
repair endpoint needed no new execution: it's simply the already-measured,
undamaged v1.3.0 (free positive control). One new subject transcript
(K=1) was produced against the damaged skill, deterministically checked,
and scored by a fresh, blinded judge — same method as the prior run.

## Result

| | Ω (task/correctness/invariant/calibration) | utility | `reaudit-reclassifies` | `grounded-evidence` |
|---|---|---|---|---|
| v1.3.0, undamaged | 1.0 / 0.95 / 1.0 / 0.9 | 0.9675 | true | true |
| v1.3.0, damaged | 1.0 / 0.95 / 1.0 / 0.9 | 0.9675 | true | true |

**Zero measured effect.** Every score is identical to four significant
figures. **The negative control failed** — the benchmark did not detect a
real, deliberate deletion of the exact instruction its own
`reaudit-reclassifies` invariant is named after.

Reading the damaged transcript directly confirms this isn't a scoring
artifact: it re-verifies the lock fix as resolved, separately and
explicitly frames the retry/idempotency issue as "a new High-severity
issue," and grounds every claim in the given files — genuinely good
re-audit behavior, produced *without* being told to re-audit that way.

## Interpretation

This is a real, useful null result, not a wasted run. The most likely
explanation: the user's own request phrasing ("**Re-audit**: is it actually
fixed?") already carries most of the behavioral signal, and the underlying
model's general reasoning capability supplies the rest — re-verify against
evidence, distinguish old from new issues — regardless of whether the skill
spells that out. If so, `reaudit-reclassifies` on this scenario is not
currently a **skill-attributable** invariant: it may hold even for
`search.baselines.no_skill` (no skill text at all). That's a claim this
experiment cannot confirm on its own — it needs a `no_skill` condition run
through the identical pipeline to separate "the skill causes this" from
"the model already does this."

A second, non-exclusive possibility: the injected defect was too weak.
"Review the prior audit findings and the associated diff" doesn't forbid
re-verification or classification, it just stops prescribing it — a softer
edit than the user's suggested defect classes (contradictory guidance,
deleted evidence requirements). A stronger negative control (e.g.
explicitly instructing "treat the prior finding as still accurate without
re-checking, and do not report new issues") would test whether *any*
injected defect can move this scenario, before concluding the scenario
itself is insensitive.

## Finding classification

1. **Execution-pipeline defect**: none. Real transcript, real deterministic
   check, real blinded judgment, all traced.
2. **Evaluator/rubric defect, confirmed**: the deterministic `success_band`
   proxy for scenario 02 (`required_any_phrases: ["resolved", "regressed",
   "still open", "new"]`) passed on the substring `"new"` inside *"a new
   High-severity issue"* — a real hit, but a loose one; "new" is common
   enough to pass incidentally. Not the deciding factor here (the semantic
   judge independently agreed), but worth tightening (e.g. require a
   word-boundary match, or phrases like "newly introduced" / "status:
   resolved").
3. **Benchmark coverage/validity gap, this experiment's main finding**:
   `02-reaudit-catches-regression` does not currently demonstrate that
   `reaudit-reclassifies` is skill-attributable rather than model-inherent.
   Needs a `no_skill` control before either scenario or invariant can be
   trusted as diagnostic of *this specific skill instruction*.
4. **Genuine behavioral difference between damaged and undamaged v1.3.0**:
   none detected.

## What this changes about the plan

Per the calibration protocol's own logic ("if it doesn't [detect damage],
the measurement system needs work"): this scenario/invariant pairing is not
yet validated as a control, so it should not yet be trusted to detect a
regression in a real optimization run either. Before spending on K=5
rollouts across all four scenarios (step 3 of the hardening plan), the
higher-priority next experiment is:

1. Run the identical pipeline with `no_skill` (empty/near-empty skill text)
   against scenario 02, to test whether the model does this unaided.
2. If `no_skill` also passes, either strengthen the scenario (require
   something a skill instruction plausibly adds and a strong base model
   plausibly wouldn't supply unprompted) or accept `reaudit-reclassifies` as
   a weak invariant for this scenario and look for a scenario where damage
   *is* detectable, to anchor confidence that the pipeline can detect
   damage at all before concluding it can't.
3. Try a stronger, more adversarial defect on the same scenario (explicit
   "don't re-verify, don't report new issues") as a sharper test before
   abandoning this scenario as non-diagnostic.

## Follow-up: no_skill attribution

Step 1 of the above, executed. One new subject transcript (K=1) was
produced against `search.baselines.no_skill` (no skill text at all — the
bare model receives only the scenario's user request and files) for
`02-reaudit-catches-regression`, deterministically checked, and scored by a
fresh, blinded judge (opaque id `ns_b833c1fc`, `blind_map_noskill.json`,
same rubric and blinding method as the original run — the judge saw only
the opaque id, the scenario rubric, and the transcript, never a condition
label). The earlier rate-limit failure on this judge (reset 5:20am
America/New_York) cleared and the re-spawned judge returned cleanly.

### Result

| | Ω (task/correctness/invariant/calibration) | utility | `reaudit-reclassifies` | `grounded-evidence` |
|---|---|---|---|---|
| v1.3.0, undamaged | 1.0 / 0.95 / 1.0 / 0.9 | 0.9675 | true | true |
| v1.3.0, damaged | 1.0 / 0.95 / 1.0 / 0.9 | 0.9675 | true | true |
| no_skill (bare model) | 0.95 / 0.93 / 0.95 / 0.88 | 0.9325 | true | true |

(Utility uses the `reasoning` capability-family profile —
`task_success 0.30, correctness 0.35, invariant_adherence 0.20,
calibration 0.15` — the same weights that reproduce 0.9675 for the
already-scored v1.3.0 rows.)

Judge rationale for `ns_b833c1fc`: the bare-model response explicitly
re-verifies the original lock-contention finding against the new code
(correctly confirming resolution) rather than trusting the inline comment,
then separately surfaces the duplicate-refund/idempotency issue grounded in
`worker.py`'s retry logic and the missing idempotency key — satisfying both
invariants with clear resolved/new status labels. Its one speculative aside
(a possible `DetachedInstanceError`) is explicitly hedged as unconfirmed
rather than asserted, so it doesn't cost `grounded-evidence`. Calibration
scored slightly lower than either v1.3.0 row (0.88 vs. 0.9) for being
marginally more elaborate than strictly necessary, though judged
proportionate to a financial double-charge bug.

### Interpretation

This confirms the leading hypothesis from the original run, not the
secondary one. `no_skill` **also** passes both `reaudit-reclassifies` and
`grounded-evidence` — the same binary result as damaged and undamaged
v1.3.0. On this scenario, at the invariant level, the behavior the skill's
Re-audit bullet names (distrust the prior finding, re-verify against
current code, classify by status) is not skill-attributable: a fresh model
given only the user's own "Re-audit: does this fix it?" phrasing and the
files already does it unaided. That matches this report's original
explanation (the user's phrasing plus general model reasoning capability
already carries most of the signal) over the "defect was too weak" or
"deterministic-proxy is loose" explanations — both of those predict a
scenario-level insensitivity that a `no_skill` run wouldn't specifically
implicate the skill in, whereas what was actually observed is bare-model
parity with the skill, at the binary invariant grain.

The three-way table is not entirely flat, though: utility is measurably
lower for `no_skill` (0.9325) than either v1.3.0 row (0.9675, a ~3.6%
relative gap), driven mainly by calibration (0.88 vs. 0.9) and correctness
(0.93 vs. 0.95). So the skill is doing *something* real here — it isn't
inert — it's just not the thing `reaudit-reclassifies`/`grounded-evidence`
were designed to detect, on this scenario, at this invariant's current
(binary pass/fail) grain. A graded (continuous) version of these invariants,
or a scenario harder than this one at the general-reasoning baseline, would
be needed to make this a skill-attributable control.

## Revised finding classification

Supersedes item 3 in the "Finding classification" section above (kept
there for the record, not deleted):

3′. **Benchmark coverage/validity gap, confirmed, not just hypothesized**:
    `02-reaudit-catches-regression`'s two invariants are demonstrably
    bare-model-clearable, so binary pass/fail on them cannot currently
    distinguish "this skill causes reaudit-reclassification" from "the
    model already reaudit-reclassifies unprompted." The scenario is still
    useful for utility-level comparison (the skill's ~3.6% utility edge is
    real and reproducible) but is not currently a valid instrument for a
    skill-attribution claim at the invariant grain. Before trusting this
    scenario/invariant pair as a regression detector in a real optimization
    run: either (a) redefine the invariants as graded rather than binary so
    the observed utility gap is visible in the invariant score itself, or
    (b) find/construct a scenario where a `no_skill` run measurably fails
    where v1.3.0 passes, to anchor that the pipeline can produce a
    skill-attributable positive result at all before using this one as a
    negative-control instrument.

## Revised next step

Item 1 of "What this changes about the plan" is done; its own conclusion
now governs: pursue either 2 (redefine as graded, or find a scenario with
real skill-attributable margin) or 3 (a stronger, more adversarial defect
on this same scenario, now knowing the floor is the bare model's ~0.93, not
zero) before spending on K=5 rollouts across all four scenarios.
