## Re-audit: `cancel_subscription()` refund/lock fix

**Verdict: Original finding resolved. Fix introduces a new High-severity regression.**

### Original finding — RESOLVED

`billing/subscriptions.py:1-8` now scopes `with db.transaction()` to only the `SELECT ... FOR UPDATE`, the status write, and `db.commit()` (lines 2-5). `stripe_client.refund(sub.charge_id)` runs at line 7, after the transaction block exits and the row lock is released. The DB lock is no longer held across the external Stripe call — the recommendation was implemented as stated.

### New finding — Duplicate refund on retry (High)

**Evidence:** `billing/subscriptions.py:1-8` + `billing/worker.py:1-6`.

Moving the refund outside the transaction decoupled it from the atomicity that used to tie its fate to the status write. Now:

1. `handle_cancel_message` wraps `cancel_subscription` in a bare `try/except Exception: requeue(msg)` — at-least-once delivery, no dedup key (per the file's own comment).
2. `cancel_subscription` is not idempotent: it unconditionally re-queries the sub, re-sets `status = "canceled"` (harmless no-op), commits, then unconditionally calls `stripe_client.refund(sub.charge_id)` again — with no check of whether the sub is already canceled or already refunded.
3. If the refund call raises for any reason *after* Stripe has actually processed it — timeout waiting on the response, transient 5xx after processing, connection reset post-success — the exception propagates out of `cancel_subscription`, the worker requeues, and the handler runs again. The second pass finds the row already `canceled`, does an idempotent no-op commit, and re-issues `stripe_client.refund(sub.charge_id)` — a second real refund against Stripe, since there's no idempotency key on the call and no local record of "refund already issued."

This is a direct financial-correctness bug (customer refunded twice), and it's strictly worse than the lock-holding issue it replaces: the old code, whatever its transaction shape, kept the refund call and the status mutation in the same atomic unit, which at least meant a rollback on failure reset local state consistently. Splitting them removed that coupling without adding the idempotency the split now requires.

**Root cause:** the fix addressed *where* the Stripe call runs but not *how many times* it's safe to run — the finding was scoped to lock contention, and the retry-safety implication of moving the call was never in scope of the original recommendation.

**Recommendation:** pass a Stripe idempotency key derived from a stable, durable value (e.g. `sub.charge_id` + a persisted "refund attempt" record, or `sub_id` plus the cancellation event id) on the `refund()` call, so repeated calls after a requeue resolve to the same Stripe-side refund instead of creating a new one. Additionally, guard the entry of `cancel_subscription` so a subscription already in `status == "canceled"` short-circuits before attempting another refund — cheap, and closes the gap even for retries that don't share a Stripe key. Either change alone fixes the immediate bug; both together close it at two independent layers (Stripe-side dedup and local-side dedup), which is warranted given financial impact.

**Validation to disprove the fix later:** force `stripe_client.refund` to raise *after* returning 200 on a real integration double (simulating a post-success timeout), let `worker.py` requeue, and assert only one refund is recorded on the Stripe side (or one idempotency-keyed request is sent twice with the second returning the cached original response).

**Next step:** treat this as a new High finding, not a footnote — the original ticket should be reopened or a new one filed referencing this file pair, since "fixed" as originally scoped is true but the change is not safe to ship as-is under the worker's retry semantics.
