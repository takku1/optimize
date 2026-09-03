import httpx

DEFAULT_TIMEOUT = 5
http_client = httpx.Client()
# used identically by every outbound caller in this service
