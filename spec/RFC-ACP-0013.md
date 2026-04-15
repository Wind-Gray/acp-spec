# RFC-ACP-0013: Session Lifecycle Management

**Status:** Draft
**Version:** 0.1.0
**Created:** 2026-04-15

---

## Abstract

This document defines how ACP sessions are created, maintained, suspended,
resumed, and closed. A session groups a sequence of related messages under
a shared identifier, enabling stateful multi-turn interactions, replay
protection, and mid-session recovery.

---

## 1. What is a Session

A session is a sequence of ACP messages sharing a `session_id`. Sessions are:

- **Optional** — stateless single-message exchanges do not need a session
- **Scoped** — all messages in a session share the same `intent_ref`
- **Resumable** — sessions can be suspended and resumed via checkpoints
- **Bounded** — sessions have a maximum lifetime (TTL)

---

## 2. Session Identifier

```
session_id: UUIDv7 string

Created by: the initiating agent (sender of the first REQUEST)
Scope:      both agents in the exchange must use the same session_id
```

The session initiator generates the `session_id` and includes it in the
first REQUEST. All subsequent messages in the session MUST include the
same `session_id`.

---

## 3. Session States

```
         create
           |
           v
         INIT
           |  first REQUEST sent
           v
      ESTABLISHED
           |
     +-----+------+
     |            |
     v            v
  ACTIVE      SUSPENDED
     |            |
     +-----+------+
           |
           v
      INTERRUPTED    <- HITL pending, RFC-ACP-0033
           |
           v
         CLOSED
```

**INIT** — session_id allocated, first message not yet sent.

**ESTABLISHED** — first REQUEST received and accepted.

**ACTIVE** — messages are flowing.

**SUSPENDED** — no messages for > `idle_timeout` seconds. Session is paused
but not closed. A checkpoint SHOULD be saved on transition to SUSPENDED.

**INTERRUPTED** — a HITL_REQUEST has been sent and is awaiting response.
No other messages may be sent until the HITL is resolved.

**CLOSED** — session ended normally or by timeout. Session state may be
discarded after this point.

---

## 4. Session Headers

These optional fields extend the core message envelope for session-aware
messages.

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | UUIDv7 | Session this message belongs to |
| `turn` | integer | Monotonically increasing turn counter (starts at 1) |
| `session_ttl` | integer | Seconds until session expires if idle |
| `parent_session` | UUIDv7 | For sub-sessions spawned by an orchestrator |

**`turn`** prevents replay attacks within a session. Receivers MUST reject
messages with a `turn` value equal to or less than the highest seen turn.
If `turn` is absent, replay protection relies on `id` deduplication only.

---

## 5. Session Timeout

Default idle timeout: 300 seconds (5 minutes).

A session transitions to SUSPENDED after `session_ttl` seconds of inactivity.
Sessions MUST be closed (state discarded) after 7 days of inactivity,
regardless of `session_ttl`.

Agents SHOULD send a CHECKPOINT message before a session goes idle, to
enable resumption.

---

## 6. Session Resumption

To resume a SUSPENDED session:

1. Retrieve the last checkpoint (RFC-ACP-0011 CHECKPOINT type)
2. Send a new REQUEST with the original `session_id`
3. Include `body.resume_from_checkpoint: "<checkpoint_id>"`
4. Set `turn` to `last_known_turn + 1`

The receiving agent SHOULD restore its state from the checkpoint and
continue from where it left off.

If the session has been CLOSED (checkpoint expired or state discarded),
the receiver MUST return ACP-404 with `detail: "session not found or expired"`.
The invoker must start a new session.

---

## 7. Session Termination

A session is closed by:
- Either party sending RESPONSE with `body.status: "COMPLETED"` or `"FAILED"`
- Either party sending INTERRUPT with `reason: "session_closed"`
- Idle timeout expiry
- Explicit close: RESPONSE with `body.close_session: true`

After a session closes, both agents SHOULD discard session state.
Audit logs (RFC-ACP-0032) MUST be retained per their own retention policy.

---

## 8. Multi-party Sessions

A session is normally bilateral (two agents). Orchestrators running
multi-agent workflows create separate bilateral sessions with each
sub-agent. These sub-sessions share the same `intent_ref` but have
distinct `session_id` values.

To trace a full workflow, use the `parent_session` field: each sub-session
includes the orchestrator's session_id as its `parent_session`.

---

## 9. Security Considerations

**Turn counter gaps:** If a receiver observes a gap in turn numbers (e.g.,
turn 5 arrives after turn 3 with no turn 4), it SHOULD treat this as a
potential replay or message drop and either request retransmission or abort
the session.

**Session fixation:** The session_id is created by the initiator. A
man-in-the-middle cannot reuse a valid session_id because all messages are
signed, and the signature covers the session_id.

**Long-lived sessions:** Sessions that stay open indefinitely accumulate
state and create larger attack surfaces. Implementations SHOULD enforce
the 7-day maximum and alert operators on unusually long sessions.

---

## References

- RFC-ACP-0010: Standard Message Envelope
- RFC-ACP-0011: Message Type Registry
- RFC-ACP-0032: Audit Log Format
- RFC-ACP-0033: Human-in-the-Loop Protocol
