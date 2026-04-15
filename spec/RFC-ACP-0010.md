# RFC-ACP-0010: Standard Message Envelope

**Status:** Draft
**Version:** 0.1.0
**Created:** 2026-04-15

---

## Abstract

This document defines the standard message envelope for ACP/1.0.
The envelope has exactly 8 required fields. An implementation that
correctly sends and receives these 8 fields is a valid ACP/1.0 node.

---

## 1. Required Fields

```json
{
  "acp":        "1.0",
  "id":         "<UUIDv7>",
  "type":       "<MESSAGE_TYPE>",
  "from":       "<AID>",
  "to":         "<AID>",
  "intent_ref": "<sha256:hex> | null",
  "timestamp":  "<ISO-8601-UTC>",
  "sig":        "<ed25519-hex>"
}
```

### 1.1 Field Definitions

**`acp`** — Protocol version. MUST be `"1.0"`. Reject unknown versions.

**`id`** — UUIDv7 (time-ordered). MUST be globally unique.
Reject duplicates within a 24-hour deduplication window.

**`type`** — One of the values in the Message Type Registry (RFC-ACP-0011).
Core implementations MUST support: `REQUEST`, `RESPONSE`, `ERROR`.

**`from`** — AID of the sender. MUST be valid per RFC-ACP-0001.

**`to`** — AID of the recipient. MUST be valid per RFC-ACP-0001.

**`intent_ref`** — SHA-256 hash of the originating Intent Object
(RFC-ACP-0020), prefixed `"sha256:"`. MUST be `null` if no
formal intent governs this message. This field MUST NOT be omitted.

**`timestamp`** — ISO 8601 UTC datetime with millisecond precision.
Reject messages with timestamps more than 5 minutes from local clock
(configurable; MUST NOT exceed 1 hour).

**`sig`** — Ed25519 signature, lowercase hex (128 chars).
Computed over CanonicalJSON of all fields except `sig`.

---

## 2. Signature Algorithm

```
sig = Ed25519Sign(
    key = sender_private_key,
    msg = UTF-8(CanonicalJSON(envelope_without_sig))
)

CanonicalJSON rules:
  - Keys sorted lexicographically (ascending)
  - No whitespace
  - UTF-8 encoding
```

---

## 3. Verification Algorithm

```
VERIFY(msg):
  1. Check all 8 required fields present     -> ACP-400 if missing
  2. Check msg.acp == "1.0"                  -> ACP-400 if unknown
  3. Check timestamp within skew window      -> ACP-400 if expired
  4. Check msg.id not in dedup cache         -> ACP-400 if duplicate
  5. Resolve sender manifest (RFC-ACP-0002)
  6. Ed25519Verify(manifest.public_key,
                   hex_decode(msg.sig),
                   canonical_json_bytes)     -> ACP-401 if invalid
  7. ACCEPT
```

---

## 4. Optional Standard Fields

These fields have standardized semantics when present.

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | UUIDv7 | Session this message belongs to |
| `in_reply_to` | UUIDv7 | id of the message being replied to (REQUIRED on RESPONSE/ERROR) |
| `body` | object | Free-form payload; schema defined by capability |
| `delegation_token` | object | Required when acting under delegated authority |
| `trace_id` | string | Distributed tracing; propagate unchanged |

---

## 5. Complete Examples

### REQUEST

```json
{
  "acp": "1.0",
  "id": "01hwkz8f-4xcr-7v1k-bwbg-4njezcsabc12",
  "type": "REQUEST",
  "from": "acp://alice.example.com/scheduler",
  "to": "acp://analyst.company.com/financial-agent",
  "intent_ref": "sha256:a3f9c7e2b1d4f8a0e5c3b7d2f6a9e1c4b8d3e7f2",
  "session_id": "01hwkz8f-0000-7000-0000-000000000001",
  "timestamp": "2026-04-15T16:00:00.000Z",
  "body": {
    "capability": "acp://cap.acp.dev/financial-analysis/1.0",
    "inputs": {
      "data_uri": "acp://storage.alice.com/q1-data.csv",
      "analysis_type": "summary"
    }
  },
  "sig": "<scheduler-ed25519-signature>"
}
```

### RESPONSE

```json
{
  "acp": "1.0",
  "id": "01hwkz8f-4xcr-7v1k-bwbg-4njezcsabc99",
  "type": "RESPONSE",
  "from": "acp://analyst.company.com/financial-agent",
  "to": "acp://alice.example.com/scheduler",
  "intent_ref": "sha256:a3f9c7e2b1d4f8a0e5c3b7d2f6a9e1c4b8d3e7f2",
  "in_reply_to": "01hwkz8f-4xcr-7v1k-bwbg-4njezcsabc12",
  "timestamp": "2026-04-15T16:00:05.231Z",
  "body": {
    "status": "COMPLETED",
    "confidence": 0.94,
    "outputs": {
      "insights": ["APAC revenue grew 23% QoQ."],
      "charts": []
    },
    "execution": { "tokens_used": 3400, "wall_time_ms": 5231 }
  },
  "sig": "<financial-agent-ed25519-signature>"
}
```

### ERROR

```json
{
  "acp": "1.0",
  "id": "01hwkz8f-4xcr-7err-bwbg-4njezcsabc00",
  "type": "ERROR",
  "from": "acp://analyst.company.com/financial-agent",
  "to": "acp://alice.example.com/scheduler",
  "intent_ref": "sha256:a3f9c7e2b1d4f8a0e5c3b7d2f6a9e1c4b8d3e7f2",
  "in_reply_to": "01hwkz8f-4xcr-7v1k-bwbg-4njezcsabc12",
  "timestamp": "2026-04-15T16:00:01.010Z",
  "body": {
    "code": "ACP-403",
    "title": "Insufficient Permission",
    "detail": "Delegation token does not include 'financial-analysis' permission.",
    "retry_after": null
  },
  "sig": "<financial-agent-ed25519-signature>"
}
```

---

## 6. Transport Binding

### HTTPS (required)

```
POST {endpoint} HTTP/1.1
Content-Type: application/acp+json
Accept: application/acp+json
ACP-Version: 1.0

{message-json}
```

TLS 1.3 REQUIRED. TLS 1.2 MAY be supported for legacy compatibility.

### WebSocket (optional)

```
GET /acp HTTP/1.1
Upgrade: websocket
Sec-WebSocket-Protocol: acp-v1
```

Each frame carries exactly one ACP message. Text frames only.

---

## 7. Security Considerations

- Signature freshness: `timestamp` + deduplication window prevent replays.
- Key distribution: security depends on ANS (RFC-ACP-0002). Use DNSSEC.
- Algorithm agility: Ed25519 is mandated in v1.0. Future versions may add algorithms via RFC process.

---

## References

- RFC-ACP-0001: Agent Identifier Specification
- RFC-ACP-0002: Agent Name Service Protocol
- RFC-ACP-0011: Message Type Registry
- RFC-ACP-0020: Intent Object Specification
- RFC-ACP-0030: Delegation Token Specification
