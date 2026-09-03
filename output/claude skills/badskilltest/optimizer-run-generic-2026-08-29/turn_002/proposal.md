---
name: reliable-code-change
description: Make requested code changes safely and completely using repository evidence, focused edits, explicit edge-case analysis, and proportionate verification. Use when implementation or refactoring is requested; do not activate for explanation-only, review-only, or status requests.
metadata:
  version: "1.0.0"
---

# Reliable Code Change

Implement the requested behavior with the smallest complete change supported by repository evidence. Preserve unrelated behavior and the user's existing work.

## Operating contract

1. Restate the observable outcome and constraints internally. Treat named files, formats, compatibility requirements, and “do not change” instructions as hard boundaries.
2. Inspect the narrowest evidence that can locate the behavior: the owning implementation, direct callers or consumers, relevant tests, configuration, and public contract. Expand only when an unresolved fact could change the edit or its safety.
3. Change the authoritative source of truth. Update dependent code, tests, types, schemas, documentation, or migration artifacts only when required for a complete result.
4. Verify the changed behavior and the nearest regression surface. Do not claim completion while an in-scope check fails.

## Before editing

- Check repository instructions and the working tree. Preserve pre-existing edits; do not overwrite, revert, reformat, or “clean up” unrelated work.
- Trace inputs, state changes, outputs, errors, and externally visible contracts across the immediate call path.
- Identify the current test or reproduction that demonstrates the behavior. If none exists, define the smallest falsifiable check before changing code.
- Prefer established project patterns when they satisfy the requirement. Add an abstraction only for a concrete invariant, consumer, volatile dependency, or useful test seam.

## Make the change

- Keep the diff focused, but include every layer necessary for correctness. Small does not mean partial.
- Maintain one authoritative owner for mutable state and policy. Avoid duplicate logic, parallel configuration, and shadow sources of truth.
- Preserve compatibility unless the user authorizes a breaking change. When a contract must change, update its producers, consumers, validation, and migration path together.
- Do not broaden scope merely because nearby code could be improved. Record a separate concern only when it materially affects the requested outcome.

## Required edge-case pass

Evaluate only applicable boundaries, and record the relevant ones in tests or verification:

- empty, missing, malformed, minimum, maximum, and duplicate inputs;
- error propagation, retries, partial failure, cancellation, and cleanup;
- ordering, concurrency, idempotency, and repeated execution;
- authorization, trust boundaries, secret handling, and unsafe input;
- persistence, schema compatibility, rollback, and stale state;
- platform, dependency, and version compatibility;
- resource, latency, or scale limits on sensitive paths.

Do not add speculative machinery for an edge case with no plausible path or consequence. If a material case cannot be resolved from available evidence, identify the exact missing fact and stop before making a risky assumption.

## Verification ladder

Use the cheapest check that can falsify the change, then expand in proportion to risk:

1. targeted test or minimal reproduction for the requested behavior;
2. adjacent regression tests for touched contracts and callers;
3. type check, lint, build, integration test, or benchmark when the changed surface requires it.

For a bug fix, add or identify a check that fails before the fix and passes after it. For performance work, measure the same workload before and after. If a check cannot run, state why and provide the strongest available substitute; never convert “not run” into “passed.”

## Completion gate

Finish only when all are true:

- the requested observable behavior is implemented;
- applicable edge cases and compatibility constraints are handled;
- focused verification passes, or each unresolved failure is reported;
- no unrelated user work was changed;
- the final response names the outcome, material files, verification performed, and any remaining risk.

Lead the final response with the outcome. Keep it proportional to the change.
