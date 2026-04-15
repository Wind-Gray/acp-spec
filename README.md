> 🚨 **Status: Draft v0.1.0**
> This is a **work-in-progress specification** for the ACP (Agent Communication Protocol).
> Implementations are experimental. Breaking changes may occur without notice.

# ACP — Agent Communication Protocol

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![RFC Status: Draft](https://img.shields.io/badge/RFC%20Status-Draft-yellow.svg)](spec/)
[![Version: 0.1.0](https://img.shields.io/badge/Version-0.1.0-green.svg)](CHANGELOG.md)
[![Contributions Welcome](https://img.shields.io/badge/Contributions-Welcome-brightgreen.svg)](CONTRIBUTING.md)

An open protocol for AI agent communication. ACP defines how agents identify themselves, discover each other, exchange messages, and delegate tasks — regardless of who built them or what model they run on.

---

## The problem

Every AI agent platform today speaks its own language. Connecting an agent from one framework to a tool or service from another requires custom glue code on both sides. The result is the same N×M integration problem the web had before HTTP: solvable, but only by duplicating effort everywhere.

ACP is a single protocol that cuts that down to N+M.

---

## Design principles

### 1. Minimal core

If a developer can't read the spec on a Saturday and have a working client by Sunday, the spec is too complex. We cut until that's true.

Concrete limits:
- Message envelope: 8 required fields, no more
- Minimum working implementation: < 500 lines of Python
- Core RFC: < 30 pages

### 2. No required center

The protocol must work when:
- The root resolver is offline
- DNS is blocked or unavailable
- The foundation stops existing
- The internet fragments regionally

Every centralized component has a federated fallback. Nothing requires phoning home to operate.

### 3. Composable, not monolithic

```
Layer 1 (Transport)   <- Only mandatory layer
     |
Layer 2 (Identity)    <- Optional, strongly recommended
     |
Layer 3 (Messaging)   <- Optional, works with L1 alone
     |
Layer 4 (Security)    <- Optional modules, add as needed
     |
Layer 5 (Workflow)    <- Optional, application-layer choice
     |
Layer 6 (Semantic)    <- Optional, advanced use cases
```

Absence of any upper layer must not break lower layers.

### 4. Intent integrity

Traditional APIs lose the user's original intent at the first hop:
```
User -> Client -> API Call -> Action
                 ^
          intent is gone here
```

ACP carries intent through the entire execution chain:
```
Intent -> Agent A -> Agent B -> Agent C -> Action
   ^_________hash-locked throughout__________^
```

Any agent in the chain can verify: does this action still match what the user originally asked for?

---

## Architecture Overview

```
+--------------------------------------------------------------+
|  ACP System Vision & Governance                              |
+------------------+-----------------------+-------------------+
|  Protocol Stack  |  Core Protocol Suites |  Ecosystem        |
|                  |                       |                   |
|  L6: ACP-SEM     |  Identity Suite       |  Open Source      |
|  Semantic/Intent |  ACP-ID + ANS         |  Foundation       |
|                  |                       |                   |
|  L5: ACP-WF      |  Messaging Suite      |  RFC-Driven       |
|  Workflow        |  ACP-MSG + ACP-NEGO   |  Evolution        |
|                  |                       |                   |
|  L4: ACP-GOV     |  Payment Suite        |  Modular &        |
|  Security/Gov    |  ACP-PAY              |  Minimalist       |
|                  |                       |                   |
|  L3: ACP-MSG     |  Governance Suite     |  Reference        |
|  Messaging       |  ACP-GOV + ACP-AUD    |  Implementation   |
|                  |                       |                   |
|  L2: ACP-ID      +-----------------------+-------------------+
|  Identity        |  Standardization Bodies                   |
|                  |  IETF . NIST . W3C . ISO                  |
|  L1: ACP-TRANS   |                                           |
|  Transport       |                                           |
+------------------+-------------------------------------------+
```

---

## Protocol Stack

### Layer 1 — ACP-TRANS (Transport)

How bytes get from one agent to another. This layer knows nothing about the content.

**Required:**
- `HTTPS (TLS 1.3+)` — Standard public internet channel

**Optional:**
- `WSS` — streaming / real-time
- `HTTP/3 (QUIC)` — high-concurrency edge
- `Unix Socket` — same-host IPC

**Content-Type:**
- `application/acp+json` — JSON payload
- `application/acp+cbor` — Binary CBOR payload (IoT)

---

### Layer 2 — ACP-ID (Identity and Discovery)

#### Agent Identifier (AID)

```
Format:  acp://{authority}/{agent-path}

Valid examples:
  acp://openai.com/gpt-4o
  acp://anthropic.com/claude/prod
  acp://alice.example.com/scheduler
  acp://localhost/dev-agent

Invalid (MUST be rejected):
  acp://192.168.1.1/agent     <- IP addresses not permitted
  acp:///no-authority         <- Empty authority forbidden
```

#### Agent Name Service (ANS)

```
Resolution:
  1. Check local cache
  2. Query DNS TXT:  _acp.{domain}  IN  TXT  "v=acp1; ep=https://..."
  3. Fetch Agent Manifest from endpoint
  4. Verify Ed25519 signature
  5. Cache result (honor DNS TTL)
```

**Agent Manifest (agent-manifest.json):**
```json
{
  "acp_version": "1.0",
  "agent_id": "acp://example.com/my-agent",
  "endpoint": "https://example.com/acp",
  "public_key": { "kty": "OKP", "crv": "Ed25519", "x": "..." },
  "capabilities": ["acp://cap.acp.dev/web-search/1.0"],
  "manifest_sig": "<ed25519-signature>"
}
```

#### Capability-Based Discovery

Find agents by *what they can do*, not *where they are.*

```
Capability URI:  acp://cap.acp.dev/{name}/{version}

Discovery query:
  GET https://registry.acp.dev/discover
      ?capability=acp://cap.acp.dev/web-search/1.0
      &trust_level=VERIFIED
```

---

### Layer 3 — ACP-MSG (Messaging and Session)

#### Standard Message Envelope

```json
{
  "acp":        "1.0",
  "id":         "01HWKZ8F4XCRV1KBWBG4NJEZCS",
  "type":       "REQUEST",
  "from":       "acp://alice.com/scheduler",
  "to":         "acp://openai.com/gpt-4o",
  "intent_ref": "sha256:a3f9c7e2b1d4f8a0e5c3b7d2f6a9e1c4",
  "timestamp":  "2026-04-15T16:00:00Z",
  "sig":        "<sender-ed25519-signature>"
}
```

#### Message Types

| Type | Description |
|------|-------------|
| `REQUEST` | Initiate a task (REQUIRED) |
| `RESPONSE` | Synchronous reply (REQUIRED) |
| `ERROR` | Standardized error (REQUIRED) |
| `STREAM_START` / `STREAM_CHUNK` / `STREAM_END` | Streaming |
| `INTERRUPT` | Cancel a running task |
| `CHECKPOINT` | Save execution state |
| `HANDOFF` | Transfer task to another agent |
| `HITL_REQUEST` / `HITL_RESPONSE` | Human approval flow |

#### Error Codes

| Code | Meaning |
|------|---------|
| `ACP-400` | Malformed message |
| `ACP-401` | Identity verification failed |
| `ACP-403` | Insufficient permission |
| `ACP-404` | Capability not found |
| `ACP-429` | Rate limit exceeded |
| `ACP-500` | Internal agent error |

---

### Layer 4 — ACP-GOV (Security and Governance)

#### Zero-Trust Authorization

Every high-risk operation triggers a policy check:
```
ALLOW  -> Proceed. Write audit log.
DENY   -> Reject. Return ACP-403. Write audit log.
REVIEW -> Pause. Emit HITL_REQUEST. Await human decision.
```

#### Delegation Token

```json
{
  "type": "ACP-DelegationToken",
  "version": "1.0",
  "delegator": "acp://user:alice@personal/main",
  "delegatee": "acp://myapp.com/orchestrator/v2",
  "permissions": [
    { "action": "web_search", "scope": "*" },
    { "action": "write_file", "scope": "/tmp/acp-*" }
  ],
  "constraints": {
    "expires_at": "2026-04-15T20:00:00Z",
    "max_delegation_depth": 3,
    "require_hitl_for": ["send_email", "payment"]
  },
  "sig": "<alice-ed25519>"
}
```

**Invariant:** A child agent's permissions are always a strict subset of its parent's. Delegation can only restrict — never expand — authority.

#### Trust Levels

| Level | Description |
|-------|-------------|
| `SYSTEM` | Built-in, highest trust |
| `ORGANIZATIONAL` | Same-org certificate |
| `VERIFIED` | Third-party audited |
| `COMMUNITY` | Reputation-backed |
| `PUBLIC` | Identity verified |
| `ANONYMOUS` | Default, ephemeral |

#### Audit Log — tamper-evident, mandatory

```json
{
  "log_id": "01HWKZ8F...",
  "timestamp": "2026-04-15T16:00:00.000000001Z",
  "agent_id": "acp://worker.example.com/v1",
  "intent_ref": "sha256:a3f9...",
  "action": "write_file",
  "decision": "ALLOW",
  "prev_log_hash": "sha256:prev-entry-hash"
}
```

---

### Layer 5 — ACP-WF (Workflow)

#### Orchestration Patterns

**Sequential:** `A -> B -> C -> D`

**Parallel Fan-Out:**
```
     +-> B -+
A ---+-> C -+--> E
     +-> D -+
```

**Debate / Red Team:**
```
Proposer <-> Critic -> Judge
```

**Human Gate:**
```
[Task A] -> HITL Checkpoint -> [Task B]
                 ^
           pauses here until human approves
```

#### Checkpoint & Resume

Any task running across multiple agents can be saved mid-execution and resumed after failure — no re-running completed steps.

---

### Layer 6 — ACP-SEM (Semantic and Intent)

#### Intent Object

```json
{
  "intent_id":  "sha256:a3f9...",
  "acp_version": "1.0",
  "created_by": "acp://user:alice@personal/main",
  "created_at": "2026-04-15T15:00:00Z",
  "goal": "Prepare a Q1 financial summary for Alice's board meeting.",
  "context": {
    "urgency": "HIGH",
    "deadline": "2026-04-20T09:00:00Z"
  },
  "constraints": [
    "All figures must come from the official financial system.",
    "Must comply with SEC disclosure standards."
  ],
  "success_criteria": [
    "Executive summary under 500 words.",
    "Q1 vs Q4 comparison with charts."
  ],
  "human_checkpoints": ["After first draft, before sending."],
  "sig": "<alice-ed25519>"
}
```

The `intent_id` is the SHA-256 hash of the intent content. It's immutable and travels with every message in the chain.

#### Intent Proof Protocol (IPP)

Before any agent takes an irreversible action, it MUST verify:
1. Every signature in the delegation chain is valid
2. Permissions are non-escalating at every step (child subset of parent)
3. The action is within the granted permission scope
4. The action does not violate any intent constraint

---

## Core Protocol Suites

```
RFC-ACP-0001  Agent Identifier Specification (ACP-ID)
RFC-ACP-0002  Agent Name Service Protocol (ANS)
RFC-ACP-0003  Capability Advertisement Format
RFC-ACP-0010  Standard Message Envelope (ACP-MSG)
RFC-ACP-0011  Message Type Registry
RFC-ACP-0012  Capability Negotiation Protocol (ACP-NEGO)
RFC-ACP-0013  Session Lifecycle Management
RFC-ACP-0020  Intent Object Specification (ACP-SEM)
RFC-ACP-0021  Intent Proof Protocol (IPP)
RFC-ACP-0022  Capability Manifest Format
RFC-ACP-0030  Delegation Token Specification
RFC-ACP-0031  Policy Decision Protocol (ACP-GOV)
RFC-ACP-0032  Audit Log Format (ACP-AUD)
RFC-ACP-0033  Human-in-the-Loop Protocol (HITL)
RFC-ACP-0040  Agent Micropayment Protocol (ACP-PAY)    [optional]
RFC-ACP-0041  Conditional Settlement Protocol          [optional]
```

Full RFC documents are in the `/spec` directory.

---

## Interoperability

| Protocol | Relationship | Notes |
|----------|-------------|-------|
| **MCP** (Anthropic) | Complementary | MCP = models to tools. ACP = agents to agents. Bridge adapter included. |
| **A2A** (Google) | Aligned | Intent layer philosophy overlaps. Transport interoperable. |
| **OpenAI Agents SDK** | Adapter | Bidirectional bridge in `adapters/openai`. |
| **LangGraph** | Implementation | Can implement ACP workflow layer. |
| **W3C DID** | Identity | ACP `did:` authority maps directly to DID spec. |
| **REST/HTTP** | Compatible | ACP over HTTPS coexists with REST. Sidecar gateway for legacy systems. |

---

## Reference Implementation

### Minimum viable client (Python)

```python
"""acp_minimal.py — ACP/1.0 in ~50 lines"""
import json, uuid, httpx, dns.resolver
from datetime import datetime, timezone
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


class ACPAgent:
    def __init__(self, agent_id: str, private_key: Ed25519PrivateKey):
        self.agent_id = agent_id
        self.private_key = private_key

    def send(self, to: str, body: dict, intent_ref: str = None) -> dict:
        msg = {
            "acp": "1.0",
            "id": str(uuid.uuid4()),
            "type": "REQUEST",
            "from": self.agent_id,
            "to": to,
            "intent_ref": intent_ref,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "body": body,
        }
        msg["sig"] = self._sign(msg)
        endpoint = self._resolve(to)
        resp = httpx.post(endpoint, json=msg,
                          headers={"Content-Type": "application/acp+json"})
        resp.raise_for_status()
        return resp.json()

    def _sign(self, msg: dict) -> str:
        payload = json.dumps(
            {k: v for k, v in msg.items() if k != "sig"},
            sort_keys=True, separators=(",", ":")).encode()
        return self.private_key.sign(payload).hex()

    def _resolve(self, agent_id: str) -> str:
        domain = agent_id.split("//")[1].split("/")[0]
        for rdata in dns.resolver.resolve(f"_acp.{domain}", "TXT"):
            for s in rdata.strings:
                rec = s.decode()
                if "v=acp1" in rec and "ep=" in rec:
                    for part in rec.split(";"):
                        if part.strip().startswith("ep="):
                            return part.strip()[3:]
        raise ValueError(f"Cannot resolve: {agent_id}")
```

### Install

```bash
pip install acp-agent           # Python
npm install @acp-protocol/core  # TypeScript
go get github.com/acp-protocol/acp-go
cargo add acp-agent             # Rust
```

---

## Compliance Levels

| Level | Requirements |
|-------|-------------|
| **Core Compatible** | Passes core test suite, supports L1-3 |
| **Full Compatible** | Passes full test suite, supports L1-5, interop with 1 other impl |
| **Certified Secure** | Independent audit, supports L1-6, meets NIST AI RMF |

---

## Governance

**ACP Foundation** — neutral non-profit, modeled on Linux Foundation.

- No single org may hold >25% of TSC seats
- All meetings recorded and published
- Core RFC changes require 2/3 supermajority
- Anyone may submit an RFC draft
- Apache 2.0 + perpetual royalty-free patent grant

### RFC Process

```
Idea -> Draft -> Review -> Last Call (28 days) -> RFC -> Standard
```

Standard status requires two independent implementations passing
the interoperability test suite.

---

## Roadmap

### 0-6 months
- [ ] RFC-ACP-0001 through 0013 published
- [ ] Python + TypeScript reference implementations
- [ ] Interoperability test suite v0.1
- [ ] Developer mailing list open

Done when two independent implementations interoperate.

### 6-18 months
- [ ] Complete six-layer spec (all 14 RFCs)
- [ ] Go and Rust SDKs
- [ ] Sidecar gateway for legacy REST services
- [ ] ACP Foundation incorporated

### 18-36 months
- [ ] Adapters for MCP, OpenAI Agents, LangChain
- [ ] IETF Working Group proposal submitted
- [ ] Decentralized capability registry

### 36+ months
- [ ] IETF RFC published
- [ ] W3C DID alignment
- [ ] ISO standard track

---

## Repository Structure

```
acp-spec/
├── README.md
├── CONTRIBUTING.md
├── CHANGELOG.md
├── LICENSE                    <- Apache 2.0 + patent grant
├── spec/
│   ├── RFC-ACP-0001.md        <- Agent Identifier Specification
│   ├── RFC-ACP-0010.md        <- Standard Message Envelope
│   ├── RFC-ACP-0020.md        <- Intent Object Specification
│   └── TEMPLATE.md            <- RFC draft template
├── schemas/
│   ├── message-envelope.json
│   ├── agent-manifest.json
│   └── intent-object.json
├── reference/
│   └── python/
│       ├── acp_core.py        <- Full reference implementation
│       └── requirements.txt
└── adapters/
    ├── mcp/
    ├── openai-agents/
    └── langchain/
```

---

## FAQ

**Q: How is ACP different from MCP?**
MCP connects models to tools. ACP connects agents to other agents. They are complementary — an MCP tool can be wrapped as an ACP capability.

**Q: Why not REST + OpenAPI?**
REST has no concept of agent identity, delegation chains, intent provenance, or human oversight. ACP adds exactly what REST omits.

**Q: Can I use ACP commercially?**
Yes. Apache 2.0 + royalty-free patent grant. Build products, sell services. You cannot own the standard.

**Q: What if the Foundation shuts down?**
RFCs are immutable once published. Repos are mirrored across multiple orgs. The registry has federated fallbacks. The spec doesn't disappear if the org does.

---

## License

ACP Specification (c) 2026 ACP Foundation Contributors

Apache License, Version 2.0 — with perpetual, royalty-free patent grant
covering all compliant implementations of this specification.

