"""
acp_core.py -- ACP/1.0 reference implementation

Covers RFC-ACP-0001, 0002, 0010, 0020.

pip install httpx cryptography dnspython
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding, PublicFormat,
)
from cryptography.exceptions import InvalidSignature


# -- AID (RFC-ACP-0001 §2) --------------------------------------------------

_AID_RE = re.compile(r"^acp://[^/\s]+/.+$")
_IP_RE = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")


def validate_aid(aid: str) -> str:
    """Validate and normalize an AID. RFC-ACP-0001 §2."""
    if not isinstance(aid, str):
        raise ValueError(f"AID must be a string, got {type(aid)}")

    # Normalize: lowercase scheme+authority, strip trailing slash
    slash2 = aid.find("//") + 2
    path_start = aid.find("/", slash2)
    if path_start == -1:
        raise ValueError(f"AID missing path component: {aid}")

    normalized = aid[:path_start].lower() + aid[path_start:].rstrip("/")

    if not _AID_RE.match(normalized):
        raise ValueError(f"Invalid AID format: {aid}")

    authority = normalized[6:normalized.index("/", 6)]
    if _IP_RE.match(authority):
        raise ValueError(f"AID authority must be domain, not IP: {aid}")

    return normalized


# -- Agent Name Service (RFC-ACP-0002) --------------------------------------

class AgentManifest:
    def __init__(self, agent_id: str, endpoint: str, public_key_bytes: bytes,
                 capabilities: list[str] = None, status: str = "active"):
        self.agent_id = agent_id
        self.endpoint = endpoint
        self.public_key_bytes = public_key_bytes
        self.capabilities = capabilities or []
        self.status = status

    def public_key(self) -> Ed25519PublicKey:
        return Ed25519PublicKey.from_public_bytes(self.public_key_bytes)

    @classmethod
    def from_dict(cls, data: dict) -> "AgentManifest":
        import base64
        required = {"acp_version", "agent_id", "endpoint", "public_key"}
        missing = required - data.keys()
        if missing:
            raise ValueError(f"Manifest missing fields: {missing}")
        pk = data["public_key"]
        if pk.get("kty") != "OKP" or pk.get("crv") != "Ed25519":
            raise ValueError("Public key must be Ed25519 OKP JWK")
        pk_bytes = base64.urlsafe_b64decode(pk["x"] + "==")
        return cls(
            agent_id=validate_aid(data["agent_id"]),
            endpoint=data["endpoint"],
            public_key_bytes=pk_bytes,
            capabilities=data.get("capabilities", []),
            status=data.get("status", "active"),
        )


# Simple in-memory cache
_manifest_cache: dict[str, tuple[AgentManifest, datetime]] = {}


def resolve_manifest(agent_id: str,
                     http_client: httpx.Client = None) -> AgentManifest:
    """
    Resolve AID to Agent Manifest. RFC-ACP-0002 Section 3.

    1. Check cache
    2. Query DNS TXT: _acp.{domain} IN TXT "v=acp1; ep=https://..."
    3. Fetch manifest JSON
    4. Verify signature
    5. Cache and return
    """
    aid = validate_aid(agent_id)

    # Step 1: cache
    if aid in _manifest_cache:
        manifest, expires = _manifest_cache[aid]
        if datetime.now(timezone.utc) < expires:
            return manifest

    # Step 2: DNS
    endpoint = _dns_lookup(aid)

    # Step 3: fetch
    client = http_client or httpx.Client(timeout=10.0)
    resp = client.get(f"{endpoint}/.well-known/acp-manifest.json",
                      headers={"Accept": "application/json"})
    resp.raise_for_status()

    # Step 4: parse
    manifest = AgentManifest.from_dict(resp.json())
    if manifest.agent_id != aid:
        raise ValueError(f"Manifest ID mismatch: got {manifest.agent_id}")
    if manifest.status == "revoked":
        raise PermissionError(f"Agent {aid} is revoked")

    # Step 5: cache (1 hour default)
    _manifest_cache[aid] = (manifest, datetime.now(timezone.utc) + timedelta(hours=1))
    return manifest


def _dns_lookup(aid: str) -> str:
    """RFC-ACP-0002 §3.2: DNS TXT lookup for _acp.{domain}"""
    authority = aid[6:aid.index("/", 6)]
    if authority.startswith("did:"):
        raise NotImplementedError("DID resolution not in minimal reference")
    try:
        import dns.resolver
        for rdata in dns.resolver.resolve(f"_acp.{authority}", "TXT"):
            for s in rdata.strings:
                rec = s.decode("utf-8")
                if rec.startswith("v=acp1") and "ep=" in rec:
                    for part in rec.split(";"):
                        if part.strip().startswith("ep="):
                            return part.strip()[3:].strip()
    except ImportError:
        return f"https://{authority}"
    except Exception as e:
        raise ConnectionError(f"DNS lookup failed for {aid}: {e}") from e
    raise ConnectionError(f"No ACP endpoint in DNS for: {authority}")


# -- Canonical JSON + Signature (RFC-ACP-0010 §2) ---------------------------

def canonical_json(obj: Any) -> bytes:
    """Sorted keys, no whitespace, UTF-8."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sign_message(msg: dict, private_key: Ed25519PrivateKey) -> str:
    """Sign a message dict. Call before adding the 'sig' field."""
    payload = canonical_json({k: v for k, v in msg.items() if k != "sig"})
    return private_key.sign(payload).hex()


