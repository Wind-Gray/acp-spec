# RFC-ACP-0021: Intent Proof Protocol

**Status:** Draft
**Version:** 0.1.0
**Created:** 2026-04-15

---

## Abstract

This document specifies the Intent Proof Protocol (IPP), the mechanism by
which any agent in a delegation chain can verify that its actions remain
authorized by the original intent creator. IPP combines the Intent Object
(RFC-ACP-0020) with a chain of signed Delegation Tokens (RFC-ACP-0030) to
produce a proof that is verifiable at any depth without contacting the
original signer.

---

## 1. The Problem IPP Solves

A single delegation creates a simple authorization:
```
Alice --[token]--> AgentB: "you may do X on my behalf"
```

Multiple delegations create a chain:
```
Alice --[token1]--> AgentB --[token2]--> AgentC --[token3]--> AgentD
```

Without IPP, AgentD has no way to know:
1. Whether Alice actually authorized this chain
2. Whether permissions escalated somewhere along the way
3. Whether the action AgentD is about to take is within the original intent

IPP answers all three.

---

## 2. Proof Structure

An IPP proof is the combination of:
- An `intent_ref` pointing to the Intent Object
- A `delegation_chain` array of Delegation Tokens from creator to current agent

Carried in the `delegation_token` field of any ACP message:

```json
{
  "type": "ACP-DelegationToken",
  "version": "1.0",
  "intent_ref": "sha256:a3f9...",
  "delegation_chain": [
    {
      "seq": 1,
      "delegator": "acp://user:alice@alice.example.com/main",
      "delegatee": "acp://orchestrator.myapp.com/v2",
      "permissions": ["web_search", "read_file", "write_file"],
      "constraints": {
        "expires_at": "2026-04-15T20:00:00Z",
        "max_depth": 3
      },
      "sig": "<alice's Ed25519 over CanonicalJSON of this link>"
    },
    {
      "seq": 2,
      "delegator": "acp://orchestrator.myapp.com/v2",
      "delegatee": "acp://analyst.example.com/v1",
      "permissions": ["read_file"],
      "constraints": {
        "expires_at": "2026-04-15T20:00:00Z",
        "max_depth": 2
      },
      "sig": "<orchestrator's Ed25519 over CanonicalJSON of this link>"
    }
  ],
  "jti": "<unique token id>",
  "issued_at": "2026-04-15T16:00:00Z"
}
```

---

## 3. Verification Algorithm

Every agent MUST run this before taking any action under delegated authority.

```
VERIFY_IPP(msg, proposed_action):

  proof = msg.delegation_token
  intent = FETCH_INTENT(proof.intent_ref)  // RFC-ACP-0020

  // Step 1: Verify intent signature
  VERIFY_SIG(intent.sig, intent.created_by)
  -> if invalid: DENY "intent signature invalid"

  // Step 2: Check intent expiry
  if intent.expires_at < NOW():
    DENY "intent expired"

  // Step 3: Verify each link in the chain
  chain = proof.delegation_chain
  for link in chain:
    VERIFY_SIG(link.sig, link.delegator)
    -> if invalid: DENY "chain link {link.seq} signature invalid"

  // Step 4: Verify chain is contiguous
  for i = 1..len(chain)-1:
    if chain[i].delegator != chain[i-1].delegatee:
      DENY "chain broken at link {i}"

  // Step 5: Verify first link was signed by intent creator
  if chain[0].delegator != intent.created_by:
    DENY "chain does not originate from intent creator"

  // Step 6: Verify receiving agent is the last delegatee
  if msg.from != chain[-1].delegatee:
    DENY "sender is not the final delegatee"

  // Step 7: Permissions are non-escalating (strict subset at each step)
  for i = 1..len(chain)-1:
    parent_perms = set(chain[i-1].permissions)
    child_perms  = set(chain[i].permissions)
    if not child_perms.issubset(parent_perms):
      DENY "permission escalation at link {i}"

  // Step 8: Proposed action is within current permissions
  if proposed_action.type not in set(chain[-1].permissions):
    DENY "action not in delegated permissions"

  // Step 9: Check expiry of all links
  for link in chain:
    if link.constraints.expires_at < NOW():
      DENY "link {link.seq} expired"

  // Step 10: Check max_depth not exceeded
  declared_max = chain[0].constraints.max_depth
  if len(chain) > declared_max:
    DENY "delegation depth {len(chain)} exceeds max {declared_max}"

  // Step 11: Check action against intent constraints
  for constraint in intent.constraints:
    if VIOLATES(proposed_action, constraint):
      DENY "action violates intent constraint: {constraint}"

  // All checks passed
  ALLOW
```

