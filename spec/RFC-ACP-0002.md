# RFC-ACP-0002: Agent Name Service Protocol

**Status:** Draft
**Version:** 0.1.0
**Created:** 2026-04-15

---

## Abstract

This document defines how an Agent Identifier (AID) is resolved to a
network endpoint and public key. Resolution uses DNS TXT records as the
discovery mechanism and HTTPS to fetch a signed Agent Manifest.

---

## 1. Resolution Algorithm

Given an AID `acp://example.com/my-agent`, resolution proceeds as:

```
1. Parse authority from AID:  "example.com"
2. Check local manifest cache (keyed by AID, honor TTL)
     -> cache hit: return cached manifest
3. Query DNS:  _acp.example.com  IN  TXT
4. Find the TXT record with prefix "v=acp1"
5. Extract the endpoint (ep=) field
6. GET {endpoint}/.well-known/acp-manifest.json
7. Parse and verify the Agent Manifest
8. Cache manifest, return
```

---

## 2. DNS TXT Record Format

```
_acp.{domain}  IN  TXT  "v=acp1; ep=https://example.com/acp"
```

Fields (semicolon-separated):

| Field | Required | Description |
|-------|----------|-------------|
| `v=acp1` | YES | Version tag. Must be first. |
| `ep=<url>` | YES | HTTPS endpoint accepting ACP messages |
| `ttl=<sec>` | NO | Override cache TTL (defaults to DNS TTL) |

Multiple TXT records MAY exist. Resolvers MUST use the first one with
`v=acp1`. If none is found, resolution fails.

---

## 3. Agent Manifest

The manifest is a JSON document served at `{endpoint}/.well-known/acp-manifest.json`.

```json
{
  "acp_version": "1.0",
  "agent_id": "acp://example.com/my-agent",
  "display_name": "My Agent",
  "endpoint": "https://example.com/acp",
  "public_key": {
    "kty": "OKP",
    "crv": "Ed25519",
    "x": "<base64url-encoded 32-byte public key>"
  },
  "capabilities": [
    "acp://cap.acp.dev/web-search/1.0"
  ],
  "protocols": ["ACP/1.0"],
  "status": "active",
  "manifest_created": "2026-04-15T00:00:00Z",
  "manifest_sig": "<ed25519 hex over all fields except manifest_sig>"
}
```

### 3.1 Manifest Verification

On receipt, the resolver MUST:

1. Verify `manifest_sig` using the public key in the manifest itself
   (self-signed; trust comes from DNS ownership)
2. Check `agent_id` matches the AID being resolved
3. Check `status` is not `"revoked"`
4. Verify `endpoint` uses HTTPS

If any check fails, the manifest MUST be rejected and resolution fails.

### 3.2 Status Values

| Value | Meaning |
|-------|---------|
| `active` | Normal operation |
| `maintenance` | Temporarily unavailable, retry later |
| `revoked` | Agent is decommissioned. Reject all further messages. |

---

## 4. Caching

Manifests MUST be cached. Default TTL: DNS TTL of the TXT record, minimum
60 seconds, maximum 24 hours.

If the `ttl=` field is present in the TXT record, it overrides the DNS TTL,
subject to the same 60s–24h bounds.

Cached manifests MUST be invalidated if:
- A received message fails signature verification (stale key, force re-resolve)
- The cache TTL expires

---

## 5. Federation and Fallbacks

Any organization MAY run its own ANS resolver. Resolvers are federated by
DNS: there is no central registry required for resolution to work.

If DNS is unavailable, implementations MAY fall back to:
- A locally configured static manifest file
- A previously cached manifest (serve stale, with a warning)
- Peer-provided manifest (included inline in the first message of a session)

**Inline manifest:** A sender MAY include their full manifest in the
`sender_manifest` optional field of the first REQUEST in a session. This
enables operation in air-gapped or DNS-blocked environments.

---

## 6. DID Authorities

For AIDs using DID authorities (e.g., `acp://did:key:z6Mk.../agent`),
resolution follows the W3C DID resolution specification for the given DID
method. The resolved DID Document MUST contain a `service` entry with
`type: "ACP"` and `serviceEndpoint` pointing to the agent's HTTPS endpoint.

DID resolution is OPTIONAL in this version. Implementations that do not
support DID authorities MUST return a clear error rather than silently failing.

---

## 7. Security Considerations

**DNS spoofing:** An attacker who can manipulate DNS responses can redirect
resolution to a malicious endpoint. Mitigations: use DNSSEC, pin manifest
public keys out-of-band for high-value agents.

**Manifest substitution:** The manifest endpoint must be served over HTTPS
with a valid certificate. An attacker with a valid cert for the domain can
substitute their public key. For high-trust scenarios, use certificate pinning
or out-of-band key verification.

**Revocation latency:** Revocation takes effect only after the cached
manifest expires. For immediate revocation, operators should set `ttl=60`
in the TXT record before publishing the revoked manifest.

---

## References

- RFC-ACP-0001: Agent Identifier Specification
- RFC-ACP-0010: Standard Message Envelope
- W3C DID Core: https://www.w3.org/TR/did-core/
