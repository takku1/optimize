# Prompt Optimization

Prompt Optimization is an alpha-stage Python toolkit for evaluating and
optimizing prompts and agent skills as behavioral policies. Its BCSO-Bench
(Behavior-Constrained Skill Optimization) workflow combines explicit
capability contracts, held-out scenarios, hard invariants, uncertainty-aware
comparison, Pareto search, attribution, and auditable candidate lineage.

The project draws a strict evidence boundary: the built-in synthetic backend
can test mechanics and propose candidates, but it cannot establish that a real
model improved. Promotion requires real, held-out results supplied through a
rubric or callable evaluator.

## Install

Python 3.11 or newer is required.

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

The runtime dependencies are NumPy and SciPy. The CLI makes no network calls
unless a user-supplied callable does so.

## Quick start

Score a directory with the deterministic synthetic scaffold:

```bash
prompt-opt scan --json src
```

Inspect the Pareto frontier and apply a hard distortion gate:

```bash
prompt-opt plan docs --gate distortion=0.25
```

Run candidate search while preserving its lineage:

```bash
prompt-opt search SKILL.md \
  --baseline full_bcso \
  --run-dir runs/example \
  --graph-dir evolution-graph
```

Compare externally produced baseline/candidate results against a contract:

```bash
prompt-opt compare \
  --contract contract.json \
  --results paired-results.json \
  --json
```

Then render the promotion boundary explicitly:

```bash
prompt-opt promote \
  --baseline SKILL-v1.md \
  --candidate SKILL-v2.md \
  --contract contract.json \
  --results paired-results.json
```

Run `prompt-opt --help`, see the [CLI reference](docs/CLI.md), or use
`python -m prompt_optimization` when the console script is unavailable.

## What is implemented

- Versioned intent and capability contracts with hard behavioral invariants.
- Synthetic, rubric-file, and user-supplied callable evaluators.
- Paired non-inferiority comparison with bootstrap uncertainty.
- Activation, metamorphic, attribution, cost, Pareto, and robustness metrics.
- Branching search, iterative optimization, named baselines, and saturation
  gates.
- Content-addressed evolution graphs with lineage and transition retrieval.
- Taxonomy coverage, maturity, provenance, promotion, and verifiable document
  claims.
- Programmatic orchestration for blinded empirical runs.

## Evidence levels

| Level | What it supports |
|---|---|
| Synthetic backend | Implementation checks, demonstrations, candidate proposals |
| Rubric/callable backend | Claims supported by the supplied evaluator and data |
| Paired held-out scenario results | Contract-conditioned comparison and promotion |
| Calibrated multi-run study | Stronger empirical claims; still future work at project scale |

The repository contains one preserved real-model pilot and a negative-control
follow-up for the `architectural-reasoning` skill. They are useful benchmark-
validity findings, not broad evidence that the optimizer generalizes. See the
[benchmark card](docs/benchmark-card.md) and [status](docs/STATUS.md).

## Package map

| Package | Responsibility |
|---|---|
| `metrics` | Synthetic basin model, uncertainty, metamorphic tests, Pareto and cost metrics |
| `attribution` | Shapley, interaction, deletion, and directional estimators |
| `context` | Token sequences, attention, representations, and cache reuse |
| `evaluators` | Synthetic, rubric, callable, activation, and calibration layers |
| `contracts` / `capability` | Behavioral specifications, maturity, provenance, claims, and promotion |
| `search` | Mutation, archives, hierarchical/iterative optimization, and run output |
| `graph` | Persistent content-addressed skills, mutations, evaluations, and retrieval |

Most common analysis primitives are re-exported from `prompt_optimization`;
advanced APIs should be imported from their subpackage.

## Documentation

- [Documentation index](docs/README.md)
- [CLI reference](docs/CLI.md)
- [Current status](docs/STATUS.md)
- [BCSO-Bench specification](docs/bcso-bench.md)
- [Benchmark card](docs/benchmark-card.md)
- [Governance](docs/governance.md)
- [Contributing](CONTRIBUTING.md)

## License

MIT. See [LICENSE](LICENSE).
