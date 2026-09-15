Re-audit: the original finding is resolved, but the fix introduces a new, equally severe regression.

**Classification**
- Original finding (DB lock held during synchronous Stripe call): RESOLVED.
- New finding, introduced by this fix: REGRESSION — the refund is no longer atomic with the cancellation, and the queue's blind retry can now double-refund a customer or leave a subscription canceled with no refund ever issued.

**Evidence**

billing/subscriptions.py:1-8, `cancel_subscription()`: the transaction now sets `sub.status = "canceled"` and commits, releasing the `FOR UPDATE` lock (line 5), before calling `stripe_client.refund(sub.charge_id)` (line 7) outside the transaction. That literally satisfies the prior recommendation — the lock is no longer held across the network call.

But this turns one logical action ("cancel and refund") into two independently-failing steps with nothing to reconcile them. billing/worker.py:1-6, `handle_cancel_message()`, is explicit that it "retries the handler on any exception, no dedup/idempotency key." If `stripe_client.refund()` raises — a timeout, a 5xx, a network blip after Stripe already processed the refund on its end — the exception propagates out of `cancel_subscription`, the message is requeued, and `cancel_subscription(msg.sub_id)` runs again. It re-queries the subscription (already `"canceled"` from the first pass) and calls `stripe_client.refund(sub.charge_id)` a second time with the same charge id. Nothing in `cancel_subscription` checks existing status before issuing the refund — line 4 sets `status = "canceled"` unconditionally, so there's no guard against this re-entry. Stripe's refund call is not idempotent on charge_id alone; repeating it without an idempotency key issues a second refund (until the charge is exhausted, then errors). So the exact failure mode the original finding worried about — a slow or failing call to Stripe — now risks a duplicate refund instead of a held DB lock.

The inverse also exists: if `refund()` fails in a way that isn't retried to success (permanent error, retries exhausted upstream), the subscription is already committed as `"canceled"` with no refund issued, and nothing in either file reconciles a "canceled but not refunded" state.

**Tradeoffs**

The fix correctly removes the coupling between the DB lock and the external call — that's real progress on fault containment for the database. But it does so by discarding the atomicity that the transaction used to provide for free: previously a failed refund couldn't leave a half-applied state relative to the lock; now cancellation and refund are two separately-retriable operations with no idempotency key and no persisted refund status to check against. The original bug (lock contention) traded for a subtler one (financial double-execution), and the second is harder to notice because it fails silently in production rather than showing up as contention under load.

**Next step**

Re-open as a new/regressed finding at the same severity (High): billing/subscriptions.py `cancel_subscription()` and billing/worker.py `handle_cancel_message()` together lack an idempotency guarantee across retries for the refund side effect. Recommend: (1) add a check in `cancel_subscription` that skips the refund call if the subscription is already marked refunded/canceled-with-refund, and (2) pass a Stripe idempotency key derived from `sub_id` or `charge_id` to `stripe_client.refund`, so a retried call is safe even without the DB-side guard. Validate with a test that forces `handle_cancel_message` through an exception + requeue path and asserts `stripe_client.refund` has effect at most once, not twice.
