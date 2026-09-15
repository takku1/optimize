## Recommendation

Reasonable change, low risk, and it threads through with **no changes to `shared/http_client.py`**. Give `Webhook` a `timeout_seconds` column (NOT NULL, default 5, validated 1–30 at registration), and pass it through the existing per-call `timeout` kwarg in `dispatch.py`:

```python
# webhook_service/dispatch.py
def dispatch(webhook_id, payload):
    hook = db.query(Webhook).get(webhook_id)
    return http_client.post(hook.url, json=payload, timeout=hook.timeout_seconds)
```

## Evidence

- `shared/http_client.py:4` — `http_client` is a single shared `httpx.Client()`; `DEFAULT_TIMEOUT` is just a value passed at each call site, not baked into the client. httpx's `.post(..., timeout=...)` already overrides the client's default for that one call and doesn't mutate shared state.
- `webhook_service/dispatch.py:5` — already passes `timeout=` explicitly per call. Swapping the source of that value from a module constant to a row attribute is the entire change to this file.
- `webhook_service/models.py:7` — comment confirms no timeout field exists yet; this is additive, not a rework.
- `shared/http_client.py:5` — comment says the client is "used identically by every outbound caller in this service." That invariant is preserved: every other caller keeps getting `DEFAULT_TIMEOUT`; only webhook dispatch reads a per-row value. The shared wrapper's contract (accepts an optional per-call timeout override) doesn't change at all — you're using a capability it already exposes.

## Ownership

`timeout_seconds` belongs to the `Webhook` row, not to the shared client. The client's job is "make HTTP calls with a sane default"; the registration record's job is "hold this particular integration's config." Validate the 1–30s bound where the value is written (registration endpoint), not where it's read (dispatch) — dispatch should trust the stored value, not re-validate it on every call.

## Tradeoffs

- **Sacrificed:** uniform, single-constant timeout behavior across webhook calls — debugging "why did this one webhook call take 28s" now requires checking the row, not just the constant. Minor; worth it for the flexibility being requested.
- **Gained:** per-tenant/per-integration tuning without touching shared infrastructure or other callers.
- **Risk if validation is skipped:** enforce the 1–30s bound at the API layer (reject out-of-range on registration) *and* add a DB CHECK constraint (`timeout_seconds BETWEEN 1 AND 30`) — cheap insurance against a future direct-write path (admin script, backfill) bypassing API validation.
- **Migration:** additive column, default `5` (matches current `DEFAULT_TIMEOUT`), so existing webhooks are behavior-preserving until someone edits them. No backfill logic needed.

## Next step

1. Migration: `ALTER TABLE webhooks ADD COLUMN timeout_seconds INTEGER NOT NULL DEFAULT 5 CHECK (timeout_seconds BETWEEN 1 AND 30)`.
2. Registration endpoint: accept optional `timeout_seconds`, validate range, default to 5 if omitted.
3. `dispatch.py`: read `hook.timeout_seconds` instead of `DEFAULT_TIMEOUT`.
4. Test: register a webhook with `timeout_seconds=1` pointed at a slow/unreachable endpoint and confirm it times out near 1s, not 5s — that's the one behavior claim worth a real check rather than inspection.

**OPEN DESIGN DECISION:** none — the shared client's per-call override already covers this use case, so there's no ambiguity to resolve here.
