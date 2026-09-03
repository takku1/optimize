## Recommendation

Partially fixed. The diff correctly resolves the original finding — the DB lock is no longer held during the Stripe call — but it introduces a new High-severity issue: the status update and the refund are no longer atomic, the refund call is not idempotent, and the queue consumer's blind retry-on-any-exception will re-issue `stripe_client.refund` for the same charge on a transient failure. There is also a silent-failure path where a subscription ends up marked "canceled" with no refund ever issued.

## Evidence

- `billing/subscriptions.py:1-5` — `sub.status = "canceled"` is set and committed inside `db.transaction()`, releasing the `SELECT ... FOR UPDATE` lock at `db.commit()`.
- `billing/subscriptions.py:6-7` — `stripe_client.refund(sub.charge_id)` now runs after the transaction has committed and the lock is released. This confirms the original finding (lock held across a network call) is fixed.
- `billing/worker.py:1` — comment states the queue consumer has "no dedup/idempotency key."
- `billing/worker.py:3-6` — `handle_cancel_message` wraps `cancel_subscription(msg.sub_id)` in a bare `try/except Exception` and requeues on *any* exception, including one raised by the refund call itself. A requeue re-runs `cancel_subscription` from the top: it re-queries the (already-canceled) subscription and calls `stripe_client.refund(sub.charge_id)` again, with no idempotency key passed to Stripe. A timeout or transient error on the first refund attempt — the exact class of failure the original fix was meant to make survivable — now produces a second, non-idempotent refund call for the same charge.
- Unhandled by either file: if the process crashes or is killed between `subscriptions.py:5` (commit) and `subscriptions.py:7` (refund) — deploy, OOM, pod eviction — the subscription is durably marked `canceled` but the refund never fires, and no exception is raised to trigger a requeue. The subscription silently ends up canceled-without-refund, and nothing in this code path detects or corrects it.

## Tradeoffs

Moving the call outside the transaction correctly eliminates the lock-contention/connection-pool-exhaustion risk during a slow or hung Stripe call, which was the concrete production risk in the prior finding. But it does so by splitting a previously-atomic operation (DB state change + external side effect) into two independent steps with no compensating mechanism — no idempotency key, no outbox/reconciliation record, no post-commit status field distinguishing "canceled, refund pending" from "canceled, refunded." That's an acceptable pattern in general (synchronous external calls generally shouldn't sit inside DB transactions), but only when paired with idempotency and a way to detect/repair the gap between the two steps. Here it wasn't, so the change traded a lock-contention risk for a data-consistency risk (classic dual-write problem), and the existing retry-on-any-exception behavior in `worker.py` actively exercises that gap.

## Next step

1. Pass a stable idempotency key to `stripe_client.refund` (e.g. derived from `sub.charge_id` or `sub_id`) — Stripe's refund API accepts an `Idempotency-Key`, which makes retries safe at the Stripe layer regardless of what the app does.
2. Make `cancel_subscription` idempotent on replay independent of Stripe's key: short-circuit (or check a `refund_status` field) if the subscription is already `canceled`, so a requeued message doesn't re-attempt a refund call it has no way of knowing already succeeded.
3. Close the crash-after-commit gap with a reconciliation path — an outbox row written in the same transaction as the status update, or a periodic job that finds `canceled` subscriptions with no corresponding refund and completes them exactly once. Without this, a crash between commit and refund is invisible to the current retry mechanism (it only fires on a raised exception, not on a stalled/killed process).

**Validation test that would disprove "fixed" if it fails:** simulate `stripe_client.refund` raising a timeout on the first call after `cancel_subscription` commits; assert the message is requeued (per current `worker.py` behavior); assert exactly one refund reaches Stripe (via idempotency key), not two.

**OPEN DESIGN DECISION:** whether refund-on-cancel should be synchronous at all, versus enqueuing a dedicated `issue_refund` job decoupled from `cancel_subscription`. That would let cancellation succeed independently of Stripe availability and gives the retry/idempotency logic one clear owner instead of splitting it between `cancel_subscription` and the generic message consumer. Resolving this needs product input on whether cancellation should ever be allowed to succeed before the refund is confirmed.