The formal invariant guaranteed by Step 7:
```
∀ i ∈ [1, n]:  permissions(chain[i]) ⊆ permissions(chain[i-1])
```

This is monotone: adding more links cannot introduce new permissions.

---

## 4. Constraint Evaluation (Step 11)

Constraint evaluation is intentionally imprecise — constraints are natural
language and not machine-executable in the general case.

Implementations MUST apply constraint evaluation to well-known action types:

| Action type | Constraint keywords to check |
|-------------|------------------------------|
| `send_email` | "do not send", "no external sharing" |
| `write_file` | "read-only", "do not modify" |
| `payment` | amount thresholds, "no financial transactions" |
| `delete` | "do not delete", "irreversible" |
| `web_search` | domain restrictions |

When a constraint cannot be evaluated (too ambiguous), agents MUST escalate
to HITL rather than either allowing or denying silently.

---

## 5. Building a Proof

When an agent re-delegates to a sub-agent, it extends the chain:

```python
def delegate_to(
    sub_agent_aid: str,
    permissions: list[str],
    expires_at: str,
    parent_proof: dict,
    private_key: Ed25519PrivateKey,
) -> dict:
    parent_chain = parent_proof["delegation_chain"]
    my_entry = parent_chain[-1]

    # Verify permissions do not escalate
    parent_perms = set(my_entry["permissions"])
    assert set(permissions).issubset(parent_perms), "Cannot grant permissions you don't have"

    new_link = {
        "seq": len(parent_chain) + 1,
        "delegator": my_entry["delegatee"],
        "delegatee": sub_agent_aid,
        "permissions": permissions,
        "constraints": {
            "expires_at": expires_at,
            "max_depth": my_entry["constraints"]["max_depth"] - 1,
        },
    }
    payload = canonical_json(new_link)
    new_link["sig"] = private_key.sign(payload).hex()

    return {
        "type": "ACP-DelegationToken",
        "version": "1.0",
        "intent_ref": parent_proof["intent_ref"],
        "delegation_chain": parent_chain + [new_link],
        "jti": str(uuid.uuid4()),
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }
```

---

## 6. Root Delegation (No Parent Proof)

When the intent creator delegates directly to the first agent, there is no
parent chain. The creator builds the initial token:

```json
{
  "type": "ACP-DelegationToken",
  "version": "1.0",
  "intent_ref": "sha256:a3f9...",
  "delegation_chain": [
    {
      "seq": 1,
      "delegator": "acp://user:alice@alice.example.com/main",
      "delegatee": "acp://orchestrator.myapp.com/v2",
      "permissions": ["web_search", "read_file", "write_file"],
      "constraints": {
        "expires_at": "2026-04-15T20:00:00Z",
        "max_depth": 3
      },
      "sig": "<alice's signature>"
    }
  ],
  "jti": "<uuid>",
  "issued_at": "2026-04-15T16:00:00Z"
}
```

---

## 7. Security Considerations

**Chain length attacks:** An attacker controlling a middle agent could try
to insert extra links to escalate permissions before trimming. Step 7
prevents this by checking the subset invariant at every step.

**Replay of expired chains:** Old tokens could be replayed after a
permission revocation. Mitigation: short expiry times on delegation links,
and checking expiry on every verification (Step 9).

**Constraint ambiguity as an attack surface:** If agents are too permissive
in constraint interpretation, attackers may craft intents with vague
constraints. Defense: when in doubt, escalate to HITL.

---

## References

- RFC-ACP-0010: Standard Message Envelope
- RFC-ACP-0020: Intent Object Specification
- RFC-ACP-0030: Delegation Token Specification
- RFC-ACP-0033: Human-in-the-Loop Protocol
