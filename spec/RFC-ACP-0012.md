# RFC-ACP-0012: Capability Negotiation Protocol

**Status:** Draft
**Version:** 0.1.0
**Created:** 2026-04-15

---

## Abstract

This document defines an optional two-message negotiation flow that allows
agents to agree on parameters, cost, and constraints before committing to
executing a capability. Negotiation is skipped for simple invocations and
required when the invoking agent needs confirmation of cost or adjusted
parameters.

---

## 1. When to Negotiate

Negotiation is OPTIONAL. Agents SHOULD negotiate when:
- The invoking agent has a budget constraint (max cost, max latency)
- The invoking agent needs to confirm the provider can meet a deadline
- The provider's capability manifest indicates parameters may be adjusted
- The task has irreversible side effects and pre-confirmation is desired

Agents SHOULD NOT negotiate for every call — it adds latency. Skip it for
simple, idempotent queries.

---

## 2. Message Flow

```
Invoker                              Provider
   |                                    |
   |-- NEGOTIATE_REQUEST -------------> |
   |   (capability, proposed inputs,    |
   |    constraints, budget)            |
   |                                    |
   |<-- NEGOTIATE_RESPONSE ----------- |
   |   (accepted/rejected,              |
   |    adjusted params, cost,          |
   |    commitment_id)                  |
   |                                    |
   |-- REQUEST (with commitment_id) --> |
   |                                    |
   |<-- RESPONSE ---------------------- |
```

If NEGOTIATE_RESPONSE is `accepted: false`, the invoker MUST NOT send the
REQUEST. It may try a different provider.

---

## 3. NEGOTIATE_REQUEST

Sent as a standard ACP REQUEST with `type: "REQUEST"` and
`body.capability: "acp://cap.acp.dev/negotiate/1.0"`.

```json
{
  "acp": "1.0",
  "id": "<uuid>",
  "type": "REQUEST",
  "from": "acp://invoker.example.com/agent",
  "to": "acp://provider.example.com/agent",
  "intent_ref": "sha256:...",
  "timestamp": "...",
  "body": {
    "capability": "acp://cap.acp.dev/negotiate/1.0",
    "inputs": {
      "target_capability": "acp://cap.acp.dev/web-search/1.0",
      "proposed_inputs": {
        "query": "latest APAC financial data",
        "num_results": 20
      },
      "constraints": {
        "max_latency_ms": 3000,
        "max_cost": 0.005,
        "deadline": "2026-04-15T17:00:00Z"
      }
    }
  },
  "sig": "..."
}
```

---

## 4. NEGOTIATE_RESPONSE

```json
{
  "acp": "1.0",
  "id": "<uuid>",
  "type": "RESPONSE",
  "from": "acp://provider.example.com/agent",
  "to": "acp://invoker.example.com/agent",
  "in_reply_to": "<negotiate request id>",
  "intent_ref": "sha256:...",
  "timestamp": "...",
  "body": {
    "status": "COMPLETED",
    "outputs": {
      "accepted": true,
      "adjusted_inputs": {
        "num_results": 15
      },
      "cost_estimate": {
        "amount": 0.003,
        "currency": "ACP-credit"
      },
      "latency_estimate_p95_ms": 2200,
      "commitment_id": "<uuid>",
      "commitment_expires": "2026-04-15T16:05:00Z"
    }
  },
  "sig": "..."
}
```

If `accepted: false`:
```json
{
  "outputs": {
    "accepted": false,
    "reason": "max_latency_ms constraint cannot be met (our p95 is 4000ms)",
    "alternatives": [
      {
        "adjusted_inputs": { "num_results": 5 },
        "latency_estimate_p95_ms": 2800
      }
    ]
  }
}
```

---

## 5. Commitment

A `commitment_id` in NEGOTIATE_RESPONSE is the provider's promise to:
- Accept the REQUEST with the agreed (or adjusted) inputs
- Honor the cost and latency estimates
- Process the task within the `commitment_expires` window

The invoker MUST include the `commitment_id` in the subsequent REQUEST:

```json
{
  "body": {
    "capability": "acp://cap.acp.dev/web-search/1.0",
    "commitment_id": "<uuid from negotiation>",
    "inputs": { ... }
  }
}
```

A provider that receives a REQUEST with a valid, unexpired `commitment_id`
MUST honor its commitment. If the commitment has expired, the provider
MUST return ACP-409 (Conflict).

Commitments without a subsequent REQUEST expire automatically at
`commitment_expires`. The provider releases reserved resources at that time.

---

## 6. Negotiation Timeout

If no NEGOTIATE_RESPONSE is received within 10 seconds (configurable),
the invoker SHOULD abort and either try a different provider or send the
REQUEST directly without negotiation.

---

## 7. Security Considerations

**Commitment abuse:** An invoker could acquire commitments without sending
REQUESTs, consuming provider resources. Providers SHOULD rate-limit negotiations
per invoking agent and track commitment redemption rates.

**Parameter bait-and-switch:** An invoker could negotiate with parameter A
but send REQUEST with parameter B. Providers MUST re-validate inputs on
REQUEST receipt, even when a commitment_id is present. The commitment only
guarantees acceptance of the *negotiated* inputs.

---

## References

- RFC-ACP-0003: Capability Advertisement Format
- RFC-ACP-0010: Standard Message Envelope
- RFC-ACP-0011: Message Type Registry
