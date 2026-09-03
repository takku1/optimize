---
name: specimen test 1
description: A variant of the specimen skill that gathers evidence with the prompt-optimization pipeline — score, rank, attribute, and select among a set of prompt candidates, then produce an evidence-gated writeup that never claims more than the measured comparisons support. Use when the user wants to compare prompt formulations or prompt corpora and also wants a specimen-style preprint/report documenting them. This is a test variant of Specimen; confirm the result before relying on it.
---

# specimen test 1

A **specimen** is a representative sample submitted as evidence. This is a test
variant of the `specimen` skill. Where the parent skill orients against a
project and reports how much of its value proposition is backed by evidence,
this variant orients against a **set of prompt candidates** and reports how much
of a "this prompt is better" claim the *comparison evidence* actually supports —
and it uses the `prompt_optimization` toolkit as its measurement pipeline.

This is explicitly a **test**: it exercises the pipeline end-to-end on candidate
prompts. Treat its output as experimental until reviewed, not as the frozen
child skill.

## The one rule that matters more than the others

**Never claim a prompt "works better" without saying on what evidence.** Every
ranking and attribution in this variant is a *measurement on a research
scaffold* (deterministic content-derived embeddings over a synthetic attractor
model). It validates ordering logic, not real-model behavior. Before
recommending a prompt change as if proven, separate *measured* from *asserted*.
A gap is a finding, not a defect — report it.

## Pipeline

1. **Orient.** Take the prompt candidates: a list of prompt strings, or a
   project directory of candidate files. Define the target behavior the user
   cares about; if none is given, state that a default target is assumed.
2. **Scan (evidence).** Embed and score each candidate against the target:
   - `prompt-opt scan <paths...>` — per-candidate `similarity` (cosine to
     target), `target_activation`, `reliability`, `distortion`, `off_target`,
     and `score`. Ordered by `similarity`, most-aligned first.
   - `prompt-opt scan --json <paths...>` for machine-readable output.
   - `--d-model N` must match the working dimension (default 32).
3. **Attribute.** For variable components, ask *which part drove the
   difference*: `shapley_values`, `interaction_effect`,
   `causal_deletion_effect`, `directional_projection`. These work on any value
   function you supply, so they are model-agnostic.
4. **Select.** `prompt-opt plan <paths...>` returns a rate-distortion frontier,
   the Pareto-non-dominated candidates, and a recommended next experiment
   (highest uncertainty-weighted potential gain). Prefer the cheapest Pareto
   point meeting the distortion target over the globally top-scoring one.
5. **Compile and verify.** Re-run the winner with varied `--seed` and raised
   `--samples`; confirm the ordering is stable across seeds. Produce the
   specimenn writeup, and in it separate **verified measurements** from
   **scaffold forecasts**.
6. **Handoff.** Say plainly that real-model / held-out evaluation is required
   before any production performance claim, and where the scaffold stops.

## Naming and scope

This test variant is named `specimen test 1` to distinguish it from the parent
`specimen` skill and from later test variants. It is a variant, not a
replacement: it shares the evidence-gated philosophy but uses a different
measurement method (prompt comparison via the `prompt_optimization` toolkit).

## What this test variant is (still) not

- **Not a production claim.** `similarity`/`score` are ordering signals on a
  synthetic scaffold; real-model evaluation is required before any claim.
- **Not a real tokenizer.** "Tokens" is a tokenizer-free estimate — enough for
  ranking, not for counting real model tokens.
- **Not an automation of judgment.** It ranks and attributes on evidence, then
  hands the decision back to a human.
