# MAS-PromptBench v1 local study recipe

This directory is reserved for local run manifests and results. The upstream
checkout is kept under the ignored `external/` directory. The registered cells
are described by `../mas-promptbench-v1.json`.

## Offline preparation

The local package can validate the registry and create a provenance-bearing
run description without a model endpoint. Do not call the upstream runners
until their environment, original dataset licenses, and model settings are
recorded.

## First study

Run one paired cell for each of `math`, `hotpotqa`, and `swe` using:

1. original/no skill;
2. a simple rewrite;
3. focused bounded search;
4. full BCSO;
5. damaged-skill control where the task supports a known defect.

Use upstream evaluation IDs only after search and calibration freeze. Keep
training and validation instances disjoint from those IDs. Run at least three
rollouts per condition when the endpoint supports stochastic sampling, and
report per-cell results plus the hierarchical aggregate.

No result should be labeled validated until the complete paired artifact,
provenance, deterministic verifier output, and held-out comparison are present.
