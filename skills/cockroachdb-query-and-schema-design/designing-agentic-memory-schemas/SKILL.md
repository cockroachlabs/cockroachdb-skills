---
name: designing-agentic-memory-schemas
description: Designs a CockroachDB schema for AI agent memory that stays correct under concurrent writes and supports safe, provable deletion — idempotent event ingestion, provenance graphs with cascade semantics, prefix-scoped vector indexes for tenant isolation, Row-Level TTL for episodic decay, and sharded hash chains for a tamper-evident audit trail. Use when designing or reviewing a schema for agent memory, RAG ingestion, or any system where an LLM's output must be stored, retrieved, and provably deleted.
compatibility: CockroachDB >=24.1 for the schema; >=25.2 if using a built-in C-SPANN vector index rather than an external vector store.
metadata:
  author: community
---

# Designing Agentic Memory Schemas

Agent memory has a shape most application schemas don't: many concurrent
writers (agent sessions) producing overlapping claims, a requirement to trust
some writes less than others, and — increasingly, under data-protection
obligations — a requirement to *prove* something was deleted, not just stop
returning it. This skill covers five schema patterns that hold up under that
shape, each with the failure mode it exists to prevent.

## When to Use This Skill

- Designing a new schema for agent memory, conversation history, or RAG
  ingestion on CockroachDB
- Reviewing an existing agent-memory schema for correctness under concurrent
  writers
- An LLM-facing memory system needs to support deletion requests (GDPR,
  CCPA, or an internal retention policy) and the current design can't prove
  a row is actually gone
- Multiple tenants or agents share one cluster and need index-level
  isolation, not just a `WHERE tenant_id = ...` clause

**For the read side of this same schema** — reconstructing what an agent
believed at a past instant, and the `AS OF SYSTEM TIME` patterns that
requires — see
[auditing-agent-memory-with-as-of-system-time](../../cockroachdb-security-and-governance/auditing-agent-memory-with-as-of-system-time/SKILL.md).

## Prerequisites

- A CockroachDB cluster (any deployment tier) with SQL access sufficient to
  create tables, indexes, and row-level TTL policies
- A settled decision on tenancy: single-tenant, or multi-tenant sharing one
  cluster — this changes the vector-index design in Step 3

---

## Step 1: Idempotent Event Ingestion

Agent frameworks retry. A tool call that times out client-side but succeeded
server-side, a queue redelivery, a client bug that double-submits — any of
these turns "write this episode" into "write this episode, maybe twice."
Treat every ingested event as **at-least-once delivered** and make the table
absorb a duplicate for free rather than trying to prevent duplicates
upstream.

```sql
CREATE TABLE episodes (
  event_id      UUID NOT NULL DEFAULT gen_random_uuid(),
  idempotency_key STRING NOT NULL,  -- caller-supplied: session_id + a
                                     -- monotonic sequence, or a content hash
  subject_key   STRING NOT NULL,
  content       STRING NOT NULL,
  occurred_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (subject_key, idempotency_key)
);
```

Keying the primary key on the caller-supplied idempotency value (not
`event_id`) means a redelivered write is a normal `INSERT ... ON CONFLICT DO
NOTHING`, not an application-level dedup query. The `event_id` still exists
as a stable handle for anything that needs to reference "this exact row"
(provenance edges, audit rows) without embedding the idempotency key
everywhere.

## Step 2: Provenance Graphs With Cascade Semantics

A fact an agent recalls should be traceable to the raw events it came from.
Model this as an explicit edge table, not a denormalized "source_ids" array
column — an array can't be joined efficiently, can't carry per-edge
metadata (which session, which trust category), and can't be walked
recursively when you need to answer "everything downstream of this one
event."

```sql
CREATE TABLE provenance_edges (
  fact_id     UUID NOT NULL REFERENCES facts(fact_id),
  event_id    UUID NOT NULL REFERENCES episodes(event_id),
  session_id  UUID NOT NULL,
  PRIMARY KEY (fact_id, event_id)
);
```

**Cascade semantics matter more than they look like they do.** When an event
turns out to be compromised (a poisoned source, a bad extraction), you need
to compute *everything that depended on it* — not just the direct facts, but
facts derived from those facts, skills learned from those facts, and past
decisions that cited them. That's a recursive query over this edge table:

```sql
WITH RECURSIVE tainted AS (
  SELECT fact_id FROM provenance_edges WHERE event_id = $1
  UNION
  SELECT pe.fact_id
  FROM provenance_edges pe
  JOIN tainted t ON pe.event_id IN (
    SELECT event_id FROM fact_derived_events WHERE fact_id = t.fact_id
  )
)
SELECT fact_id FROM tainted;
```

