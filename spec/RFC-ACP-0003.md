# RFC-ACP-0003: Capability Advertisement Format

**Status:** Draft
**Version:** 0.1.0
**Created:** 2026-04-15

---

## Abstract

This document defines the format for advertising what an ACP agent can do.
A Capability Manifest describes one capability: its identifier, input/output
schemas, prerequisites, and cost estimates. Agents publish manifests so
that other agents can discover and invoke them without prior arrangement.

---

## 1. Capability URI

Every capability has a globally unique URI:

```
acp://cap.{domain}/{name}/{version}

Examples:
  acp://cap.acp.dev/web-search/1.0        <- maintained by ACP Foundation
  acp://cap.mycompany.com/invoice/2.1     <- organization-specific
  acp://cap.acp.dev/code-execution/1.0
  acp://cap.acp.dev/image-generation/1.0
  acp://cap.acp.dev/summarize/1.0
  acp://cap.acp.dev/translate/1.0
```

The `cap.acp.dev` namespace is reserved for capabilities maintained by the
ACP Foundation and reviewed by the community. Organizations SHOULD use their
own domain for custom capabilities.

Version format: `{major}.{minor}`. Minor increments are backward-compatible.
Major increments are breaking changes.

---

## 2. Capability Manifest Format

```json
{
  "acp_version": "1.0",
  "capability_id": "acp://cap.acp.dev/web-search/1.0",
  "name": "Web Search",
  "description": "Searches the web and returns ranked results with snippets.",
  "provider": "acp://search.example.com/agent",
  "version": "1.0.3",

  "input_schema": {
    "type": "object",
    "required": ["query"],
    "properties": {
      "query": {
        "type": "string",
        "maxLength": 500
      },
      "num_results": {
        "type": "integer",
        "minimum": 1,
        "maximum": 50,
        "default": 10
      },
      "language": {
        "type": "string",
        "default": "en"
      }
    }
  },

  "output_schema": {
    "type": "object",
    "properties": {
      "results": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "title":   { "type": "string" },
            "url":     { "type": "string", "format": "uri" },
            "snippet": { "type": "string" }
          }
        }
      },
      "total_found": { "type": "integer" }
    }
  },

  "prerequisites": {
    "trust_level": "PUBLIC",
    "permissions": [],
    "min_delegation_depth": 0
  },

  "performance": {
    "latency_p50_ms": 800,
    "latency_p95_ms": 2000,
    "latency_p99_ms": 5000
  },

  "cost": {
    "model": "per_call",
    "amount": 0.001,
    "currency": "ACP-credit"
  },

  "rate_limits": {
    "requests_per_minute": 60,
    "requests_per_day": 10000
  },

  "languages": ["en", "zh", "de", "fr", "ja"],

  "capability_sig": "<provider ed25519 hex over all fields except capability_sig>"
}
```

---

## 3. Field Definitions

**`capability_id`** — The capability URI this manifest describes.

**`provider`** — AID of the agent that provides this capability.

**`input_schema`** — JSON Schema for the `body.inputs` field of REQUEST
messages invoking this capability. Implementations MUST validate inputs
against this schema before sending.

**`output_schema`** — JSON Schema for `body.outputs` in RESPONSE messages.

**`prerequisites.trust_level`** — Minimum trust level required to invoke.
See RFC-ACP-0030 for trust level definitions.

**`prerequisites.permissions`** — List of permissions the invoking agent's
delegation token must include. Empty list means no special permissions needed.

**`cost`** — Estimated cost per invocation. The `currency` field is free-form.
`"ACP-credit"` is a notional unit; implementations may map this to real
currencies via the ACP-PAY layer (RFC-ACP-0040). This field is informational —
actual billing is handled out of band unless ACP-PAY is used.

**`capability_sig`** — Ed25519 signature by the provider over CanonicalJSON
of all other fields. Verifiable using the provider's public key from their
Agent Manifest (RFC-ACP-0002).

---

## 4. Capability Discovery

### 4.1 Agent Manifest Listing

The simplest discovery: read an agent's manifest (RFC-ACP-0002). The
`capabilities` array lists capability URIs the agent supports. Fetch the
capability manifest for each to get full schema details.

```
GET {endpoint}/.well-known/acp-capabilities/{capability-name}.json
```

### 4.2 Registry Query

A capability registry aggregates manifests from many providers. The ACP
Foundation operates a reference registry at `registry.acp.dev`, but any
organization MAY operate their own.

```http
GET https://registry.acp.dev/v1/search
    ?capability=acp://cap.acp.dev/web-search/1.0
    &trust_level=VERIFIED
    &language=zh
    &latency_max_ms=3000

Response 200:
{
  "results": [
    {
      "capability_id": "acp://cap.acp.dev/web-search/1.0",
      "provider": "acp://search.example.com/agent",
      "trust_level": "VERIFIED",
      "latency_p95_ms": 1200,
      "cost_per_call": 0.001,
      "manifest_uri": "https://search.example.com/acp/capabilities/web-search.json"
    }
  ],
  "total": 1
}
```

### 4.3 Capability Negotiation

Before invoking a capability, agents MAY negotiate parameters. See
RFC-ACP-0012 for the negotiation protocol.

---

## 5. Versioning

When a provider updates a capability:

- **Patch** (`1.0.x`): Bug fixes only. Do not publish a new manifest; update
  the existing one in place.
- **Minor** (`1.x.0`): New optional input fields, new optional output fields.
  Publish a new manifest. Old consumers still work.
- **Major** (`x.0.0`): Breaking changes. Publish under a new capability URI
  (e.g., `/web-search/2.0`). Keep the old version running during transition.

---

## 6. Security Considerations

**Schema injection:** Input schemas define what the invoking agent sends.
A malicious provider could publish a schema that tricks agents into sending
sensitive data. Invoking agents SHOULD review capability manifests from
unknown providers before use.

**Capability spoofing:** Anyone can claim to implement `acp://cap.acp.dev/...`.
Trust comes from the `trust_level` field verified via the provider's Agent
Manifest, not from the capability URI alone.

---

## References

- RFC-ACP-0001: Agent Identifier Specification
- RFC-ACP-0002: Agent Name Service Protocol
- RFC-ACP-0012: Capability Negotiation Protocol
- RFC-ACP-0030: Delegation Token Specification
