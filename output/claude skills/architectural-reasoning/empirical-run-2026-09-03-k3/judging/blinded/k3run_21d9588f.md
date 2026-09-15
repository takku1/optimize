## Recommendation

Yes — reasonable and cheaply threaded through the existing path. Add a `timeout` column to `Webhook`, validate the 1-30s range at the registration endpoint (not in dispatch), and have `dispatch()` read `hook.timeout` instead of the module-level `DEFAULT_TIMEOUT` constant. No change to `shared/http_client.py` is needed.

## Evidence

- `webhook_service/dispatch.py:5` already passes a per-call `timeout=` kwarg to `http_client.post(...)` — httpx's per-request timeout override is the mechanism already in use, it's just fed a hardcoded constant (`DEFAULT_TIMEOUT`) instead of caller-specific data. Threading a stored value through this call is a one-line change.
- `shared/http_client.py:4-5` — the client is a single shared `httpx.Client()` used identically by every outbound caller in the service (per the comment). It has no webhook-specific state and shouldn't acquire any: per-call timeout override is a stdlib capability of the client, not a webhook-specific feature.
- `webhook_service/models.py:1-7` — `Webhook` has no `timeout` field; registration currently stores only `url`, `secret`, `created_at`. The row is the natural, single owner of "how long should we wait for this endpoint" — it's registration-time policy tied to that specific destination, not global transport config.

## Tradeoffs

**Ownership (primary lens):** the per-webhook timeout belongs on the `Webhook` row, not in `dispatch.py` or `http_client.py`. `dispatch()` should remain a thin reader of that row's policy; `http_client` should remain a generic transport with zero awareness of webhooks. This keeps the boundary where it already is — dispatch is the only place that knows both "which webhook" and "which HTTP call."

**Challenge — end-to-end responsibility / blast radius:** the value is untrusted input from whoever calls `POST /webhooks/register`. Validation (1-30s, integer/numeric, reject NULL/garbage) belongs at the registration boundary, not in `dispatch()` and not in `http_client`. If dispatch or the client silently clamps or defaults a bad value instead of the registration endpoint rejecting it, you get a second, weaker enforcement point and a stored value that doesn't match what the registrant thinks they set. Validate once, at the point of entry; trust the stored value everywhere downstream.

**Non-responsibility to preserve:** `shared/http_client.py` should not grow any per-webhook or per-caller-type logic. It already supports the override via `timeout=` on the call — that's sufficient. Don't add webhook-aware branching there; every other caller in the service depends on it staying generic (per the file's own comment).

**OPEN DESIGN DECISION:** raising the ceiling to 30s on a shared client used by every outbound caller increases worst-case blocking time per dispatch call. Whether that's safe depends on dispatch's concurrency model (async/worker pool/queue depth), which isn't visible in these three files. Worth a quick check before shipping: confirm dispatch isn't run inline on a request-serving thread/pool where N slow webhooks could exhaust capacity. If it's already queued/worker-based, this is a non-issue.

## Next step

1. Migration: add `timeout` to `webhooks` (int, NOT NULL, default 5 so existing rows behave exactly as today).
2. Validate `1 <= timeout <= 30` in the registration handler; reject out-of-range with a 4xx.
3. `dispatch.py`: replace `timeout=DEFAULT_TIMEOUT` with `timeout=hook.timeout`; keep `DEFAULT_TIMEOUT` only as the schema/handler default, not as a dispatch-time fallback.
4. No change to `shared/http_client.py`.
5. Test: register a webhook with timeout=1 against a slow/unreachable endpoint, confirm it times out at ~1s and other callers using `DEFAULT_TIMEOUT` are unaffected.