Design the edge table so this query is answerable in one transaction — if
"what does this event's compromise touch" requires joining across services,
you cannot revoke atomically, and a partial revocation is worse than none
(some downstream damage looks contained when it isn't).

## Step 3: Prefix-Scoped Vector Indexes for Tenant Isolation

A vector index shared across tenants and filtered by a `WHERE tenant_id =
...` predicate is isolation in the query, not isolation in the index — nothing
stops an index-scan implementation detail, a query-planner regression, or a
future refactor from returning a neighbor across tenants. Prefix the index
key with the tenant identifier instead, so isolation is a property of the
index's own key ordering:

```sql
CREATE TABLE facts (
  tenant_id   UUID NOT NULL,
  fact_id     UUID NOT NULL DEFAULT gen_random_uuid(),
  embedding   VECTOR(1536),
  PRIMARY KEY (tenant_id, fact_id),
  VECTOR INDEX (tenant_id ASC, embedding)
);
```

With a `tenant_id`-prefixed vector index, a nearest-neighbor search is
naturally scoped to a single tenant's key range — a cross-tenant match isn't
just filtered out, it's outside the range the index ever traverses for that
query. This matters most for the deletion guarantee in Step 5: a vector
lives and dies with the row it belongs to, in the same key range, in the
same transaction.

## Step 4: Row-Level TTL for Episodic Decay

Raw episodes (as opposed to the durable facts distilled from them) usually
shouldn't live forever — retention policy, cost, and "an agent's memory of
exactly what was said three years ago" being lower-value than the
consolidated fact it produced. Row-Level TTL expires rows automatically
without an application-level cron job that can fall behind or fail silently:

```sql
ALTER TABLE episodes SET (ttl_expire_after = '90 days');
```

**The trap:** TTL deletion is a background job, not instantaneous, and it
does not itself write an audit trail. If episodes feed a provenance graph
(Step 2), decide explicitly whether a TTL-expired episode leaves a
tombstone provenance edge or whether the fact it produced becomes
unexplainable once the source expires — both are defensible, but only one
is what your compliance obligations actually require, and picking neither
by default is the common mistake.

## Step 5: Sharded Hash Chains for a Tamper-Evident Audit Trail

If deletion needs to be *provable*, an audit trail needs to be tamper-evident
against more than accidental corruption — a hash chain, where each row
commits to the hash of the previous row, catches an attacker who edits a
row after the fact even with `UPDATE` privileges, because the edit breaks
every subsequent hash in the chain.

```sql
CREATE TABLE audit_log (
  shard_id    INT4 NOT NULL,
  seq         INT8 NOT NULL,
  event_id    UUID NOT NULL,
  op          STRING NOT NULL,
  entry_hash  BYTES NOT NULL,
  prev_hash   BYTES NOT NULL,
  PRIMARY KEY (shard_id, seq)
);
```

A single unsharded chain serializes every write on one hot row (the current
chain head) — sharding by a hash of the subject (or tenant) trades a small
amount of verification complexity (recompute N chains instead of one) for
write throughput that scales with shard count instead of flatlining. The row
this audit entry describes and the audit entry itself belong in the **same
transaction** — CockroachDB's serializable isolation is what makes "the
mutation and its own audit trail are atomic" true without extra
coordination; a queue or a separate audit service reintroduces exactly the
gap this pattern is meant to close. A `BEFORE INSERT/UPDATE/DELETE` trigger
that refuses the mutation unless a matching audit row exists in the same
transaction makes this a database-enforced guarantee rather than an
application convention that a future code path can forget to honor.

**A hash chain proves a row wasn't silently altered after the fact — it does
not by itself prove data is unrecoverable.** For an actual deletion
guarantee, the chain needs to be periodically checkpointed (a Merkle root
over a batch of entries) and that checkpoint anchored somewhere outside the
database entirely — object storage with a write-once retention lock is a
common choice, since it means even an attacker with full database access
cannot rewrite history undetected: the live chain and the externally
anchored root would disagree, and that disagreement is what an independent
verifier checks.

---

## Safety Considerations

- **Idempotency keys must be caller-controlled and stable across retries.**
  A `gen_random_uuid()` idempotency key generated fresh on every retry
  defeats Step 1 entirely — it must be something the caller already knows
  before the first attempt (a session sequence number, a content hash).
- **Cascade queries (Step 2) can be expensive at depth.** Bound recursion
  depth or add a query timeout before running a full blast-radius
  computation against production traffic; test it against a realistic
  provenance graph size first, not a handful of seed rows.
- **Row-Level TTL (Step 4) is irreversible once a row expires.** If any
  retention or legal-hold obligation can require keeping a specific row past
  its default TTL, that exception path needs to exist *before* enabling
  TTL, not be retrofitted after the first premature deletion.
- **A hash chain alone (Step 5) does not survive an attacker with full
  database privileges** who rewrites a chain and its own checkpoint
  consistently — only an externally anchored checkpoint catches that class
  of attack. Don't present chain verification alone as proof against a
  database-privileged adversary.

## References

- [CockroachDB Docs: Row-Level TTL](https://www.cockroachlabs.com/docs/stable/row-level-ttl)
- [CockroachDB Docs: Vector Indexes](https://www.cockroachlabs.com/docs/stable/vector-indexes)
- [CockroachDB Docs: Multi-Region Overview](https://www.cockroachlabs.com/docs/stable/multiregion-overview)
- [CockroachDB Docs: Transactions](https://www.cockroachlabs.com/docs/stable/transactions)
- [CockroachDB Docs: Triggers](https://www.cockroachlabs.com/docs/stable/triggers)
- [Recursive Common Table Expressions](https://www.cockroachlabs.com/docs/stable/common-table-expressions#recursive-common-table-expressions)

See [references/example-migration.sql](references/example-migration.sql) for
a runnable migration combining all five patterns into one schema.
