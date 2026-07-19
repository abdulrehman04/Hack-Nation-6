"""Verify Firebase ID tokens via the Identity Toolkit REST API.

Confirms a token is valid and belongs to this project, and returns the user's
uid. No service account needed; uses the public web API key.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

_LOOKUP = "https://identitytoolkit.googleapis.com/v1/accounts:lookup"


class AuthError(RuntimeError):
    """An ID token could not be verified."""


def verify_id_token(id_token: str, api_key: str) -> str:
    """Return the uid for a valid ID token, or raise AuthError."""
    url = f"{_LOOKUP}?key={api_key}"
    data = json.dumps({"idToken": id_token}).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise AuthError(f"token rejected ({exc.code})") from None
    users = body.get("users") or []
    if not users or "localId" not in users[0]:
        raise AuthError("token did not resolve to a user")
    return users[0]["localId"]
