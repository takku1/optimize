# External run procedure

The downloaded checkout is a reference input, not a vendored dependency. The
first runnable slice is guarded by `scripts/run_mas_promptbench.ps1`, which
checks the pinned revision and requires an explicit model ID and endpoint.

Example after configuring the upstream environment:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_mas_promptbench.ps1 `
  -Dataset math -Topology single -Limit 10 `
  -ModelId <exact-model-id> -Endpoint http://localhost:8000/v1
```

Run each baseline with identical task-model settings and preserve the upstream
result files. Translate them into the local paired result schema only after
checking scorer identity, task IDs, and split exclusion. The launcher does not
claim a result, perform promotion, or parallelize cells.

The upstream benchmark reports nine datasets and five topologies, but the
initial slice intentionally uses math, HotpotQA, and SWE. SWE requires a
sandboxed repository test environment; it should be run only after the first
two cells validate the adapter and provenance path.
