# RFC-ACP-0022: Capability Manifest Format

**Status:** Draft
**Version:** 0.1.0
**Created:** 2026-04-15

---

## Abstract

This document defines the formal schema and behavioral contracts for ACP
Capability Manifests. While RFC-ACP-0003 covers capability discovery and
advertisement, this document specifies the precise semantics of each manifest
field, capability composition rules, and behavioral classification that
providers MUST declare and invokers MUST respect.

---

## 1. Manifest Schema (normative)

```json
{
  "$schema": "https://acp.dev/schemas/capability-manifest/1.0.json",
  "acp_version": "1.0",
  "capability_id": "<URI>",
  "name": "<string>",
  "description": "<string>",
  "provider": "<AID>",
  "version": "<semver>",
  "status": "STABLE | BETA | DEPRECATED",

  "input_schema": { "<JSON Schema>" },
  "output_schema": { "<JSON Schema>" },

  "behavior": {
    "idempotent": true,
    "side_effects": ["none | network | storage | financial | external-api"],
    "reversible": true,
    "max_duration_ms": 30000
  },

  "prerequisites": {
    "trust_level": "PUBLIC | VERIFIED | TRUSTED | PRIVATE",
    "permissions": ["<permission strings>"],
    "min_delegation_depth": 0,
    "required_intent_constraints": []
  },

  "performance": {
    "latency_p50_ms": 0,
    "latency_p95_ms": 0,
    "latency_p99_ms": 0,
    "throughput_rps": 0
  },

  "cost": {
    "model": "per_call | per_token | per_byte | subscription | free",
    "amount": 0.0,
    "currency": "ACP-credit",
    "billing_ref": "<URI to billing documentation>"
  },

  "rate_limits": {
    "requests_per_minute": 0,
    "requests_per_day": 0,
    "burst_size": 0
  },

  "composition": {
    "depends_on": ["<capability URIs>"],
    "incompatible_with": ["<capability URIs>"],
    "pipeline_position": "source | transform | sink | any"
  },

  "languages": ["<BCP-47 language tags>"],
  "tags": ["<free-form strings for search>"],
  "deprecated_by": "<capability URI or null>",
  "documentation_uri": "<URI>",

  "capability_sig": "<Ed25519 hex over CanonicalJSON of all other fields>"
}
```

---

## 2. Field Definitions

### 2.1 Identity Fields

**`capability_id`** (required) — The capability URI as defined in RFC-ACP-0003.
Format: `acp://cap.{domain}/{name}/{major}.{minor}`.

**`version`** (required) — Semver string (`major.minor.patch`) for the
manifest itself. The `major.minor` must match the version in `capability_id`.

**`status`** (required):
- `STABLE` — production-ready, breaking changes require a major version bump
- `BETA` — interface may change with minor version bumps; use in production at own risk
- `DEPRECATED` — no new invocations should use this; see `deprecated_by`

### 2.2 Schema Fields

**`input_schema`** (required) — JSON Schema (Draft 2020-12) for
`body.inputs` in REQUEST messages. Providers MUST validate inputs before
processing. Invokers MUST validate inputs before sending.

**`output_schema`** (required) — JSON Schema for `body.outputs` in RESPONSE
messages. Providers MUST produce outputs conforming to this schema.

If either schema allows arbitrary additional properties (`additionalProperties:
true`), the provider MUST document the extension mechanism via
`documentation_uri`.

### 2.3 Behavior Fields

**`behavior.idempotent`** — If `true`, calling the capability twice with
identical inputs produces identical outputs and no additional side effects.
Invokers MAY retry idempotent capabilities on timeout without risk of
duplication.

**`behavior.side_effects`** — Array of side effect categories:
- `none` — purely computational, no external state changes
- `network` — makes outbound network requests
- `storage` — reads or writes durable storage
- `financial` — triggers financial transactions
- `external-api` — calls third-party APIs with their own rate limits or costs

If `side_effects` contains `financial`, the capability MUST require trust
level `VERIFIED` or higher in `prerequisites.trust_level`.

**`behavior.reversible`** — If `false`, completed invocations cannot be
undone. Invokers MUST warn users or require explicit confirmation before
invoking irreversible capabilities.

**`behavior.max_duration_ms`** — Maximum wall-clock time the provider may
take. Providers MUST return a response (including ERROR) within this window.
Invokers MAY treat silence beyond this time as ACP-408.

### 2.4 Prerequisites Fields

**`prerequisites.trust_level`** — Minimum trust level from the invoker's
Agent Manifest (RFC-ACP-0002). Values in ascending order:
`PUBLIC < VERIFIED < TRUSTED < PRIVATE`.

**`prerequisites.permissions`** — Permissions that MUST appear in the
invoker's current delegation token (RFC-ACP-0030). Empty list means no
delegated permission is required beyond identity verification.

