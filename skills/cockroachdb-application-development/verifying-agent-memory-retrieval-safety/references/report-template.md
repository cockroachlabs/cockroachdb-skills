# Retrieval Safety Report

Use synthetic identifiers and redact sensitive values. Do not include raw vectors, secrets, credentials, or production memory text.

## Scope

- Application and retrieval path:
- Reviewer and date:
- Environment:
- SQL or source revision:
- Authoritative caller scope:

## Boundary Matrix

| Boundary | Required rule | Evidence inspected | Result: pass/fail/unverified | Gap or remediation |
|---|---|---|---|---|
| Authenticated scope binding | | | | |
| Tenant/workspace eligibility | | | | |
| Lifecycle and validity | | | | |
| Review/evidence policy | | | | |
| Embedding-space compatibility | | | | |
| Candidate and output bounds | | | | |
| Database role/grants | | | | |
| Row-level security, if relied upon | | | | |
| Relationship/value integrity | | | | |
| Empty-result abstention | | | | |

## Plan Review

- Non-executing command used:
- Relevant scalar indexes:
- Relevant vector index:
- Candidate-set observation:
- Unexpected scan or distribution behavior:
- Performance claims intentionally not established:

## Synthetic Behavioral Tests

| Case | Sanitized fixture IDs | Expected result | Actual result | Status |
|---|---|---|---|---|
| Eligible memory | | | | |
| Cross-scope nearer memory | | | | |
| Ineligible lifecycle/validity | | | | |
| Incompatible embedding space | | | | |
| Bounded result set | | | | |
| No eligible evidence | | | | |
| Untrusted scope change | | | | |

## Decision

- Decision: pass / fail / conditional
- Blocking failures:
- Unverified items and evidence needed:
- Explicit limitations:

