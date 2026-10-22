"""Authenticated access to Ghost's Admin API."""
import os
import sys
import time


def admin_session():
    """(requests session, Admin API base URL), from GHOST_URL and
    GHOST_ADMIN_KEY ("id:secret"). Credentials come from the environment only."""
    import jwt
    import requests

    url = os.environ.get("GHOST_URL", "").rstrip("/")
    key = os.environ.get("GHOST_ADMIN_KEY", "")
    if not url or ":" not in key:
        sys.exit("Set GHOST_URL and GHOST_ADMIN_KEY (id:secret) to talk to Ghost")
    key_id, secret = key.split(":", 1)
    now = int(time.time())
    token = jwt.encode(
        {"iat": now, "exp": now + 300, "aud": "/admin/"},
        bytes.fromhex(secret),
        algorithm="HS256",
        headers={"kid": key_id},
    )
    session = requests.Session()
    session.headers.update({"Authorization": f"Ghost {token}", "Accept-Version": "v5.0"})
    return session, f"{url}/ghost/api/admin"
