---
name: designing-agent-memory-schemas
description: Guides developers in designing CockroachDB schemas for agent memory — episodic/semantic memory tables with VECTOR columns, prefix-filtered vector indexes for per-agent semantic retrieval, reconciliation lineage that preserves memory history instead of overwriting it, set-based forgetting-curve decay, crash-safe task checkpoints, and audit trails. Use when building agent memory layers, RAG stores with per-tenant isolation, or any workload that combines vector search with relational state on CockroachDB.
compatibility: "CockroachDB >= 25.2 (VECTOR type and vector indexes). Requires the feature.vector_index.enabled cluster setting. Works on CockroachDB Cloud Basic clusters."
metadata:
  author: Vector897
  version: "1.0"
---

# Designing Agent Memory Schemas

Guides you through designing a production-grade memory store for AI agents on
CockroachDB: what to persist, how to index it for semantic retrieval, and how
to keep memory auditable and crash-safe. The patterns treat agent memory as
production state — survivable, consistent, and queryable — rather than as an
in-process cache.

## When to Use This Skill

- Building a persistent memory layer for an agent (episodic logs, long-term
  facts, user preferences)
- Designing a RAG or semantic-search store that needs per-tenant/per-agent
  isolation inside one table
- Deciding how to combine `VECTOR` similarity search with relational filters
  (owner, kind, liveness) in one query plan
- Preserving the history of facts that change over time instead of overwriting
  them (temporal reconciliation)
- Making long-running agent tasks resumable after a crash without re-spending
  LLM tokens
- Implementing a forgetting curve (usage-based retention) over a large memory
  table

## Prerequisites

- A CockroachDB cluster (self-hosted >= 25.2, or CockroachDB Cloud) and a SQL
  user with `CREATE` privileges on the target database
- The vector-index feature enabled:

```sql
SET CLUSTER SETTING feature.vector_index.enabled = true;
```

- An embedding model of known dimensionality (the `VECTOR(n)` column is fixed
  at creation; e.g. 1024 for Amazon Titan Text Embeddings V2, 1536 for many
  OpenAI models)

## Steps

### 1. Model memory kinds in one table, discriminated by `kind`

Episodic memories (things that happened) and semantic memories (distilled
facts) share a lifecycle and are retrieved together, so one table with a
`kind` column beats two tables:

```sql
CREATE TABLE memories (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id    STRING NOT NULL,          -- one memory space per agent/tenant
    kind        STRING NOT NULL CHECK (kind IN ('episodic', 'semantic')),
    content     STRING NOT NULL,
    tags        STRING NOT NULL DEFAULT '',
    embedding   VECTOR(1024),
    heat        FLOAT8 NOT NULL DEFAULT 1.0,   -- usage-based retention signal
    confidence  FLOAT8 NOT NULL DEFAULT 0.5,
    archived    BOOL NOT NULL DEFAULT false,   -- out of retrieval, never deleted
    supersedes  UUID REFERENCES memories (id), -- reconciliation lineage
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 2. Create a prefix-filtered vector index

Put the tenant discriminator **before** the vector column. The prefix column
makes the equality filter part of the index scan itself, so per-agent
similarity search never scans another agent's vectors:

```sql
CREATE VECTOR INDEX memories_embedding_idx
    ON memories (owner_id, embedding vector_cosine_ops);
```

Use `vector_cosine_ops` for normalized text embeddings. Add a conventional
secondary index for non-vector access paths:

```sql
CREATE INDEX memories_owner_kind_idx
    ON memories (owner_id, kind, archived, created_at DESC);
```

### 3. Retrieve with a two-stage query

Filter first (prefix columns), rank second (ANN). Keep both the filter and the
`ORDER BY` in one statement so the optimizer uses the vector index:

```sql
SELECT id, kind, content, embedding <=> $1 AS dist
FROM memories
WHERE owner_id = $2 AND archived = false AND kind = ANY($3)
ORDER BY embedding <=> $1
LIMIT 8;
```

Verify the plan uses the vector index with `EXPLAIN` before shipping; a
missing prefix match silently degrades to a full scan.

### 4. Reconcile conflicting facts with lineage, not overwrites

When a new fact contradicts a stored one, do not `UPDATE` the old row's
content. Insert a reconciled row that points at the superseded one, then
archive the old row. History stays queryable — essential for auditing why an
agent believes what it believes:

```sql
-- new reconciled layer
INSERT INTO memories (owner_id, kind, content, embedding, supersedes)
VALUES ($1, 'semantic', $2, $3, $4)  -- $4 = old memory id
RETURNING id;

-- the old layer leaves retrieval but keeps existing
UPDATE memories SET archived = true, updated_at = now() WHERE id = $4;
```

Walk the `supersedes` chain to reconstruct the full belief history of any
memory.

### 5. Apply the forgetting curve set-based

Retention pressure should be one `UPDATE`, not a row-by-row loop:

```sql
UPDATE memories SET heat = heat * 0.95 WHERE archived = false;

UPDATE memories SET archived = true, updated_at = now()
WHERE archived = false AND kind = 'episodic' AND heat < 0.05;
```

Bump `heat` on retrieval hits (`UPDATE ... SET heat = heat + 1 WHERE id =
ANY(...)`) so frequently used memories resist decay.

### 6. Add crash-safe checkpoints and an audit trail

Two small companion tables make agent work resumable and reviewable:

```sql
CREATE TABLE checkpoints (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id    STRING NOT NULL,
    task_id     STRING NOT NULL,
    step        STRING NOT NULL,
    state       JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (owner_id, task_id, step)
);

CREATE TABLE audit_log (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id    STRING NOT NULL,
    action      STRING NOT NULL,
    detail      JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Checkpoint upserts target the unique constraint (`INSERT ... ON CONFLICT
(owner_id, task_id, step) DO UPDATE`), not the primary key.

### 7. Optionally bound episodic growth with row-level TTL

If archived episodic rows should eventually leave storage entirely, prefer
CockroachDB's row-level TTL over cron deletes:

```sql
ALTER TABLE memories SET (
    ttl_expiration_expression = $$
        IF(archived AND kind = 'episodic',
           updated_at + INTERVAL '90 days',
           NULL)
    $$
);
```

Keep semantic memories and reconciliation lineage exempt (the expression
returns `NULL` for them) so belief history is never silently destroyed.

## Safety Considerations

- **Batch inserts degrade vector-indexed tables** — insert memory rows
  individually or in small batches; avoid bulk `IMPORT INTO` (unsupported on
  vector-indexed tables).
- **Adding a vector index to a populated table blocks writes during backfill**
  — create indexes before loading data, or schedule the backfill off-peak.
- **Never store credentials or secrets in memory content** — memories are
  returned verbatim into future LLM contexts.
- **Dimensionality is fixed** — changing embedding models with a different
  dimension requires a new column and re-embedding; plan for it.
- **TTL deletes are permanent** — scope `ttl_expiration_expression` carefully
  so reconciliation lineage (`supersedes` targets) is not garbage-collected
  out from under live rows.

## References

- [Vector Indexes](https://www.cockroachlabs.com/docs/stable/vector-indexes) —
  syntax, operator classes, prefix columns, limitations
- [`VECTOR` type](https://www.cockroachlabs.com/docs/stable/vector) — storage
  and distance operators
- [Row-Level TTL](https://www.cockroachlabs.com/docs/stable/row-level-ttl)
- [CockroachDB and AI](https://www.cockroachlabs.com/docs/stable/cockroachdb-and-ai)
