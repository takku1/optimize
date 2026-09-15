**Recommendation**

Yes, reasonable — and it doesn't require touching the shared client's contract. Give `Webhook` ownership of its own timeout and pass it explicitly per-call; `shared/http_client.py` already supports this today.

**Evidence**

- `webhook_service/models.py`: `Webhook` has `id`, `url`, `secret`, `created_at` — no timeout field.
- `webhook_service/dispatch.py`: `http_client.post(hook.url, json=payload, timeout=DEFAULT_TIMEOUT)` — timeout is already passed as a **per-call keyword argument**, not baked into the client object.
- `shared/http_client.py`: `http_client = httpx.Client()` is a bare connection pool; `DEFAULT_TIMEOUT = 5` is just a module constant every caller currently imports and reuses. The comment "used identically by every outbound caller" describes current *usage*, not a constraint the client enforces — `httpx.Client.post(..., timeout=...)` overrides per-request regardless of what the client was constructed with.

This is the material finding: the mechanism for per-call variability already exists. No change to `shared/http_client.py` is needed, and no other caller of `http_client` is affected.

**Lens**

*Information hiding / ownership* (primary): timeout-per-registration is a property of the webhook, not of the shared transport. Authority for it belongs on `Webhook`, read at dispatch time and passed down — not hoisted into shared infra, which would leak one endpoint's policy into every other caller's contract.

*End-to-end responsibility* (challenge): the 1-30s bound is a validation rule, and validation needs one authoritative place, not two. Put it at registration (API/model layer) so an invalid value never reaches the row — don't re-validate at dispatch time as a substitute. Dispatch should trust the stored value.

**Tradeoffs**

- Sacrificed: none material. `shared/http_client.py` keeps its current contract untouched; `DEFAULT_TIMEOUT` remains the fallback for every other caller in the service.
- New failure mode: a slow/malicious registrant sets timeout near 30s, holding a connection open 6x longer than today's fixed 5s. Not a new attack surface (dispatch already POSTs to arbitrary registered URLs), but it does raise per-call worst-case latency and held-connection time — worth a glance at whatever concurrency/pool limits `httpx.Client()` is using if webhook volume is high. Flagging as **OPEN DESIGN DECISION**: is 30s ceiling chosen for a reason, or arbitrary? Resolve by checking expected webhook receiver SLAs / existing pool `limits=` config (not present in the inspected files).

**Next step**

1. `models.py`: add `timeout = Column(Integer, nullable=False, server_default="5")` to `Webhook` (server-side default avoids a backfill migration for existing rows).
2. Registration endpoint: validate `1 <= timeout <= 30` there — reject out-of-range before insert.
3. `dispatch.py`: change `timeout=DEFAULT_TIMEOUT` to `timeout=hook.timeout`. `DEFAULT_TIMEOUT` stays imported/used only as the column's application-level fallback if you don't trust the DB default.
4. No change to `shared/http_client.py`.

Validation that would disprove this: if some other part of the service constructs `httpx.Client(timeout=...)` at the client level (not shown in the inspected files) and relies on that as a single point of control, per-call override would silently bypass it — worth a quick grep across other callers of `shared.http_client` before merging, since only `dispatch.py` was in scope here.
