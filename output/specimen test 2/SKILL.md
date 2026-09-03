---
name: specimen-prompt-eval
description: A specialized child of the specimen skill for prompt-comparison experiments. It scores, ranks, attributes, and selects among a set of prompt candidates with the prompt_optimization toolkit, then produces an evidence-gated writeup that never claims a prompt "works better" without saying on what evidence. Use when the user wants to compare prompt formulations or prompt corpora AND wants a specimen-style report documenting them. This is the second test iteration; confirm the result before relying on it.
---

# specimen-prompt-eval

A **specimen** is a representative sample submitted as evidence. The parent
`specimen` skill turns a project into an evidence-gated preprint: it orients
against a project and reports how much of its value proposition is backed by
evidence versus asserted. This is a **specialized child skill**, not an
enhanced replacement. Where the parent asks *"what evidence does this project
have?"*, this child asks *"which prompt candidate performs best, and on what
evidence?"* It uses the `prompt_optimization` toolkit as its measurement
pipeline.

The parent-child relationship is the load-bearing frame:

```text
specimen
    general evidence-gated research writeup
        |
        └── specimen-prompt-eval
                specialized prompt-comparison experiment
```

If only one skill is loaded, prefer the parent. Load this child only when the
object of study is a set of prompt candidates and the question is which one the
evidence favors.

## The one rule that matters more than the others

**Never claim a prompt "works better" without saying on what evidence.** Every
ranking and attribution in this skill is produced by a *research scaffold* —
deterministic content-derived embeddings scored against a synthetic attractor
model. The scaffold validates ordering logic, not real-model behavior. Its
verdicts are **candidate hypotheses**, not conclusions. Before recommending a
prompt change as if proven, separate *measured* from *asserted*.

Two invariants sharpen this rule:

> **Behavioral performance must dominate embedding similarity.**

Cosine closeness to a hand-defined target is a *synthetic alignment signal*, a
convenient ordering heuristic for the machinery. It is not evidence of
behavioral equivalence. A candidate may be geometrically near the target yet
behaviorally inert, or far yet behaviorally decisive. Never let the scaffold's
alignment score outrank a real behavioral measurement.

> **Do not select any candidate that fails mandatory behavioral constraints,
> regardless of score.**

Some dimensions are hard gates — critical invariants with a cap `D_critical ≤
δ_critical` — not tradeable objectives. Pareto efficiency must not be used to
rescue a candidate that breaks one. If a candidate violates a hard constraint,
it is out, even if it sits on the efficient frontier.

And the parent's deeper principle survives intact in this child:

> **Absence of evidence is itself a reportable result.**

If no candidate survives the distortion bound, the correct output is *"no
supported improvement was found"* — a finding, not a failure of the writeup.

## Pipeline

The pipeline has a deliberate architectural split. The synthetic scaffold
**proposes**; a real held-out evaluator **disposes**; only then does a claim
exist.

```text
     synthetic optimizer proposes
                    │
                    ▼
   candidate generation / ranking      (Orient → Score → Attribute → Select)
                    │
                    ▼
        REAL held-out model evaluation
                    │
                    ▼
                   claim
```

1. **Orient.** Take the prompt candidates: a list of prompt strings, or a
   project directory of candidate files. Define the target behavior the user
   cares about; if none is given, state that a default target is assumed.
2. **Score.** `prompt-opt scan <paths...>` embeds and scores each candidate
   against the target: `target_activation`, `reliability`, `distortion`,
   `off_target`, `uncertainty`, and `score`. The `synAlign` column is the
   **synthetic alignment signal** — cosine to the hand-defined target. Treat it
   as machinery ordering only; it is NOT behavioral evidence. Use
   `prompt-opt scan --json <paths...>` for machine-readable output, and
   `--d-model N` matching the working dimension (default 32).
