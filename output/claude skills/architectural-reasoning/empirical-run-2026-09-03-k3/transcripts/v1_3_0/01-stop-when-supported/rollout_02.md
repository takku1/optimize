**Recommendation**

Yes — reasonable, and it's a small, well-contained change. Give `Webhook` a `timeout` column (validated to 1-30s at registration), and have `dispatch()` read `hook.timeout` instead of the module-level `DEFAULT_TIMEOUT`. You don't need to touch `shared/http_client.py` at all.

**Evidence**

- `shared/http_client.py:4` — `http_client = httpx.Client()`, called via `http_client.post(hook.url, json=payload, timeout=DEFAULT_TIMEOUT)` in `dispatch.py:5`. httpx's `Client.post()` already accepts `timeout` as a per-call override; `DEFAULT_TIMEOUT` is just the value `dispatch.py` happens to pass in, not a fixed property of the client. So the shared client's contract already supports what you need — the "same 5s timeout for every outbound call" behavior lives in each caller's call site, not in the client.
- `shared/http_client.py:5` — the comment "used identically by every outbound caller in this service" describes current usage, not an enforced constraint. Since the override is per-call, other callers keep passing `DEFAULT_TIMEOUT` and are unaffected by webhook_service changing what it passes.
- `webhook_service/models.py:1-7` — `Webhook` has no timeout field; storage is the only real gap.
- `webhook_service/dispatch.py:3-5` — `dispatch()` already loads the `Webhook` row before calling out, so the per-row timeout is available for free at the call site with no new query or plumbing.

**Ownership**

`Webhook.timeout` becomes the single source of truth for that webhook's send timeout. Validate the 1-30s bound where the value is written (the registration handler, not shown here but implied by "configurable at registration") — reject or clamp there, don't re-validate in `dispatch()`. `dispatch()` should just read the stored value; if you allow the column to be nullable for pre-existing rows, fall back to `DEFAULT_TIMEOUT` there rather than assuming every row has a value.

**Tradeoffs**

- Sacrifices uniformity of behavior across webhooks (each can now behave differently under slow endpoints), but that's the point of the feature and it's scoped to this one call site — it doesn't weaken the shared client's contract for anything else in the service.
- A registrant setting 30s on every webhook increases how long a dispatch worker can be tied up per call. Whether that's a real problem depends on `dispatch()`'s concurrency model (sync/threaded/async, retry behavior, queue depth under backlog), which isn't in the files inspected here. **OPEN DESIGN DECISION**: whether 30s per-call timeouts need an additional guard (e.g., a worker-level deadline or concurrency cap) — resolve by checking how `dispatch()` is invoked (sync loop vs. async/worker pool) before shipping the max bound.

**Next step**

1. Add `timeout = Column(Integer, nullable=False, default=5)` to `Webhook` (backfill existing rows to 5).
2. Validate 1-30 at the registration endpoint.
3. Change `dispatch.py` to `timeout=hook.timeout` (with a `DEFAULT_TIMEOUT` fallback only if the column is nullable).
4. Add a regression test asserting `dispatch()` passes the stored per-webhook timeout, not the module default, to `http_client.post`.
