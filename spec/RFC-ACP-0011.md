# RFC-ACP-0011: Message Type Registry

**Status:** Draft
**Version:** 0.1.0
**Created:** 2026-04-15

---

## Abstract

This document is the authoritative registry of ACP message types. For each
type it defines: required fields beyond the envelope, expected behavior of
sender and receiver, and which types may be sent in reply.

---

## 1. Core Types (all implementations MUST support)

### REQUEST

Initiates a task or query.

**Additional required fields:**
```json
{
  "body": {
    "capability": "<capability URI>",
    "inputs": { ... }
  }
}
```

**Behavior:**
- Sender MUST include a valid `intent_ref` or `null`
- Sender MUST include `delegation_token` if acting under delegated authority
- Receiver MUST reply with RESPONSE or ERROR
- Receiver MAY reply with STREAM_START instead of RESPONSE for streaming output

**Valid replies:** RESPONSE, ERROR, STREAM_START, HITL_REQUEST

---

### RESPONSE

Synchronous reply to a REQUEST.

**Additional required fields:**
```json
{
  "in_reply_to": "<id of the REQUEST>",
  "body": {
    "status": "COMPLETED | PARTIAL | FAILED",
    "outputs": { ... },
    "confidence": 0.0
  }
}
```

`confidence` is a float in [0, 1]. Optional. When present, indicates the
agent's self-assessed reliability of its output.

`status` values:
- `COMPLETED` — task finished, outputs are final
- `PARTIAL` — task ran but some outputs are incomplete or low confidence
- `FAILED` — task could not be completed; see `error` field for detail

**Valid replies:** none (terminal message in exchange)

---

### ERROR

Indicates a failure. Sent in place of RESPONSE when processing cannot proceed.

**Additional required fields:**
```json
{
  "in_reply_to": "<id of the triggering message>",
  "body": {
    "code": "ACP-4xx | ACP-5xx",
    "title": "<short string>",
    "detail": "<longer explanation>"
  }
}
```

**Error code registry:**

| Code | Meaning | Retryable |
|------|---------|-----------|
| `ACP-400` | Malformed message or invalid schema | No |
| `ACP-401` | Identity verification failed | No |
| `ACP-403` | Insufficient permission | No |
| `ACP-404` | Capability not found or not supported | No |
| `ACP-408` | Request timed out | Yes |
| `ACP-409` | Conflict (duplicate id, state mismatch) | No |
| `ACP-422` | Valid schema but semantically invalid inputs | No |
| `ACP-429` | Rate limit exceeded | Yes, after `retry_after` |
| `ACP-500` | Internal agent error | Maybe |
| `ACP-503` | Agent temporarily unavailable | Yes, after `retry_after` |

Optional `body` fields: `hint` (string, actionable suggestion), `retry_after`
(ISO-8601 datetime or null).

---

## 2. Streaming Types (OPTIONAL)

Used when output is produced incrementally (e.g., LLM token stream, large
file transfer).

### STREAM_START

Signals that a streaming response is beginning.

```json
{
  "in_reply_to": "<REQUEST id>",
  "body": {
    "stream_id": "<uuid>",
    "content_type": "text/plain | application/json | ...",
    "estimated_chunks": 42
  }
}
```

`estimated_chunks` is advisory; receivers MUST NOT rely on it being accurate.

### STREAM_CHUNK

One fragment of streaming content.

```json
{
  "body": {
    "stream_id": "<uuid>",
    "seq": 1,
    "data": "<base64 or plain string>",
    "encoding": "base64 | utf-8"
  }
}
```

`seq` is a monotonically increasing integer starting at 1. Gaps indicate
lost chunks; receivers SHOULD request retransmission or abort the stream.

### STREAM_END

Signals normal stream completion.

```json
{
  "body": {
    "stream_id": "<uuid>",
    "total_chunks": 42,
    "checksum": "sha256:<hex of full reassembled content>"
  }
}
```

Receivers MUST verify the checksum after reassembly.

---

## 3. Control Types (OPTIONAL)

### INTERRUPT

Requests cancellation of a running task.

```json
{
  "body": {
    "target_task_id": "<task id to cancel>",
    "reason": "user_cancelled | timeout | error | policy_violation"
  }
}
```

The receiving agent MUST acknowledge with RESPONSE `{ "status": "CANCELLED" }`
or ERROR if the task cannot be cancelled (already completed, etc.).

Agents MUST make a best-effort attempt to stop work when INTERRUPT is received.
They are not required to undo already-committed side effects.

### CHECKPOINT

Requests or delivers a serialized execution snapshot for resumption.

**Request checkpoint (sender asks receiver to save state):**
```json
{
  "body": {
    "action": "SAVE",
    "task_id": "<task id>"
  }
}
```

**Checkpoint delivery (receiver sends saved state):**
```json
{
  "body": {
    "action": "DELIVER",
    "task_id": "<task id>",
    "checkpoint_id": "<uuid>",
    "state_uri": "acp://storage/ckpt/<id>",
    "ttl_hours": 72,
    "resume_hint": "<natural language description of current progress>"
  }
}
```

### HANDOFF

Transfers ownership of a task to a different agent.

```json
{
  "body": {
    "task_id": "<task id>",
    "reason": "<why this agent cannot complete it>",
    "suggested_capability": "acp://cap.acp.dev/...",
    "context": { ... }
  }
}
```

The receiving orchestrator (indicated by `to`) is responsible for finding
a new agent to continue the task.

---

## 4. Human-in-the-Loop Types

Defined fully in RFC-ACP-0033. Listed here for completeness.

### HITL_REQUEST

Pauses execution and requests a human decision. Sent by an agent to a
human-facing endpoint.

### HITL_RESPONSE

Carries the human's decision back to the waiting agent.

---

## 5. Type Extension

Organizations MAY define custom message types using reverse-domain notation:

```
X-ACP-Type: com.mycompany.custom-event/1.0
```

Custom types MUST NOT conflict with core type names. Implementations that
receive an unknown type MUST ignore it (do not return ACP-400) and MAY log
a warning.

---

## References

- RFC-ACP-0010: Standard Message Envelope
- RFC-ACP-0013: Session Lifecycle Management
- RFC-ACP-0033: Human-in-the-Loop Protocol
