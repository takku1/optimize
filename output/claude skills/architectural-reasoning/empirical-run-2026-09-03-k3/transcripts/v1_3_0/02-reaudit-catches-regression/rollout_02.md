## Re-audit: cancel_subscription refund handling

**Prior finding (2026-08-01) — RESOLVED.** billing/subscriptions.py:1-8 confirms `stripe_client.refund(sub.charge_id)` now executes at line 7, after the `with db.transaction()` block (lines 2-5) has exited and the `SELECT ... FOR UPDATE` lock has been released by `db.commit()` at line 5. The DB row lock no longer spans the Stripe network call. The fix matches the recommendation.

**New finding introduced by the fix — High.** Evidence: billing/subscriptions.py:4-7 together with billing/worker.py:1-6.

Moving the refund outside the transaction split one atomic operation into two independently-failable steps: (1) commit `status = "canceled"`, (2) call Stripe. Nothing links their outcomes. billing/worker.py's own comment states the consumer has "no dedup/idempotency key" and retries the handler on *any* exception (worker.py:1,5-6). So:

- If `stripe_client.refund` raises after actually succeeding on Stripe's side (timeout, dropped response, 5xx after processing) — a normal partial-failure mode for a synchronous external call — `handle_cancel_message` requeues, and the retry runs `cancel_subscription` again. The DB re-query at subscriptions.py:3 finds `status` already `"canceled"` (harmless re-write), but line 7 unconditionally re-issues `stripe_client.refund(sub.charge_id)` with no idempotency key. The customer is refunded twice.
- Because status is committed *before* the refund call (line 5 precedes line 7), there is no signal in `Subscription` distinguishing "canceled, refund pending" from "canceled, refund issued" — a retry can't tell whether it's the first attempt or a duplicate.

This is the same class of defect as the original finding — an external call with unmanaged failure semantics — just relocated: previously it endangered a DB lock, now it endangers billing correctness (double refund) because it interacts with the worker's at-least-once retry.

**Recommendation:** Pass a stable idempotency key to `stripe_client.refund` (e.g. derived from `sub_id` or `charge_id` — Stripe's API supports an `Idempotency-Key` header natively) so retries of the same logical cancellation collapse to one refund. Also add a `refund_status` (or similar) field to `Subscription`, set only after Stripe confirms the refund, so replays can check "already refunded" before calling out again, rather than relying on Stripe-side idempotency alone to paper over the split between the DB commit and the external call.

**Next step:** Confirm with the Stripe client wrapper whether it already supports/enforces an idempotency key anywhere in the codebase (not shown in the two files in scope here); if not, that's the smallest fix that closes the new gap without re-introducing the original lock-holding problem.
