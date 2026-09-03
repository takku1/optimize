---
name: architectural-reasoning
description: Evidence-first architectural reasoning for consequential software decisions, with calibrated effort, explicit ownership, stable contracts, justified boundaries, falsifiable migration, and behavior-preserving edits.
metadata:
  version: "1.3.0-damaged-reaudit"
  based_on: "architectural-reasoning 1.3.0"
---

# Architectural Reasoning

Design from actual system forces, not a favored pattern. Produce clear ownership, contracts, justified boundaries, explicit tradeoffs, and an incremental path from current reality.

## Calibrate effort

- **Quick decision (default):** inspect targeted evidence, apply one primary lens and one meaningful challenge, then return a compact recommendation.
- **Focused design:** for one subsystem, boundary, or critical flow, map its owner, state, contract, dependencies, risks, and migration.
- **Full architecture:** reserve for an explicitly requested audit, formal system design, or change spanning foundational subsystems.
- **Re-audit:** review the prior audit findings and the associated diff.

Stop when the decision is supported. Gather only evidence that could change the recommendation. Do not execute every lens mechanically or rewrite working code to fit a philosophy.

## Work from reality

Inspect relevant code, configuration, tests, deployment artifacts, and documentation. Cite concrete files and symbols for material findings. Run an available test, build, benchmark, or minimal reproduction before reporting a material claim.

Keep these views distinct:

- **Current:** observed behavior, components, state, dependencies, and constraints.
- **Target:** desired ownership, contracts, boundaries, invariants, and qualities.
- **Migration:** dependency-aware changes that preserve valuable behavior.

Directory names and diagrams are hypotheses until flows and dependencies confirm them. Do not rewrite working code merely to fit a philosophy.

## Select lenses and preserve invariants

For a consequential choice, select lenses from the governing force observed in the evidence; use one to generate the design and another to challenge it; surface the tension only when it changes the recommendation.

| Lens | Use when the governing force is |
|---|---|
| Information hiding / ownership | responsibility or state authority |
| End-to-end responsibility | a workflow crosses components |
| Sociotechnical alignment | team boundaries or incentives shape design |
| Evolutionary architecture | change and reversibility dominate |
| Security by construction | misuse or trust boundaries matter |
| Empirical performance | latency, throughput, or resource cost matters |
| Fault containment / recovery | partial failure or recovery matters |
| Distributed tradeoffs | consistency, coordination, or partitioning matters |
| Specification / invariant-first | correctness constraints govern |

- Give each important responsibility and mutable state set one authoritative owner; make readers, writers, lifetime, synchronization, persistence, reconciliation, and non-responsibilities explicit where relevant.
- Expose minimum stable domain semantics, not private representation. Distinguish ownership, contract, build, runtime, protection, and deployment boundaries.
- Add runtime boundaries only when isolation, security, fault containment, deployment, scaling, or runtime variability justifies their cost.
- Introduce abstraction for a concrete consumer, invariant, volatile dependency, required substitution, or useful test seam.
- Optimize sensitive paths with: baseline → benchmark → profile → bottleneck → change → benchmark → regression test.

## Evidence, output, and migration

Capture requirements/evidence, alternatives including the status quo, decision and sacrificed qualities, failure modes, migration/reversal conditions, and validation tests that could disprove the choice. Mark unresolved choices **OPEN DESIGN DECISION** and state what evidence would resolve them.

When editing this skill, preserve mandatory behavior under held-out evaluation before reducing wording; the separate instruction-optimization skill owns measurement and search.

Route to the requested PR comment, ADR, RFC, audit, or subsystem specification. Otherwise use `Recommendation`, `Evidence`, `Tradeoffs`, and `Next step`. Characterize behavior first, move one authoritative responsibility at a time, avoid a second source of truth, give every adapter a removal condition, and treat optional references as supplements.
