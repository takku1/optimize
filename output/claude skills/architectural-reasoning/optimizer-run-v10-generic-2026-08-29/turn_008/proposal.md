---
name: architectural-reasoning
description: Evidence-first architectural reasoning for consequential software decisions, with calibrated effort, explicit ownership, stable contracts, justified boundaries, falsifiable migration, and behavior-preserving edits. Use for subsystem boundaries, ownership, dependencies, platform design, modernization, and formal architecture work; do not use for routine isolated changes.
metadata:
  version: "1.3.2"
  based_on: "architectural-reasoning 1.3.1"
---

# Architectural Reasoning

Design from actual system forces, not a favored pattern. Produce clear ownership,
contracts, justified boundaries, explicit tradeoffs, and an incremental path from current
reality.

## Calibrate effort

- **Quick decision (default):** inspect targeted evidence, apply one primary lens and one meaningful challenge, then return a compact recommendation.
- **Focused design:** for one subsystem, boundary, or critical flow, map its owner, state, contract, dependencies, risks, and migration.
- **Full architecture:** reserve for an explicitly requested audit, formal design, or change spanning foundational subsystems.
- **Re-audit:** distrust prior findings; re-verify each against current code; classify resolved, regressed, still open, or new; check whether a fix introduced another problem.

Requested depth and output format override these defaults.

### Quick-decision completion contract

For a straightforward Quick decision, use this contract as the completion criterion, not as a suggestion:

1. Inspect only the named files and their immediate call path. Expand once only when a missing fact could reverse the recommendation or reveal a material risk.
2. Return exactly four sections, in this order: **Recommendation**, **Evidence**, **Tradeoffs**, **Next step**. Add no preamble, summary, appendix, risk register, ownership inventory, lens survey, or migration plan.
3. Put at most two bullets under each section and one claim per bullet. Use a governing lens only when it changes the recommendation; omit lens narration otherwise.
4. Keep the complete response at or below 300 words. Before sending, check the section count, bullet count, and word budget; delete repetition and non-decision-critical detail until all three limits pass.

When evidence is insufficient, name the single smallest missing fact under **Evidence** and stop. When a consequential risk makes this compact contract unsafe, state that risk and the smallest additional analysis needed; do not silently produce a longer artifact. A requested format or depth overrides this contract.## Route the output

Use the requested artifact. Otherwise default to a short decision brief with:

- **Recommendation** - the proposed decision and scope;
- **Evidence** - concrete inspected facts and verification;
- **Tradeoffs** - alternatives, sacrificed qualities, and failure modes;
- **Next step** - the smallest reversible action and its validation.

Use the requested format when one is named:

- **PR comment:** finding/consequence, exact code evidence, smallest correction, verification.
- **ADR:** `Status`, `Context`, `Forces`, `Options`, `Decision`, `Consequences`, `Validation and reversal`.
- **RFC/system design:** goals/non-goals, current system, forces, proposal, ownership/contracts, cross-cutting behavior, alternatives, migration, validation, open decisions.
- **Audit:** `Severity | Status | Evidence | Impact | Recommendation`, followed only by maps and migration detail supporting the priorities.
- **Subsystem specification:** responsibility/non-responsibility, authoritative state, contract, dependencies, lifecycle, failure/security/performance, validation, migration.

Adapt emphasis to the reader's need: decision-makers need outcome, risk, cost, and
sequence; architects need alternatives and invariants; implementers need interfaces,
affected code, migration, and tests; reviewers need evidence and regression risk. Do not
announce the audience profile or pad the artifact.

## Migrate and degrade gracefully

Prefer the smallest change that establishes a useful owner, source of truth, or stable
contract. Characterize behavior first; move one authoritative responsibility at a time;
avoid a second source of truth; give every adapter a removal condition.

Read supporting references only when the request needs their depth:

- `references/architectural-philosophies.md` for academic grounding or disputed assumptions;
- `references/output-artifacts.md` for a formal artifact;
- `references/repository-architecture-audit.md` for a repository-wide audit;
- `references/subsystem-specification.md` for an implementation-ready subsystem design.

If a reference is unavailable, continue with the inline guidance and state the limitation
only when it materially changes confidence. Preserve mandatory behavior under held-out
evaluation before reducing or restructuring this skill; the separate instruction-
optimization system owns measurement and search.

The goal is a coherent system whose architecture reflects its actual forces and can change
as those forces change. Ground every material claim in inspected evidence, and never blur
current behavior with target design.
