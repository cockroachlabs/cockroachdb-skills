---
name: verifying-agent-memory-retrieval-safety
description: Verifies that agent-memory retrieval on CockroachDB preserves application trust boundaries before vector ranking, uses compatible embedding spaces, bounds candidate sets, and fails safely when evidence is ineligible or insufficient. Use when reviewing semantic-memory SQL, diagnosing cross-tenant or stale-memory retrieval risk, preparing an agent-memory launch review, or producing a redacted retrieval-safety report.
metadata:
  author: cockroachdb
  version: "1.0"
---

# Verifying Agent Memory Retrieval Safety

Review a CockroachDB-backed agent-memory retrieval path before treating its results as trustworthy. Separate application eligibility, database authorization, relational integrity, and vector ranking: each solves a different problem.

## When to Use This Skill

- Reviewing SQL that ranks memories by vector distance
- Checking tenant, workspace, service, state, or validity boundaries
- Migrating embeddings or supporting multiple embedding models
- Investigating cross-boundary, stale, or unsupported agent answers
- Preparing a launch, security, or architecture review for agent memory

## Safety Rules

- Use `EXPLAIN`, never `EXPLAIN ANALYZE`, on untrusted or production retrieval SQL. `EXPLAIN ANALYZE` executes the statement.
- Do not select, log, or paste raw embedding vectors, secrets, credentials, or sensitive memory text into the report.
- Treat query predicates as application retrieval policy, not as a replacement for grants or row-level authorization.
- Treat foreign keys and constraints as integrity controls, not authorization controls.
- Do not write fixtures to production. Use sanitized fixtures in an isolated test database when behavioral tests are needed.
- Do not claim that a plan is production-ready from `EXPLAIN` alone. Scale and latency require representative, approved testing.

## Inputs

Gather the following, redacting values where necessary:

1. The retrieval SQL and parameter meanings.
2. Relevant table, index, constraint, and policy definitions.
3. The application's trust boundaries: tenant, workspace, service, user, or another scope.
4. Memory eligibility rules: lifecycle state, validity interval, review state, evidence quality, and embedding space.
5. The maximum candidate and result counts.
6. If available, a non-executing `EXPLAIN` plan and sanitized boundary-test results.

If a required input is missing, record it as **unverified** rather than inferring safety.

## Procedure

### 1. Map the trust boundary

Identify the caller-controlled scope and the authoritative scope supplied by authentication or server-side context. Flag retrieval SQL that accepts a tenant or workspace identifier from an untrusted request without independently binding it to the caller.

Document controls separately:

| Control | Question it answers |
|---|---|
| Query eligibility predicates | Which memories may this retrieval consider? |
| Grants and database roles | Which database objects may this identity access? |
| Row-level security, when used | Which rows may this database identity access? |
| Foreign keys and constraints | Which stored relationships and values are valid? |

Passing one row does not compensate for a missing control in another row.

### 2. Build the eligibility-before-ranking matrix

Inspect the SQL and record every applicable boundary using [the report template](references/report-template.md). Common boundaries include:

- tenant, workspace, account, or service scope
- memory lifecycle state, such as active versus revoked
- `valid_from` and `valid_until`
- review, confidence, outcome, or evidence requirements
- embedding-space identifier and vector dimension
- source visibility or sensitivity classification
- hard candidate and final-result limits

The safe logical order is:

1. establish the authorized scope;
2. exclude ineligible rows;
3. rank the remaining candidates by vector distance;
4. apply a bounded result limit;
5. abstain if no eligible evidence clears the application's threshold.

A SQL optimizer may reorder physical execution while preserving semantics. Judge the query's semantics and plan together; do not require textual predicate order.

### 3. Verify embedding compatibility

Confirm that the query vector and stored vectors belong to the same declared embedding space and have compatible dimensions. A dimension check alone is insufficient because different models can emit equal-length but semantically incompatible vectors.

Prefer an explicit, immutable embedding-space identifier associated with each memory and query. During migration, retrieve only from spaces the application intentionally supports, or run separate rankings whose scores are not compared as if they were calibrated identically.

### 4. Inspect indexes and a non-executing plan

Inventory relevant indexes without selecting vector values. Then run or request:

```sql
EXPLAIN (OPT, VERBOSE)
SELECT memory_id
FROM memories
WHERE tenant_id = $1
  AND embedding_space_id = $2
  AND state = 'active'
  AND valid_from <= now()
  AND (valid_until IS NULL OR valid_until > now())
ORDER BY embedding <=> $3
LIMIT $4;
```

Adapt names and operators to the application. Check whether the plan and indexes support the intended scalar filters and vector ordering, whether the candidate set is bounded, and whether an unexpected full scan deserves investigation. Plan shape alone does not prove authorization or result quality.

For CockroachDB vector-index syntax and tuning, follow the current official documentation rather than inventing index options.

### 5. Test boundary behavior safely

In an isolated environment with synthetic text and vectors, cover at least:

- an eligible memory is returned;
- a nearer memory from another tenant or workspace is excluded;
- revoked, expired, future-valid, or unreviewed memories are excluded as policy requires;
- an incompatible embedding space is excluded;
- the candidate and output limits are enforced;
- no eligible memory produces an explicit empty result or abstention;
- changing a caller-supplied scope cannot cross the authenticated boundary.

Record the fixture identifiers and assertions, not raw production content or vectors.

### 6. Report the decision

Classify every boundary as **pass**, **fail**, or **unverified**. A launch decision passes only when all required boundaries pass. Any failed boundary blocks approval; any unverified boundary makes the result conditional and names the evidence needed to resolve it.

Include limitations explicitly: a static review does not establish production latency, recall quality, resistance to prompt injection, or database authorization unless those were separately tested.

## Official References

- [Vector indexes](https://www.cockroachlabs.com/docs/stable/vector-indexes)
- [Vector data types](https://www.cockroachlabs.com/docs/stable/vector)
- [EXPLAIN](https://www.cockroachlabs.com/docs/stable/explain)
- [EXPLAIN ANALYZE](https://www.cockroachlabs.com/docs/stable/explain-analyze)
- [Authorization overview](https://www.cockroachlabs.com/docs/stable/authorization)
- [Row-level security](https://www.cockroachlabs.com/docs/stable/row-level-security)
