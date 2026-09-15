**Recommendation**

Yes, add it. This is a small, additive change: the timeout becomes a property owned by the `Webhook` record (per-registration config) rather than the shared `http_client`, and it flows through the one call site that already passes `timeout` explicitly. No change to `shared/http_client.py` is needed.

Concretely:

1. **`webhook_service/models.py`** — add `timeout_seconds = Column(Integer, nullable=False, default=5)` to `Webhook`. Enforce the 1–30s bound at the registration API boundary (request validation), not as a DB constraint only — the column type alone won't reject 0 or 500. A migration backfills existing rows to `5`, matching today's `DEFAULT_TIMEOUT`, so behavior is unchanged for every webhook registered before this ships.
2. **`webhook_service/dispatch.py`** — change `timeout=DEFAULT_TIMEOUT` to `timeout=hook.timeout_seconds`. That's the entire threading change; the import of `DEFAULT_TIMEOUT` can go (or stay as the migration's backfill constant).
3. **`shared/http_client.py`** — untouched. `http_client.post(..., timeout=...)` already accepts a per-call override (dispatch.py is already using this form), so the "used identically by every outbound caller" property is preserved: other callers keep getting `DEFAULT_TIMEOUT`, and webhook dispatch is the only caller that now supplies its own value.

**Evidence**

- `webhook_service/dispatch.py:5` already calls `http_client.post(hook.url, json=payload, timeout=DEFAULT_TIMEOUT)` — the timeout is a call-site argument, not something baked into `http_client`, so per-webhook override is a one-line substitution, not a new mechanism.
- `shared/http_client.py:5` — `# used identically by every outbound caller in this service` — this is the invariant to preserve. It describes the *default*, not a restriction on per-call overrides; since httpx's `timeout` kwarg is already exercised per-call, adding a second caller-supplied value doesn't touch this file or affect other callers.
- `webhook_service/models.py:7` — `# no timeout field yet` confirms the gap is exactly where the teammate wants to close it: the webhook's own record.

**Tradeoffs**

- Sacrificed: a small amount of uniformity — dispatch is no longer "just like every other outbound call." That's acceptable because the request (customer-configurable timeout on a customer-registered URL) is inherently per-webhook, not service-wide.
- Risk to flag, not block on: a registrant can now set 30s on every webhook. If dispatch runs synchronously with limited worker concurrency, many slow/malicious endpoints at 30s each could tie up dispatch capacity longer than the current fixed 5s ever could. Nothing in the evidence scope (models.py/dispatch.py/http_client.py) shows the calling/concurrency context for `dispatch()`, so this is an **OPEN DESIGN DECISION** — resolve by checking how `dispatch` is invoked (sync request path vs. background worker/queue) before shipping a ceiling above the current 5s default; if it's a worker pool, 30s×concurrent-slow-hooks is the number that matters.
- Validation ownership: putting the 1–30s bound only in the API layer means any other future writer of `Webhook.timeout_seconds` (admin tool, script, bulk import) can bypass it. If that's a realistic path, add a DB `CHECK (timeout_seconds BETWEEN 1 AND 30)` as a backstop — cheap, and it doesn't need to be the primary enforcement point.

**Next step**

Implement the three edits above; add a test asserting `dispatch()` passes `hook.timeout_seconds` (not `DEFAULT_TIMEOUT`) to `http_client.post`, plus a registration-endpoint test rejecting values outside 1–30. Before merging, confirm the dispatch concurrency model to close the OPEN DESIGN DECISION on worst-case blocking time.
