# Empirical runs

Iterative candidate optimization is available through one public command:

```text
prompt-opt optimize --config run.json
```

The implemented command generates proposals and scores them through either a
`score_fn` callback or an `executor_fn` plus scenario file. It writes a final
proposal and `run.json` when `output_dir` is configured. It does not yet own
blinding, judging, promotion, or resumable execution.

The programmatic `run_empirical` API owns subject batching, blind IDs,
deterministic checks, judge batching, and isolation metadata. Integrating that
API with `optimize` into one artifact-complete CLI lifecycle remains planned.

## Source of truth

The authoritative judge is model-free wherever the scenario can express its
expectation as an executable predicate. Examples include word bounds,
required/forbidden content, schema validation, file-path evidence, invariant
state transitions, and resource/cost limits. These checks are versioned in the
scenario fixture and are evaluated by the program.

Natural-language semantic claims are not silently converted into phrase
matches. If a scenario has no executable predicate for an invariant, its
result is `unresolved`, not `true`; the run must either provide a human review,
a calibrated external semantic evaluator, or leave the promotion gate
uncertified.

## Call minimization without invalid evidence

- Subjects are batched by skill version. Scenario outputs use explicit IDs and
  are persisted separately.
- Judges may use a provider batch API only when each item is context-isolated.
  A shared-context judge is recorded as non-independent and cannot be reported
  as independent evidence.
- Deterministic checks run before semantic review and are authoritative for the
  properties they cover.
- Retries are idempotent by unit ID; completed work is resumed rather than
  respawned.

The target is one user-visible run and one report while preserving the
distinction between operational batching and statistical independence.
