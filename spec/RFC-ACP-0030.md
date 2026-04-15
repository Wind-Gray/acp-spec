# RFC-ACP-0030: Delegation Token Specification

**Status:** Draft
**Version:** 0.1.0
**Created:** 2026-04-15

---

## Abstract

This document specifies the structure, issuance, and verification rules for
ACP Delegation Tokens. A Delegation Token grants a named agent a specific
set of permissions to act on behalf of a principal, within defined
constraints. Tokens form chains as authority is re-delegated; the chain
structure and verification algorithm are specified in RFC-ACP-0021.

---

## 1. What a Delegation Token Is

A Delegation Token is a signed data structure that answers:
- **Who** authorized the action (the delegator)
- **To whom** authority was granted (the delegatee)
- **What** they are allowed to do (permissions)
- **Under what constraints** (expiry, depth, custom conditions)

Tokens are bearer credentials: any agent in possession of a valid token
may present it. Signature verification prevents forgery.

---

## 2. Token Structure

```json
{
  "type": "ACP-DelegationToken",
  "version": "1.0",
  "intent_ref": "sha256:<hex>",
  "delegation_chain": [
    {
      "seq": 1,
      "delegator": "<AID>",
      "delegatee": "<AID>",
      "permissions": ["<permission strings>"],
      "constraints": {
        "expires_at": "<ISO-8601 datetime>",
        "max_depth": 3,
        "allowed_capabilities": ["<capability URIs>"],
        "allowed_domains": ["<domain patterns>"],
        "custom": {}
      },
      "sig": "<Ed25519 hex over CanonicalJSON of this link excluding sig>"
    }
  ],
  "jti": "<UUIDv4>",
  "issued_at": "<ISO-8601 datetime>"
}
```

---

## 3. Field Definitions

### Token-level fields

**`type`** — MUST be `"ACP-DelegationToken"`. Allows parsers to identify
token documents.

**`version`** — MUST be `"1.0"` for tokens conforming to this RFC.

**`intent_ref`** — Content-addressed reference to the Intent Object
(RFC-ACP-0020) this token is issued under. Format:
`"sha256:<hex-of-sha256>"`.

**`delegation_chain`** — Ordered array of delegation links. The first link
(`seq: 1`) MUST have `delegator` equal to `intent.created_by`. Each
subsequent link MUST have `delegator` equal to the previous link's
`delegatee`. See RFC-ACP-0021 for chain verification.

**`jti`** (JWT ID) — UUIDv4 uniquely identifying this token instance.
Used for revocation tracking and replay prevention. Receivers MUST reject
tokens whose `jti` they have previously accepted.

**`issued_at`** — When this token was assembled. Not a security-critical
field; used for audit and debugging.

### Chain link fields

**`seq`** — 1-based sequence number. MUST be monotonically increasing
across the chain. Receivers MUST reject chains with duplicate or
out-of-order `seq` values.

**`delegator`** — AID of the agent granting authority.

**`delegatee`** — AID of the agent receiving authority.

**`permissions`** — Array of permission strings granted to the delegatee.
MUST be a subset of the delegator's own permissions at the time of
issuance. The first link's permissions are bounded by the intent's
declared allowed actions.

**`constraints.expires_at`** (required) — ISO-8601 datetime after which
this link is invalid. Receivers MUST reject links whose `expires_at` is in
the past.

**`constraints.max_depth`** (required in first link) — Maximum total chain
length permitted. If the chain length exceeds this value, the token is
invalid. Each re-delegation MUST decrement this by 1.

**`constraints.allowed_capabilities`** (optional) — If present, the
delegatee may only invoke capabilities whose URI appears in this list.
Acts as a whitelist on top of the permissions set.

**`constraints.allowed_domains`** (optional) — If present, the delegatee
may only contact agents whose AID authority component matches one of these
patterns. Patterns follow the same syntax as HTTP Host headers; `*.` prefix
matches any subdomain.

**`constraints.custom`** (optional) — Arbitrary key-value pairs for
application-specific constraints. Receivers that do not understand a custom
constraint MUST treat it as unenforceable and escalate to HITL per
RFC-ACP-0033.

**`sig`** — Ed25519 signature by the delegator over CanonicalJSON of the
link object with the `sig` field excluded. Verifiable using the
delegator's public key from their Agent Manifest (RFC-ACP-0002).

---

## 4. Permission Strings

Permissions are strings from a shared vocabulary. The following are
standardized:

| Permission | Meaning |
|------------|---------|
| `web_search` | May invoke web search capabilities |
| `read_file` | May read files from storage capabilities |
| `write_file` | May write files to storage capabilities |
| `delete_file` | May delete files |
| `execute_code` | May invoke code execution capabilities |
| `send_email` | May send email via messaging capabilities |
| `send_message` | May send messages (non-email) |
| `payment` | May initiate financial transactions |
| `read_user_data` | May access user-linked data stores |
| `write_user_data` | May modify user-linked data stores |
| `spawn_agent` | May create and delegate to sub-agents |
| `hitl_bypass` | May skip HITL checkpoints marked as optional |
| `*` | All permissions (root delegation only) |

Organizations MAY define custom permissions using reverse-domain notation:
`com.mycompany.custom-permission`.

