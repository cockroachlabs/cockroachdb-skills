---
name: auditing-agent-memory-with-as-of-system-time
description: Reconstructs exactly what an AI agent's memory contained at a past instant using AS OF SYSTEM TIME, for audit, deposition, and compliance review. Covers the difference between a historical read and a stale one, garbage-collection window limits, extending retention for rows under legal hold, and the failure mode where an audit query silently reads current state instead of historical state. Use when building a review or compliance feature that must answer "what did this system believe when it acted," not just "what does it believe now."
compatibility: CockroachDB (all versions supporting AS OF SYSTEM TIME); historical read range is bounded by gc.ttlseconds, configurable per table/database via zone configuration.
metadata:
  author: community
---

# Auditing Agent Memory With AS OF SYSTEM TIME

"What does the agent currently know" and "what did the agent believe when it
made this decision three weeks ago" are different questions, and an audit or
compliance feature that only answers the first one is not actually an audit
feature — it's a dashboard. `AS OF SYSTEM TIME` is CockroachDB's mechanism
for answering the second question precisely, and it has real limits that
matter more here than in almost any other use case, because the whole point
is trusting the answer.

## When to Use This Skill

- Building a "reconstruct past state" or "explain this decision" feature for
  an AI agent, where a reviewer needs to see exactly what memory the agent
  had access to at the moment it acted
- Implementing an audit trail that must survive a "how do you know that's
  what it believed then, and not now" challenge
- Designing retention policy for rows that must remain historically
  queryable for a compliance-mandated period, even after your default
  garbage-collection window would otherwise reclaim them
- Reviewing an existing audit feature that reads "current" data and labels
  it historical — this is the single most common bug this pattern produces

**For the schema this pattern queries against** — provenance edges, audit
tables, and the tenant isolation that makes cross-tenant historical reads
impossible by construction — see
[designing-agentic-memory-schemas](../../cockroachdb-query-and-schema-design/designing-agentic-memory-schemas/SKILL.md).

## Prerequisites

- A schema where the tables being audited are actually mutated in place
  (updated/deleted), not append-only — `AS OF SYSTEM TIME` is most valuable
  precisely where state changes, since an append-only log doesn't need a
  historical read to see the past
- `gc.ttlseconds` known for the tables involved (default is commonly 25
  hours on recent CockroachDB versions; confirm the actual configured value
  for your cluster rather than assuming a default)

---

## Step 1: The Historical Read

```sql
SELECT fact_text, confidence, trust_state
FROM facts
AS OF SYSTEM TIME '2026-06-01 14:32:00+00'
WHERE tenant_id = $1 AND subject_key = $2;
```

This returns the table exactly as it existed at that timestamp — rows that
were later updated show their pre-update values; rows deleted after that
timestamp still appear; rows inserted after that timestamp do not. That last
property is what makes this useful for reconstructing "what could the agent
have known" rather than "what do we know now and assume it knew."

A relative form is often more useful for "N minutes/hours ago" queries:

```sql
SELECT ... FROM facts AS OF SYSTEM TIME '-10m' WHERE ...;
```

## Step 2: The Trap — Silently Reading `now()`

The failure mode worth naming explicitly: a query that is *supposed* to be
historical but isn't, because the `AS OF SYSTEM TIME` clause was dropped
somewhere between the audit tool's UI and the actual query — a refactor that
moved the clause into a query builder and lost it, a code path that
special-cases "no timestamp given" as "just read current state" instead of
erroring. **This fails silently.** The query still returns rows; they're just
the wrong rows, and nothing about the result shape tells you that.

Two defenses:

1. **Make the timestamp a required parameter with no default**, at the
   layer that constructs the query — not an optional one that falls back to
   "current" when absent. A missing timestamp should be a caller error, not
   an implicit `now()`.
2. **Return the resolved timestamp alongside the results**, so a caller (or
   a test) can assert the query actually ran against the timestamp
   requested:

```sql
SELECT cluster_logical_timestamp();  -- run in the same AS OF SYSTEM TIME
                                      -- transaction to confirm what was used
```

## Step 3: The Garbage-Collection Window

A historical read only works within `gc.ttlseconds` of the present — older
MVCC versions are eligible for garbage collection and, once collected,
genuinely gone; the query does not silently fall back to something else, it
errors:

```
pq: batch timestamp ... must be after replica GC threshold ...
```

**Treat this error as informative, not a bug to route around.** It means
the specific historical state being asked for no longer exists anywhere in
the cluster. For an audit feature, the correct response is to say so
plainly — "this decision predates the retention window and cannot be
reconstructed" — not to catch the error and quietly show current state
instead (which reintroduces Step 2's trap through the back door).

## Step 4: Extending the Window for Retention Obligations

If a compliance or legal-hold requirement means specific rows must remain
historically queryable longer than your default GC window, extend
`gc.ttlseconds` via zone configuration — scoped as narrowly as the
obligation actually requires, not cluster-wide:

```sql
ALTER TABLE facts CONFIGURE ZONE USING gc.ttlseconds = 7776000; -- 90 days
```

For a true "this specific subject is under legal hold, extend retention for
exactly this row's history" requirement, that scoping typically needs to
happen at the row/range level (a partition or a `REGIONAL BY ROW`-style
homing that a hold can target), not just the table — table-wide extension
is a blunt instrument that keeps *everything's* history around longer,
which has its own storage and exposure cost. Model "what is under hold"
explicitly (a boolean or a reference to a hold record) so the extension
logic can be driven by real data rather than a manually maintained
allowlist that goes stale.

## Step 5: Historical Reads and Erasure Requests Are in Tension — By Design

If a subject's data was deleted (a GDPR/CCPA erasure request, an internal
retention expiry) and later someone needs to audit a decision made *before*
that deletion, a historical read at a timestamp preceding the erasure will
correctly show the since-deleted content — this is not a bug, it's the
entire point of the audit feature, and getting it "wrong" in the direction
of hiding history would defeat the audit's purpose. But it means an
audit/deposition query path is now a way to view erased content, which
must be access-controlled as carefully as the original data was — an
audit feature with weaker access control than the data it audits is a
bigger hole than the deletion was trying to close.

---

## Safety Considerations

- **Never let "no timestamp provided" silently mean "now."** See Step 2 —
  this is the single most consequential mistake this pattern enables.
- **Handle the GC-threshold error explicitly and say so to the caller.**
  Swallowing it and falling back to a current-state read is worse than
  surfacing the error, because it looks like a successful historical
  answer.
- **`ALTER ... CONFIGURE ZONE` retention extensions have a storage cost.**
  Longer `gc.ttlseconds` means more retained MVCC history cluster-wide for
  that zone; scope it to what the obligation actually requires.
- **A historical read of erased content is privileged access, not a
  loophole.** Apply the same (or stricter) authorization to the audit path
  as to the live data it's reconstructing — see Step 5.

## References

- [CockroachDB Docs: AS OF SYSTEM TIME](https://www.cockroachlabs.com/docs/stable/as-of-system-time)
- [CockroachDB Docs: Garbage Collection](https://www.cockroachlabs.com/docs/stable/architecture/storage-layer#garbage-collection)
- [CockroachDB Docs: Configure Replication Zones](https://www.cockroachlabs.com/docs/stable/configure-replication-zones)
- [CockroachDB Docs: Follower Reads](https://www.cockroachlabs.com/docs/stable/follower-reads)

See [references/example-audit-query.sql](references/example-audit-query.sql)
for a full "reconstruct the decision" query pattern joining a historical
fact read against an audit log entry.
