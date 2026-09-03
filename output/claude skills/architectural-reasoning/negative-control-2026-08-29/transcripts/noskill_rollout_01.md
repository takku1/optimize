# Re-audit: cancel_subscription() lock/refund fix

## Verdict: Original finding is fixed. The fix introduces a new, related correctness bug.

## 1. Original finding — resolved

The prior finding was that `stripe_client.refund()` ran synchronously *inside* the `SELECT ... FOR UPDATE` transaction, so a slow/hung Stripe call held the DB row lock open.

`billing/subscriptions.py:88` (now lines 1-8) confirms the fix:

```python
def cancel_subscription(sub_id):
    with db.transaction():
        sub = db.query(Subscription).filter_by(id=sub_id).with_for_update().one()
        sub.status = "canceled"
        db.commit()
    # refund moved outside the transaction, per the prior audit's recommendation
    stripe_client.refund(sub.charge_id)
    return sub
```

The `with db.transaction():` block now only covers the row lock, status mutation, and commit. It exits — releasing the lock — before `stripe_client.refund()` is called. The row is no longer held locked for the duration of the external network call. As literally recommended, this is correct.

One thing to verify but not blocking: whether `sub` is still a valid/attached object after the transaction context exits (ORM-dependent — some session scopes detach or expire instances on commit). If `sub.charge_id` access after the `with` block ever throws (e.g., `DetachedInstanceError`), that's a separate, low-severity bug, not a recurrence of the original one.

## 2. New issue introduced by the fix — High severity

By pulling the Stripe call out of the transaction, the fix also pulled it out of the *only* mechanism that made the operation retry-safe: the row's canceled-status write and the refund call are no longer atomic, and the refund call has no idempotency protection. Combined with `billing/worker.py`, this creates a duplicate-refund path:

```python
# worker.py
def handle_cancel_message(msg):
    try:
        cancel_subscription(msg.sub_id)
    except Exception:
        requeue(msg)  # will call cancel_subscription again, including stripe_client.refund
```

Walk the failure path:

1. `cancel_subscription` commits `status = "canceled"` and releases the lock.
2. `stripe_client.refund(sub.charge_id)` is called. Suppose it raises — a timeout, a transient 5xx, or even a timeout on the *response* after Stripe has already processed the refund on their side (the classic "did it actually happen?" ambiguity of any network call).
3. The exception propagates out of `cancel_subscription`, uncaught.
4. `handle_cancel_message` catches it and calls `requeue(msg)`.
5. The message is redelivered and `cancel_subscription(msg.sub_id)` runs again: the row is already `"canceled"` (a harmless no-op write), but `stripe_client.refund(sub.charge_id)` is called **a second time** with the same `charge_id` and no idempotency key anywhere in the call.

Nothing in either file provides:
- An idempotency key on the Stripe call (Stripe supports `Idempotency-Key` specifically for this pattern — it isn't being used here).
- A guard against re-refunding a subscription whose status is already `"canceled"` (the code doesn't check current status before refunding, it just re-runs unconditionally).
- Any persisted "refund succeeded / refund pending" state to distinguish "never attempted" from "attempted, outcome unknown" from "confirmed succeeded."

Net effect: a subscription can be refunded twice on Stripe for one cancellation, triggered by exactly the kind of transient failure this code path exists to tolerate (worker.py's docstring says "retries the handler on any exception, no dedup/idempotency key" — that comment is accurate and is flagging the exposure, but nothing downstream addresses it).

This is arguably worse than the original finding: the original was an availability/contention risk (a stuck DB lock under load). This is a financial-correctness risk (money moving twice) with a straightforward trigger (any transient Stripe error, which is precisely when retries fire).

## Recommendation

Don't just move the refund out of the transaction — make it idempotent and re-entrant, since it's now reachable via blind retry:

1. **Pass a Stripe idempotency key** derived from something stable and unique to this cancellation attempt (e.g. `sub_id` or `sub.charge_id` plus a cancellation/version identifier), so a retried call is a guaranteed no-op on Stripe's side rather than a new refund.
2. **Short-circuit on already-canceled state**: check `sub.status == "canceled"` (and ideally a separate `refund_status` field) before calling Stripe at all, so a requeued message that already succeeded doesn't re-attempt the refund.
3. **Track refund state explicitly** (e.g. `refund_status: pending/succeeded/failed` on the subscription or a separate ledger row) rather than inferring success from "no exception was thrown." This also resolves the ambiguity in step 2 above (call raised, but did Stripe actually process it?) — on requeue, check Stripe's own idempotent response instead of assuming failure.
4. Given the exception now escapes `cancel_subscription` and drives `requeue`, decide deliberately whether cancellation-DB-write failures and refund-call failures should share the same retry path — right now they're indistinguishable, and only the refund side is unsafe to retry blindly.

Until one of these lands, this file trades a High-severity lock-contention bug for a High-severity duplicate-refund bug — it isn't a net fix yet.