The `*` wildcard permission MUST only appear in the first link of a
chain (direct grant from a human intent creator) and MUST NOT be
re-delegated. Any chain link after `seq: 1` that contains `*` MUST be
rejected.

---

## 5. Trust Levels

Trust levels describe the verified status of an agent in a PKI sense.
They are recorded in Agent Manifests (RFC-ACP-0002) and checked by
capability providers (RFC-ACP-0022).

| Level | Description |
|-------|-------------|
| `PUBLIC` | Identity claimed but not independently verified |
| `VERIFIED` | Identity verified by a trust authority |
| `TRUSTED` | Explicitly trusted by the provider organization |
| `PRIVATE` | Internal-only agent; no external trust claims |

Trust levels are not carried in delegation tokens. They are properties of
the agent's manifest, evaluated at invocation time by the provider.

---

## 6. Token Issuance

### 6.1 Root Token (intent creator to first agent)

The intent creator issues the root token:

```python
def issue_root_token(
    intent: dict,
    first_agent_aid: str,
    permissions: list[str],
    expires_at: str,
    max_depth: int,
    private_key: Ed25519PrivateKey,
) -> dict:
    link = {
        "seq": 1,
        "delegator": intent["created_by"],
        "delegatee": first_agent_aid,
        "permissions": permissions,
        "constraints": {
            "expires_at": expires_at,
            "max_depth": max_depth,
        },
    }
    payload = canonical_json(link)
    link["sig"] = private_key.sign(payload).hex()

    return {
        "type": "ACP-DelegationToken",
        "version": "1.0",
        "intent_ref": intent["intent_id"],
        "delegation_chain": [link],
        "jti": str(uuid.uuid4()),
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }
```

### 6.2 Re-delegation (agent to sub-agent)

Agents extending the chain MUST:
1. Verify their own received token is valid (RFC-ACP-0021).
2. Ensure new permissions are a subset of their own.
3. Decrement `max_depth` by 1.
4. Set `expires_at` no later than their own link's `expires_at`.

See RFC-ACP-0021 §5 for the `delegate_to()` reference implementation.

### 6.3 Depth Enforcement

If an agent's link has `max_depth: 1`, it MUST NOT re-delegate. Any
attempt to call `delegate_to()` in this state MUST raise an error before
signing the new link.

---

## 7. Token Transmission

Delegation tokens are attached to ACP messages via the `delegation_token`
field of the message envelope (RFC-ACP-0010):

```json
{
  "acp": "1.0",
  "id": "...",
  "type": "REQUEST",
  "from": "...",
  "to": "...",
  "intent_ref": "sha256:...",
  "delegation_token": {
    "type": "ACP-DelegationToken",
    "version": "1.0",
    "intent_ref": "sha256:...",
    "delegation_chain": [ ... ],
    "jti": "...",
    "issued_at": "..."
  },
  "timestamp": "...",
  "sig": "..."
}
```

The `intent_ref` in the message envelope MUST match the `intent_ref` in
the embedded delegation token. A mismatch MUST cause the receiver to
return ACP-400.

---

## 8. Revocation

ACP does not define a real-time revocation mechanism (no OCSP equivalent).
Revocation is handled by:

1. **Short expiry times.** Links SHOULD expire within hours. The maximum
   recommended `expires_at` window for most use cases is 24 hours.

2. **Revocation lists.** Agents MAY publish a list of revoked `jti` values
   at a well-known endpoint:
   ```
   GET {endpoint}/.well-known/acp-revoked-tokens.json
   Response: { "revoked_jtis": ["<uuid>", ...], "as_of": "<ISO-8601>" }
   ```
   Receivers SHOULD check this list for tokens with long expiry windows.

3. **Intent cancellation.** Cancelling an Intent Object (RFC-ACP-0020)
   implicitly revokes all tokens referencing that intent. Receivers that
   cache intents MUST re-fetch before accepting a token if the cached
   intent is older than 5 minutes.

---

## 9. Security Considerations

**Permission escalation:** The spec prohibits escalation at each chain link
(child permissions must be a subset of parent). Verification MUST be done
cryptographically at every link, not just at the boundary. A compromised
middle agent cannot silently add permissions.

**Token theft:** Tokens are bearer credentials. A stolen token grants the
thief the permissions within it until expiry. Mitigations: short expiry,
binding tokens to sessions via `session_id`, and transport-layer encryption
(TLS required).

**Replay attacks:** The `jti` field prevents a captured token from being
replayed. Receivers MUST maintain a `jti` seen-set for at least the
maximum token lifetime.

**Forged issuer:** A chain link's `delegator` AID is not authenticated by
itself. Authentication comes from the `sig` field, which must verify
against the delegator's public key. Implementations MUST resolve the
delegator's public key from their Agent Manifest before verifying the
signature — never from the token itself.

---

## References

- RFC-ACP-0001: Agent Identifier Specification
- RFC-ACP-0002: Agent Name Service Protocol
- RFC-ACP-0010: Standard Message Envelope
- RFC-ACP-0020: Intent Object Specification
- RFC-ACP-0021: Intent Proof Protocol
- RFC-ACP-0033: Human-in-the-Loop Protocol