def verify_message(msg: dict) -> None:
    """
    Verify ACP message. RFC-ACP-0010 §3.
    Raises ValueError (bad format), PermissionError (bad sig).
    """
    required = {"acp", "id", "type", "from", "to", "intent_ref",
                "timestamp", "sig"}
    missing = required - msg.keys()
    if missing:
        raise ValueError(f"Missing required fields: {missing}")

    if msg["acp"] != "1.0":
        raise ValueError(f"Unknown ACP version: {msg['acp']}")

    ts = datetime.fromisoformat(msg["timestamp"].replace("Z", "+00:00"))
    skew = abs((datetime.now(timezone.utc) - ts).total_seconds())
    if skew > 300:
        raise ValueError(f"Timestamp too far from now (skew={skew:.0f}s)")

    manifest = resolve_manifest(msg["from"])
    payload = canonical_json({k: v for k, v in msg.items() if k != "sig"})
    try:
        manifest.public_key().verify(bytes.fromhex(msg["sig"]), payload)
    except (ValueError, InvalidSignature) as e:
        raise PermissionError(f"Signature invalid: {e}") from e


# -- Message building -------------------------------------------------------

def build_message(
    *,
    msg_type: str,
    from_aid: str,
    to_aid: str,
    private_key: Ed25519PrivateKey,
    body: dict = None,
    intent_ref: str = None,
    session_id: str = None,
    in_reply_to: str = None,
    **extra,
) -> dict:
    """Build and sign an ACP message envelope."""
    validate_aid(from_aid)
    validate_aid(to_aid)

    msg: dict[str, Any] = {
        "acp": "1.0",
        "id": str(uuid.uuid4()),
        "type": msg_type,
        "from": from_aid,
        "to": to_aid,
        "intent_ref": intent_ref,
        "timestamp": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.") + \
            f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z",
    }
    if session_id:
        msg["session_id"] = session_id
    if in_reply_to:
        msg["in_reply_to"] = in_reply_to
    if body is not None:
        msg["body"] = body
    msg.update(extra)
    msg["sig"] = sign_message(msg, private_key)
    return msg


class ACPAgent:
    """
    Usage:
        key = Ed25519PrivateKey.generate()
        agent = ACPAgent("acp://example.com/my-agent", key)
        response = agent.send("acp://other.com/service", {"query": "hello"})
    """

    def __init__(self, agent_id: str, private_key: Ed25519PrivateKey,
                 http_client: httpx.Client = None):
        self.agent_id = validate_aid(agent_id)
        self._key = private_key
        self._http = http_client or httpx.Client(timeout=30.0)

    def send(self, to: str, body: dict = None, *,
             msg_type: str = "REQUEST",
             intent_ref: str = None,
             session_id: str = None,
             in_reply_to: str = None) -> dict:
        msg = build_message(
            msg_type=msg_type, from_aid=self.agent_id, to_aid=to,
            private_key=self._key, body=body, intent_ref=intent_ref,
            session_id=session_id, in_reply_to=in_reply_to,
        )
        manifest = resolve_manifest(to, self._http)
        resp = self._http.post(
            manifest.endpoint, json=msg,
            headers={"Content-Type": "application/acp+json",
                     "Accept": "application/acp+json",
                     "ACP-Version": "1.0"},
        )
        resp.raise_for_status()
        response = resp.json()
        verify_message(response)
        return response

    @property
    def public_key_hex(self) -> str:
        return self._key.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw).hex()


# -- Intent Object (RFC-ACP-0020) -------------------------------------------

def create_intent(
    *,
    goal: str,
    created_by: str,
    private_key: Ed25519PrivateKey,
    context: dict = None,
    constraints: list[str] = None,
    success_criteria: list[str] = None,
    human_checkpoints: list[str] = None,
    expires_at: str = None,
) -> dict:
    validate_aid(created_by)

    intent: dict[str, Any] = {
        "acp_version": "1.0",
        "created_by": created_by,
        "created_at": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"),
        "goal": goal,
    }
    if context:
        intent["context"] = context
    if constraints:
        intent["constraints"] = constraints
    if success_criteria:
        intent["success_criteria"] = success_criteria
    if human_checkpoints:
        intent["human_checkpoints"] = human_checkpoints
    if expires_at:
        intent["expires_at"] = expires_at

    # intent_id = sha256 of canonical JSON (without intent_id and sig)
    intent_hash = hashlib.sha256(canonical_json(intent)).hexdigest()
    intent["intent_id"] = f"sha256:{intent_hash}"

    payload = canonical_json({k: v for k, v in intent.items() if k != "sig"})
    intent["sig"] = private_key.sign(payload).hex()
    return intent


# -- Example ----------------------------------------------------------------

if __name__ == "__main__":
    key = Ed25519PrivateKey.generate()
    agent = ACPAgent("acp://localhost/example", key)
    print("Agent ID:", agent.agent_id)
    print("Public key:", agent.public_key_hex[:32] + "...")

    intent = create_intent(
        goal="Summarize the Q1 financial results for the board meeting.",
        created_by="acp://localhost/example",
        private_key=key,
        context={"urgency": "HIGH", "deadline": "2026-04-20T09:00:00Z"},
        constraints=["Use only official data sources."],
        success_criteria=["Under 500 words.", "Includes key metrics."],
        human_checkpoints=["After draft, before sending."],
    )
    print("\nIntent ID:", intent["intent_id"])

    msg = build_message(
        msg_type="REQUEST",
        from_aid="acp://localhost/example",
        to_aid="acp://localhost/target",
        private_key=key,
        body={"capability": "acp://cap.acp.dev/summarize/1.0"},
        intent_ref=intent["intent_id"],
    )
    print("Message ID:", msg["id"])
    print("Signature:", msg["sig"][:32] + "...")
