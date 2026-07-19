"""ProfileStore backed by Cloud Firestore over its REST API.

Uses the Firebase web projectId + apiKey (both public by design; access is
governed by Firestore security rules, not the key). No service account needed.
Requires a Firestore database to exist and its rules to allow the writes.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

from .base import ProfileStore

_BASE = "https://firestore.googleapis.com/v1"


class FirestoreError(RuntimeError):
    """A Firestore REST call failed; carries the HTTP status and body."""

    def __init__(self, code: int, body: str):
        self.code = code
        self.body = body
        super().__init__(f"Firestore returned {code}: {body}")


# Python values <-> Firestore's typed Value format.

def _to_value(value) -> dict:
    if value is None:
        return {"nullValue": None}
    if isinstance(value, bool):
        return {"booleanValue": value}
    if isinstance(value, int):
        return {"integerValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, str):
        return {"stringValue": value}
    if isinstance(value, list):
        return {"arrayValue": {"values": [_to_value(v) for v in value]}}
    if isinstance(value, dict):
        return {"mapValue": {"fields": {k: _to_value(v) for k, v in value.items()}}}
    return {"stringValue": str(value)}


def _from_value(value: dict):
    if "nullValue" in value:
        return None
    if "booleanValue" in value:
        return value["booleanValue"]
    if "integerValue" in value:
        return int(value["integerValue"])
    if "doubleValue" in value:
        return value["doubleValue"]
    if "stringValue" in value:
        return value["stringValue"]
    if "timestampValue" in value:
        return value["timestampValue"]
    if "arrayValue" in value:
        return [_from_value(v) for v in value["arrayValue"].get("values", [])]
    if "mapValue" in value:
        return {k: _from_value(v) for k, v in value["mapValue"].get("fields", {}).items()}
    return None


def to_fields(record: dict) -> dict:
    return {k: _to_value(v) for k, v in record.items()}


def from_fields(fields: dict) -> dict:
    return {k: _from_value(v) for k, v in fields.items()}


class FirestoreProfileStore(ProfileStore):
    def __init__(self, project_id: str, api_key: str, collection: str = "profiles"):
        self.project_id = project_id
        self.api_key = api_key
        self.collection = collection
        self._docs = f"{_BASE}/projects/{project_id}/databases/(default)/documents"

    def save(self, profile: dict) -> str:
        profile_id = profile.get("profile_id") or uuid.uuid4().hex[:12]
        record = {
            "profile_id": profile_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "confirmed",
            **profile,
        }
        url = f"{self._docs}/{self.collection}?documentId={profile_id}&key={self.api_key}"
        self._request("POST", url, {"fields": to_fields(record)})
        return profile_id

    def get(self, profile_id: str) -> dict | None:
        url = f"{self._docs}/{self.collection}/{profile_id}?key={self.api_key}"
        try:
            doc = self._request("GET", url)
        except FirestoreError as exc:
            if exc.code == 404:
                return None
            raise
        return from_fields(doc.get("fields", {}))

    def list_summaries(self) -> list[dict]:
        url = f"{self._docs}/{self.collection}?key={self.api_key}&pageSize=300"
        data = self._request("GET", url)
        summaries = []
        for doc in data.get("documents", []):
            record = from_fields(doc.get("fields", {}))
            summaries.append({
                "profile_id": record.get("profile_id"),
                "created_at": record.get("created_at"),
                "owner_uid": record.get("owner_uid"),
                "person_name": (record.get("household") or {}).get("person_name"),
                "document_count": len(record.get("documents") or []),
            })
        return sorted(summaries, key=lambda s: s.get("created_at") or "", reverse=True)

    def _request(self, method: str, url: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(
            url, data=data, method=method, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise FirestoreError(exc.code, exc.read().decode("utf-8", "replace")) from None
