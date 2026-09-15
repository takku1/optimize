## Recommendation

Yes, reasonable — and it fits the existing call path with almost no new mechanism. `httpx` already supports a per-request timeout override, and `dispatch.py` already uses it (`http_client.post(hook.url, json=payload, timeout=DEFAULT_TIMEOUT)` — `webhook_service/dispatch.py:5`). Threading a custom value through is a change to *what* gets passed as that argument, not a new capability layered onto the client.

**Design:**
1. Add `timeout_seconds` to `Webhook` (nullable, no default at the DB level) — `webhook_service/models.py`.
2. Validate the 1-30s bound at the registration endpoint (reject out-of-range input at the trust boundary), and re-clamp defensively at dispatch time in case a row is ever populated outside that path (migration, admin tooling, direct DB edit).
3. In `dispatch()`, resolve the value the row carries and fall back to `DEFAULT_TIMEOUT` when `NULL`: `timeout = hook.timeout_seconds or DEFAULT_TIMEOUT`, then pass it as the existing `timeout=` kwarg — no change to the call shape.
4. Leave `shared/http_client.py` untouched. Don't parameterize the client, and don't mutate `http_client.timeout` per call — it's one shared `httpx.Client()` instance reused by "every outbound caller in this service" (`shared/http_client.py:5`), so anything that touches its state is shared state for everyone else's calls too. Ownership of "what timeout this call gets" belongs to the caller, expressed as a per-request argument — that's the mechanism `httpx` gives you specifically so shared clients don't need per-caller configuration.

Net effect: one additive, nullable column; one bounds-check at the write path; one line changed in `dispatch()`. Existing rows and every other caller of `http_client` are unaffected.

## Evidence

- `shared/http_client.py:3-5` — single module-level client, single constant timeout, explicit comment that it's shared identically across all outbound callers. This is the fact that rules out modifying the client itself.
- `webhook_service/dispatch.py:5` — timeout is already passed per-call, not relied on as a client default. The override mechanism this request needs already exists in the code, unused for variation but present in shape.
- `webhook_service/models.py:7` — no timeout field yet; confirms this is a pure additive migration, not a rework of an existing contract.

## Tradeoffs

- **Fault containment (the real cost of this change):** raising the ceiling from a fixed 5s to configurable up to 30s means a slow or unresponsive registered endpoint can now hold a dispatch call 6x longer than today. If `dispatch()` runs synchronously on a request-handling or otherwise capacity-constrained worker, this is a materially larger blast radius per bad webhook than what exists today — worth checking before shipping, since it's not visible from `dispatch.py` alone whether it's called inline or off a queue. If it's inline, this change is still fine, but the max timeout and worker pool capacity should be considered together.
- **Trust boundary discipline:** validating 1-30s only at dispatch (not at registration) would let bad values sit in the table indefinitely and only surface as a rejected/clamped value at call time — enforce it where the value enters (registration), and treat the dispatch-time check as a defensive backstop, not the primary gate.
- Not addressed here because it's outside this request's scope: SSRF/URL validation on the registered webhook URL itself — assumed already handled elsewhere in registration, unaffected by this change.

## Next step

Add the migration for the nullable column, the range validation on the registration handler, and the one-line fallback-and-pass change in `dispatch()`. Before merging, confirm with whoever owns the dispatch path whether it executes inline on a request thread or off a queue/worker — that answer determines whether the 30s ceiling needs a corresponding look at worker concurrency, or is a non-issue.
