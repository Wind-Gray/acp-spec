# RFC-ACP-0020: Intent Object Specification

**Status:** Draft
**Version:** 0.1.0
**Created:** 2026-04-15

---

## Abstract

This document defines the Intent Object. An Intent Object is a signed,
immutable record of a user's original goal, created once and carried as a
hash through every hop in a multi-agent chain. Any agent in the chain can
retrieve it and verify that its action is consistent with the original
request.

---

## 1. Motivation

### The Intent Loss Problem

In existing agent frameworks, user intent dissolves into API calls at the
first hop. By the time the third sub-agent executes, there is no
machine-readable record of *why* the chain was initiated.

This causes two failures:

**Alignment drift.** Sub-agents optimize for their immediate task without
access to the constraints the human specified upstream.

**Auditability failure.** When a workflow causes harm, there is no way to
trace why each agent made each decision.

### Solution

A signed JSON document created by the intent originator, referenced by
hash (`intent_ref`) in every ACP message in the resulting workflow. Any
agent can retrieve it and check whether its action falls within the
original goal and constraints.

---

## 2. Intent Object Schema

```json
{
  "acp_version":       "1.0",
  "intent_id":         "sha256:<hex>",
  "created_by":        "<AID>",
  "created_at":        "<ISO-8601-UTC>",
  "goal":              "<string, required>",
  "context":           { ... },
  "constraints":       [ "<string>", ... ],
  "success_criteria":  [ "<string>", ... ],
  "human_checkpoints": [ "<string>", ... ],
  "expires_at":        "<ISO-8601-UTC>",
  "sig":               "<ed25519-hex>"
}
```

### 2.1 Field Definitions

**`intent_id`** — SHA-256 of CanonicalJSON of all fields except
`intent_id` and `sig`, prefixed `"sha256:"`.

```
intent_id = "sha256:" + hex(SHA-256(CanonicalJSON(intent_without_id_and_sig)))
```

Implementations MUST recompute and verify this hash on receipt.

**`goal`** — Natural language description of the desired outcome.
MUST NOT be empty. Max 1000 characters recommended.

**`constraints`** — What MUST NOT happen. Expressed in natural language.
Each constraint SHOULD be specific and verifiable.

**`success_criteria`** — What constitutes completion. Positive statements.

**`human_checkpoints`** — Points where execution MUST pause for human
approval (HITL_REQUEST). Implementations MUST honor these.

**`expires_at`** — Optional. Intent is invalid after this time.

**`sig`** — Ed25519 signature by `created_by` over CanonicalJSON of
all fields except `sig`.

---

## 3. Complete Example

```json
{
  "acp_version": "1.0",
  "intent_id": "sha256:a3f9c7e2b1d4f8a0e5c3b7d2f6a9e1c4b8d3e7f2a1c5b9d4",
  "created_by": "acp://user:alice@alice.example.com/main",
  "created_at": "2026-04-15T15:00:00.000Z",
  "goal": "Prepare a Q1 financial summary for Alice's board meeting on April 20.",
  "context": {
    "urgency": "HIGH",
    "deadline": "2026-04-20T09:00:00Z",
    "audience": "Board of Directors",
    "background": "Q1 ended. Focus on APAC growth and margin vs Q4."
  },
  "constraints": [
    "All figures must come from the official financial system, not estimates.",
    "Do not include material non-public information (MNPI).",
    "Output must comply with SEC Regulation FD."
  ],
  "success_criteria": [
    "Executive summary under 500 words.",
    "Q1 vs Q4 revenue comparison with percentage changes.",
    "Forward-looking risk matrix covering at least 3 risks."
  ],
  "human_checkpoints": [
    "After first complete draft, before any content is shared externally."
  ],
  "expires_at": "2026-04-20T09:00:00Z",
  "sig": "a3b4c5d6e7f8...ed25519 hex..."
}
```

---

## 4. Intent Proof Protocol (IPP)

### 4.1 Problem

Alice delegates to OrchestratorAgent, which delegates to 10 sub-agents.
Sub-agent #8 is about to take an irreversible action. Is this still
what Alice intended?

### 4.2 Solution: Delegation Proof Chain

Every message operating under delegated authority MUST include a
`delegation_token` (RFC-ACP-0030) containing the signed delegation chain.

### 4.3 Verification Algorithm

```
VERIFY_INTENT_PROOF(msg, action):

  1. Fetch intent = RESOLVE(msg.intent_ref)
  2. Verify intent.sig with intent.created_by public key   -> DENY if invalid
  3. chain = msg.delegation_token.delegation_chain
  4. For each link in chain:
       Verify link.sig with link.delegator public key      -> DENY if invalid
  5. For i = 1..len(chain)-1:
       if not chain[i].permissions subset of chain[i-1].permissions:
         DENY  <- permission escalation attempt
  6. if action.type not in chain[-1].permissions:
       DENY  <- action not authorized
  7. For each constraint in intent.constraints:
       if action VIOLATES constraint:
         DENY
  8. ALLOW
```

**Formal invariant:** permissions(chain[i]) subset-of permissions(chain[i-1])
for all i. This cannot be violated by adding more links.

---

## 5. Privacy Considerations

- Transmit Intent Objects only over TLS 1.3+
- Log `intent_id` hash only, not full content, in shared audit systems
- Delete expired intents from local storage on request
- Intent content may contain sensitive business context — treat accordingly

---

## 6. Security Considerations

**Intent substitution attack:** An attacker controlling a sub-agent might
substitute a different `intent_ref` to authorize unauthorized actions.
Prevented by: delegation tokens include `intent_ref` in their signed payload;
any mismatch causes DENY.

**Constraint ambiguity:** Constraints are natural language and subject to
interpretation. When ambiguous, implementations SHOULD escalate to HITL
rather than proceeding with the ambiguous interpretation.

---

## References

- RFC-ACP-0001: Agent Identifier Specification
- RFC-ACP-0010: Standard Message Envelope
- RFC-ACP-0030: Delegation Token Specification
- RFC-ACP-0033: Human-in-the-Loop Protocol