3. **Attribute.** For variable components, ask *which part drove the
   difference*: `shapley_values`, `interaction_effect`,
   `causal_deletion_effect`, `directional_projection`. These estimators are
   **value-function agnostic**: they accept any value function you supply, but
   their interpretation is only as valid as the supplied evaluator. Shapley
   over the synthetic cosine score is not Shapley over held-out architectural
   behavior — say which value function produced any attributed claim.
4. **Select.** Apply **hard gates first**: `prompt-opt plan --gate
   KEY=BOUND <paths...>` (repeatable, with `--gate-op max|min`). Candidates
   that break a mandatory constraint are excluded unconditionally — score
   cannot rescue them. On the survivors, `prompt-opt plan` returns the
   rate-distortion frontier, the Pareto-non-dominated set, and a recommended
   next experiment (highest uncertainty-weighted potential gain). Prefer the
   cheapest Pareto point meeting the distortion target over the globally
   top-scoring one.
5. **Verify (synthetic).** Re-run the scaffold winner with varied `--seed` and
   raised `--samples`; confirm ordering is stable across seeds. This still
   validates the machinery, not the model.
6. **Verify (real).** Run the surviving candidates against a **real held-out
   evaluator** — the actual model, on unseen examples, under the behavioral
   constraint. This step is required before any performance claim. It is not a
   formality; it is where "scaffold forecast" becomes "measured result."
7. **Compile and hand off.** Produce the specimen writeup, separating
   **verified measurements** from **scaffold forecasts** in the Evaluation
   Status section. Say plainly where the scaffold stops and what a real
   model-run must measure next. If the real evaluator was not run, the writeup
   says so and the claim language stays provisional.

## Selecting when there is no winner

Selection is not required to produce a winner. The pipeline must be honest in
the negative case, in the parent skill's spirit:

- If the synthetic scaffold yields no candidate within the distortion bound,
  report **"no supported improvement was found."** Do not force a choice.
- If every candidate passes the scaffold but none passes the real held-out
  evaluator, the writeup reports the mismatch as a finding — the synthetic
  signal let them through; the behavioral test did not confirm them.
- Do not paper over a gated-out candidate because it looks efficient. The gate
  report (`blocked`) is part of the evidence, not an appendix to apologize for.

## Worked measurement this skill ships with

This iteration was exercised against the parent `Z:\Specimen` project, so the
output folder contains its scan/plan artifacts (`scan.*`, `plan.*`,
`plan-partial-gate.*`, `plan-strict-gate.*`). The scaffold's verdict on that
run, stated as a hypothesis only:

- **Scaffold winner:** `Z:/Specimen/README.md` — lowest distortion (0.801) and
  lowest measured cost (303 tokens) at every point on the rate-distortion
  frontier, and the sole survivor of a partial hard gate at
  `distortion=0.80065`. It is the Pareto-cheapest point, which is why the
  reference pipeline prefers it over the globally higher-activation files.
- **Pareto survivors (3):** `README.md`, `references/section-template.md`,
  `scripts/arxiv_lookup.py`.
- **Strict-gate case:** at `distortion=0.77` no candidate survives; the plan
  correctly reports *no supported improvement is claimed*.
- **Status:** a candidate hypothesis for the real held-out evaluator. These
  numbers are scaffold forecasts; they carry no behavioral claim by themselves.

## Naming and scope

This skill is named `specimen-prompt-eval` to make the parent/child relation
explicit: it inherits the evidence-gated philosophy of `specimen` and changes
the measurement method (prompt comparison via the `prompt_optimization` toolkit).
It is a child skill, not a replacement.

## What this skill is (still) not

- **Not a production claim.** `synAlign`/`score`/`distortion` are synthetic
  ordering signals. Real held-out evaluation is required before any claim.
- **Not a real tokenizer.** "Tokens" is a tokenizer-free estimate — enough for
  ranking, not for counting real model tokens.
- **Not an automation of judgment.** It ranks and attributes on evidence, then
  hands the decision back to a human.
- **Not the parent skill.** It does not produce a general evidence-gated
  preprint about a whole project; it produces the prompt-comparison slice of
  one. When in doubt, load `specimen` instead.