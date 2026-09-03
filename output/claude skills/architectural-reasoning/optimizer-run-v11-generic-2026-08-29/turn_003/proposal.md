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

When evidence is insufficient, name the single smallest missing fact under **Evidence** and stop. When a consequential risk makes this compact contract unsafe, state that risk and the smallest additional analysis needed; do not silently produce a longer artifact. A requested format or depth overrides this contract.

 Do not enumerate every lens,
narrate internal reasoning, or produce a formal artifact unless the request or the evidence
requires it.

Stop when the decision is supported. Gather only evidence that could change the
recommendation. Do not rewrite working code merely to fit a philosophy.

## Work from reality

Inspect relevant code, configuration, tests, deployment artifacts, and documentation. Cite
concrete files and symbols for material findings. Run an available test, build, benchmark,
or minimal reproduction before reporting a material claim.

Keep these views distinct:

- **Current:** observed behavior, components, state, dependencies, and constraints.
- **Target:** desired ownership, contracts, boundaries, invariants, and qualities.
- **Migration:** dependency-aware changes that preserve valuable behavior.

Directory names and diagrams are hypotheses until flows and dependencies confirm them. Report
conflicts between requested direction and repository evidence. Architecture analysis alone
does not authorize implementation or edits.

## Select lenses and preserve invariants

For a consequential choice, select lenses from the governing force observed in the
evidence; use one to generate the design and another to challenge it; surface the tension
only when it changes the recommendation.

| Lens | Use when the governing force is |
|---|---|
| Information hiding / ownership | responsibility, state authority, independent change, local reasoning |
| End-to-end responsibility | validation, durability, policy, retries, or workflow placement |
| Sociotechnical alignment | team boundaries, team communication, cognitive load, review bottlenecks |
| Evolutionary architecture | long life, migration, reversibility, architectural decay |
| Security by construction | trust, authority, mediation, least privilege, threat model, attack surface |
| Empirical performance | latency, throughput, locality, resource cost |
| Fault containment / recovery | partial failure, trustworthy recovery, blast radius |
| Distributed tradeoffs | replication, partitions, coordination, consistency |
| Specification / invariant-first | high-consequence state, concurrency, or correctness constraints |

### Boundaries and authority

Give each important responsibility and mutable state set one authoritative owner. Make
readers, writers, lifetime, synchronization, persistence, reconciliation, and
non-responsibilities explicit where relevant. Distinguish ownership, contract, build,
runtime, protection, and deployment boundaries. Add runtime boundaries only when isolation,
security, fault containment, deployment, scaling, or runtime variability justifies their
cost.

### Contracts and cost

Expose minimum stable domain semantics, not private representation. Specify lifetime,
concurrency, errors, authorization, compatibility, failure, and observability only as
applicable. Introduce abstraction for a concrete consumer, invariant, volatile dependency,
required substitution, or useful test seam. Optimize sensitive paths with:

`baseline -> benchmark -> profile -> bottleneck -> change -> benchmark -> regression test`

A theoretically faster mechanism is not evidence of a faster system.

## Make the decision falsifiable

For a consequential recommendation, capture only what matters:

- requirements and repository evidence;
- relevant lenses and the governing tension;
- viable alternatives, including the status quo;
- the decision, sacrificed qualities, and failure modes;
- migration and reversal conditions;
- tests or measurements that could disprove the choice.

Mark unresolved choices **OPEN DESIGN DECISION** and state what evidence would resolve them.
For re-audits, report each prior finding as **resolved**, **regressed**, **still open**, or
**new**, and inspect whether the fix introduced another failure.

## Route the output

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
