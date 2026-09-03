Yes, this is a reasonable change, and it threads through cleanly because of how the call path is already built.

**Recommendation**

Give each `Webhook` row its own `timeout` value, validate it (1-30s) at registration, and pass it through to the existing per-call `timeout` argument in `dispatch.py`. No change to `http_client` itself is needed — `DEFAULT_TIMEOUT` stays the service-wide default for every other caller, and the webhook row's timeout only overrides it at the one call site that dispatches to that row's URL.

**Evidence**

- `shared/http_client.py:1-5` — `http_client` is a shared `httpx.Client()`, and `DEFAULT_TIMEOUT` is just a module-level constant passed explicitly at each call site, not baked into the client. `dispatch.py:5` already calls `http_client.post(hook.url, json=payload, timeout=DEFAULT_TIMEOUT)` — httpx accepts `timeout` as a per-request override, so swapping the constant for a per-row value (`timeout=hook.timeout or DEFAULT_TIMEOUT`) is a one-line change with no effect on other callers or on the client's own state.
- `webhook_service/models.py:1-7` — `Webhook` has no timeout column yet (line 7 says so explicitly), so this needs a migration: add a nullable `timeout` integer column. Nullable/fallback matters for existing rows created before this feature ships.
- No registration handler is in scope here, so I can't see where "1-30s" would be enforced today — that validation needs to live at the POST /webhooks/register boundary, not deep in `dispatch()`.

**Tradeoffs**

- *End-to-end responsibility*: the 1-30s bound is a policy decision about what's an acceptable timeout for this service to hold open, and it should be validated once, at the registration write path, not re-derived at dispatch time. Store the value already-validated; `dispatch()` should not need to know the legal range.
- *Fault containment (the challenge)*: `http_client` is currently identical for every outbound caller in the service (per the comment at `shared/http_client.py:5`), which is a real invariant some other reader may be relying on when reasoning about worst-case blocking time for outbound calls. Once webhook dispatch can hold a connection for up to 30s instead of 5s, that invariant is gone for this one call site — worth a one-line comment update at `shared/http_client.py:5` so it doesn't mislead someone modifying the client later. If `dispatch()` is ever called synchronously inside a request-handling path (not visible in the files provided), a 6x longer possible hold time is worth confirming isn't a problem before shipping; if it's only invoked from an async worker/queue, this doesn't matter. **OPEN DESIGN DECISION**: whether to also clamp `hook.timeout` defensively at read time in `dispatch()`, in case a row's value is ever written outside the registration path (e.g. a future admin tool or direct DB edit). Cheap insurance, not required by anything currently in scope.

**Next step**

Smallest reversible slice: add the nullable `timeout` column to `Webhook`, validate 1-30s in the registration handler before the insert, and change `dispatch.py:5` to `timeout=hook.timeout or DEFAULT_TIMEOUT`. Validate with a unit test asserting `dispatch()` passes the row's timeout to `http_client.post`, plus a registration-endpoint test rejecting values outside [1, 30]. This is fully reversible — a row with `timeout=NULL` behaves exactly as today.
