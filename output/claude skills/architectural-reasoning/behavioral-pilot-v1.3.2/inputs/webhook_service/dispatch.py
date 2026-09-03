from shared.http_client import http_client, DEFAULT_TIMEOUT

def dispatch(webhook_id, payload):
    hook = db.query(Webhook).get(webhook_id)
    return http_client.post(hook.url, json=payload, timeout=DEFAULT_TIMEOUT)
