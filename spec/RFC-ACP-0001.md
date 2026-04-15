# RFC-ACP-0001: Agent Identifier Specification

**Status:** Draft
**Version:** 0.1.0
**Created:** 2026-04-15

---

## Abstract

This document defines the Agent Identifier (AID) — the stable, globally
unique, human-readable string that unambiguously identifies a single AI agent
in the ACP ecosystem.

---

## 1. Motivation

For two agents to communicate they must unambiguously refer to each other.
Existing approaches fail:

- **API keys** are credentials, not identities. Cannot be publicly shared.
- **URLs** encode location, which changes when infrastructure migrates.
- **Model names** don't identify instances, carry no crypto proof, and can't
  represent user-owned agents.

ACP needs an identifier that is stable, globally unique, verifiable,
human-readable, and decentralized.

---

## 2. AID Syntax

```
AID        = "acp://" authority "/" agent-path
authority  = dns-name | did-authority | "localhost"
agent-path = 1*path-segment
```

### 2.1 Authority Types

**DNS (RECOMMENDED)**
```
acp://example.com/my-agent
acp://api.company.com/billing-assistant
acp://alice.personal.com/scheduler
```

**DID (decentralized, DNS-independent)**
```
acp://did:key:z6MkhaXgBZDvot.../assistant
acp://did:web:example.com/agent
```

**localhost (development only)**
```
acp://localhost/dev-agent
```

### 2.2 Prohibited Forms (MUST reject)

```
acp://192.168.1.1/agent     <- IP addresses forbidden
acp:///no-authority         <- Empty authority forbidden
acp://example.com           <- Missing path forbidden
```

### 2.3 Normalization

Before comparison, AIDs MUST be normalized:
1. Scheme and authority: lowercase
2. Path: case-sensitive, preserve as-is
3. Strip trailing slash

```
Unnormalized:  ACP://EXAMPLE.COM/MyAgent/
Normalized:    acp://example.com/MyAgent
```

---

## 3. AID Resolution

An AID resolves to an Agent Manifest — a signed JSON document containing
the agent's endpoint and public key. Resolution is defined in RFC-ACP-0002.

---

## 4. Lifecycle

### 4.1 Creation
1. Operator controls the authority (owns DNS domain or DID)
2. Generate Ed25519 key pair
3. Publish Agent Manifest at the resolvable endpoint
4. Configure DNS TXT record (for DNS authorities)

### 4.2 Key Rotation
Agents MAY rotate signing keys without changing their AID.
New public key MUST be published before the old key is retired.

### 4.3 Revocation
- Remove the DNS TXT record, OR
- Publish an Agent Manifest with `"status": "revoked"` signed with current key

After revocation: implementations MUST NOT initiate new sessions.

---

## 5. Security Considerations

**Domain hijacking:** AID security is tied to DNS security.
Operators SHOULD enable DNSSEC and monitor for unauthorized DNS changes.

**Key compromise:** Immediately revoke manifest, generate new key pair,
notify known counterparties out-of-band.

**Spoofing:** Signature verification against the Agent Manifest public key
is REQUIRED for all received messages. Skipping verification enables spoofing.

---

## References

- RFC 3986: Uniform Resource Identifier (URI): Generic Syntax
- W3C DID: Decentralized Identifiers v1.0
- RFC-ACP-0002: Agent Name Service Protocol
