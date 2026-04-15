# Contributing to ACP

---

## Ways to Contribute

| Type | How |
|------|-----|
| Fix a typo or clarify wording | Open a PR directly |
| Report spec ambiguity | Open a GitHub Issue |
| Propose a new feature | Follow the RFC Process below |
| Build an implementation | See `reference/` |
| Add a protocol adapter | See `adapters/` |
| Expand test coverage | See `compliance/` |
| Security vulnerability | Email `security@acp-protocol.org` |

---

## RFC Process

All normative changes go through the RFC process.

### Step 1: Idea
Post to the mailing list with: what problem does this solve, and why can't it be solved above the protocol layer?

### Step 2: Draft
Create `spec/drafts/draft-{handle}-{topic}-00.md` using [TEMPLATE.md](spec/TEMPLATE.md).

Required sections:
- Abstract
- Motivation
- Specification (with MUST/SHOULD/MAY)
- Security Considerations
- Backwards Compatibility
- Reference Implementation (at least a sketch)

Open a PR marked `[DRAFT]`.

### Step 3: Review
TSC evaluates: design constitution compliance, security, scope, implementability.

### Step 4: Last Call
28-day public comment window. Blocking objections must be substantive and technical.

### Step 5: RFC
Assigned an RFC number. Moved to `spec/RFC-ACP-XXXX.md`. Immutable from this point.

### Step 6: Standard
Promoted after two independent implementations pass the interoperability test suite.

---

## Code of Conduct

Contributor Covenant v2.1.

---

## Governance

TSC meets bi-weekly. Notes published in `/governance/meeting-notes/`.

No single organization may hold more than 25% of TSC seats. Any contributor with 3+ merged PRs over 6+ months may be nominated.