**`prerequisites.min_delegation_depth`** — Minimum position in the
delegation chain where this capability may be invoked. `0` means the intent
creator may call directly. `1` means a delegated agent must be involved.
This allows capabilities to enforce that a human-controlled agent is
somewhere in the chain.

**`prerequisites.required_intent_constraints`** — List of constraint
keywords that MUST appear in the intent object's `constraints` array before
this capability will execute. Example: `["approved_by_legal"]`.

### 2.5 Cost Fields

**`cost.model`** values:
- `per_call` — flat fee per REQUEST
- `per_token` — billed by token count (for LLM-backed capabilities)
- `per_byte` — billed by input/output data volume
- `subscription` — covered under a pre-arranged plan; no per-call charge
- `free` — no charge

When `cost.model` is `per_token` or `per_byte`, the `amount` field is the
unit price. The RESPONSE SHOULD include actual usage in `body.usage`:

```json
{
  "body": {
    "usage": {
      "input_tokens": 150,
      "output_tokens": 320,
      "total_cost": 0.00235
    }
  }
}
```

### 2.6 Composition Fields

**`composition.depends_on`** — Capability URIs that this capability calls
internally. Informational; helps orchestrators understand transitive
permission requirements.

**`composition.incompatible_with`** — Capability URIs that must not be
active in the same session or workflow. Example: two capabilities that
write to conflicting state.

**`composition.pipeline_position`**:
- `source` — produces data from external systems; no required inputs from prior steps
- `transform` — takes inputs and produces transformed outputs; typical middle step
- `sink` — writes data to an external destination; produces no meaningful outputs
- `any` — no constraint on position

---

## 3. Trust Level Hierarchy

```
PUBLIC    — Any agent may invoke without any trust relationship
VERIFIED  — Invoker's identity must be verified (public key registered)
TRUSTED   — Invoker must appear in provider's explicit trust list
PRIVATE   — Only agents sharing the provider's private network or org
```

A provider advertising `trust_level: "PUBLIC"` accepts invocations from
any agent that can construct a valid signed ACP message.

A provider advertising `trust_level: "TRUSTED"` MUST maintain a trust list
(by AID or domain) and reject agents not on it with ACP-403.

---

## 4. Behavioral Contracts

Providers that publish a manifest make the following binding commitments:

1. **Schema conformance**: Outputs will conform to `output_schema` for all
   inputs that conform to `input_schema`.

2. **Duration bound**: Responses will arrive within `max_duration_ms`.

3. **Idempotency**: If `idempotent: true`, the provider guarantees no
   additional side effects from retried calls with the same inputs.

4. **Side effect disclosure**: All categories of side effects are listed
   in `behavior.side_effects`. Undisclosed side effects are a spec violation.

5. **Cost accuracy**: Actual costs will not exceed 2× the declared cost
   estimate without a prior negotiation (RFC-ACP-0012).

Invokers are entitled to report manifest violations to the operator of the
capability registry used for discovery.

---

## 5. Deprecation

When a capability is deprecated:

1. Set `status: "DEPRECATED"` in the manifest.
2. Set `deprecated_by` to the URI of the replacement capability.
3. Keep the capability operational for a minimum of 90 days after setting
   `status: "DEPRECATED"`.
4. Return a deprecation warning in RESPONSE body:

```json
{
  "body": {
    "outputs": { ... },
    "warnings": [
      {
        "code": "CAPABILITY_DEPRECATED",
        "message": "This capability is deprecated. Use acp://cap.acp.dev/web-search/2.0",
        "sunset_date": "2026-07-15"
      }
    ]
  }
}
```

---

## 6. Manifest Signing

The `capability_sig` field is an Ed25519 signature by the provider's
private key over the CanonicalJSON of all other fields (sorted keys, no
whitespace, UTF-8 encoded, `capability_sig` excluded from input).

Verification uses the provider's public key from their Agent Manifest
(RFC-ACP-0002). An invoker that cannot verify the signature MUST treat
the manifest as untrusted and SHOULD NOT invoke the capability.

---

## 7. Security Considerations

**Overly broad input schemas:** A manifest with `additionalProperties: true`
and no constraint on sensitive field names could be used to harvest
unintended data from orchestrators. Invokers should treat such manifests
with suspicion.

**Side effect under-declaration:** A provider that omits `financial` from
`side_effects` when it does trigger payments is in spec violation. Invokers
relying on this field for safety checks should verify through the
negotiation protocol (RFC-ACP-0012) for high-stakes actions.

**Stale manifests:** Cached manifests may not reflect current provider
state. Invokers SHOULD revalidate manifests older than their TTL before
invoking capabilities with irreversible or financial side effects.

---

## References

- RFC-ACP-0002: Agent Name Service Protocol
- RFC-ACP-0003: Capability Advertisement Format
- RFC-ACP-0010: Standard Message Envelope
- RFC-ACP-0012: Capability Negotiation Protocol
- RFC-ACP-0030: Delegation Token Specification
