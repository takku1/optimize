# queue consumer: retries the handler on any exception, no dedup/idempotency key
def handle_cancel_message(msg):
    try:
        cancel_subscription(msg.sub_id)
    except Exception:
        requeue(msg)  # will call cancel_subscription again, including stripe_client.refund
