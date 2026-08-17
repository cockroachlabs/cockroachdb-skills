---
name: designing-tiered-agent-memory
description: Guides implementation of a 3-tier persistent memory pattern for AI agents on CockroachDB -- exact-match caching, vector-indexed fuzzy recall, and TTL-decayed long-term context -- behind a read-only boundary with async write-back, verified against real node failure. Use when designing persistent memory for a production coding or reasoning agent, choosing between exact-match and semantic caching, or when resilience to node failure is a real requirement rather than an assumed property.
compatibility: "CockroachDB Cloud, with feature.vector_index.enabled for the warm tier (see docs/v25.2/vector-indexes)"
---

# Designing Tiered Agent Memory

Guides the implementation of a 3-tier persistent memory pattern for AI agents on CockroachDB: an exact-match cache for repeat queries, a vector-indexed tier for semantically similar-but-differently-worded queries, and a TTL-decayed tier for standing conventions or corrections. All three tiers live in one cluster, so vector data and operational data never drift out of consistency with each other -- and the pattern is only called "production-ready" once a real node failure has been run against it, not assumed.

**Complement to other skills:** for the SELECT-only role that backs the read boundary below, see [hardening-user-privileges](../../cockroachdb-security-and-governance/hardening-user-privileges/SKILL.md). For a local multi-node cluster to run the node-failure verification against, see [setting-up-local-cluster](../../cockroachdb-onboarding-and-migrations/setting-up-local-cluster/SKILL.md).

## When to Use This Skill

- Designing persistent memory for an agent that runs in production, not just a demo
- The memory needs both exact-match caching AND semantic/fuzzy recall over past interactions
- Standing conventions or corrections need to persist but should decay if not reaffirmed
- Resilience to node failure is a real requirement for the memory layer, not a nice-to-have
- Deciding how to keep an agent's live reasoning loop from ever holding write access to its own memory store

**Do not use this skill** for a single-table exact-match cache with no fuzzy-recall or resilience requirement -- a plain keyed table is simpler and sufficient there.

## Prerequisites

- A CockroachDB cluster with `feature.vector_index.enabled` set, for the warm tier's [vector index](https://www.cockroachlabs.com/docs/v25.2/vector-indexes.html)
- An embedding model whose output dimension matches the warm tier's `VECTOR(N)` column exactly -- keep both defined from one shared config value in application code, not duplicated
- For the node-failure verification step: either a CockroachDB Cloud Advanced cluster enrolled for `ccloud cluster disruption` (contact your Cockroach Labs account team; not self-service and not available on Basic/Standard plans), or a local 3+ node cluster you can kill a process on directly

## Pattern

### 1. Hot tier: exact-match cache, dual-key

Key the cache on **both** a hash of the normalized query text and a hash of the context it was answered against:

```sql
CREATE TABLE semantic_cache (
    query_hash   STRING NOT NULL,
    content_hash STRING NOT NULL,
    response     STRING NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (query_hash, content_hash)
);
```

The dual key means a change in underlying context (a file changing, a schema migrating) silently invalidates stale entries -- they simply stop matching -- without a separate invalidation job.

### 2. Warm tier: vector-indexed fuzzy recall

```sql
CREATE TABLE query_memory (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_text STRING NOT NULL,
    response   STRING NOT NULL,
    embedding  VECTOR(N) NOT NULL  -- N must match your embedding model's output
);
CREATE VECTOR INDEX ON query_memory (embedding);
```

Query with `ORDER BY embedding <=> $1 LIMIT k`. Calibrate the acceptance distance empirically against your own embedding model before trusting it -- do not assume a threshold from a different model's documentation. In practice, thresholds tuned for one embedding model can be off by nearly 2x for another; verify with real paraphrase-vs-distinct-query pairs from your own data.

### 3. Cold tier: TTL-decayed standing context

```sql
CREATE TABLE team_conventions (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain           STRING NOT NULL,
    convention       STRING NOT NULL,
    last_affirmed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    INDEX (domain)
) WITH (
    ttl_expiration_expression = $$ (last_affirmed_at + INTERVAL '180 days') $$,
    ttl_job_cron = '@daily'
);
```

Re-affirming a convention (an UPSERT touching `last_affirmed_at`) keeps it alive; anything not reaffirmed decays on its own. See [Row-Level TTL](https://www.cockroachlabs.com/docs/stable/row-level-ttl).

### 4. Enforce the read/write boundary structurally, not by convention

Connect the agent's live reasoning path through a SELECT-only SQL role (or the [CockroachDB Cloud Managed MCP Server](https://www.cockroachlabs.com/docs/v26.2/cockroachdb-mcp-server) in its default read-only mode) -- never a role that can write. In application code, back this with a reader class that structurally has no write method at all, so a coding mistake can't smuggle a write through even before the database-level grant would reject it. Route all writes through a separate path (e.g., an async function/queue) holding the only write-capable credential, and write the hot-tier row and warm-tier embedding together in one transaction so they can never drift apart.

### 5. Verify resilience, don't assert it

Before calling the memory layer production-ready, run a real node-failure test: kill one node (locally, `kill -9` on a `cockroach start` process; on Cloud, `ccloud cluster disruption set` if your org is enrolled -- see Prerequisites) while a continuous read-loop probe runs against the cluster, and record the real pass/fail count and latency during the outage window. An assumed resilience property is not a verified one -- see the [CockroachDB resilience demo](https://www.cockroachlabs.com/docs/stable/demo-cockroachdb-resilience) for a comparable node-kill methodology.

## Safety Considerations

- Never let the agent's live reasoning path hold write access to the memory store -- reads should be immediate and safe, writes should be async and auditable.
- Never claim resilience without having actually run a node-failure test against a multi-node cluster; a single-node dev cluster proves nothing about failover.
- A vector-tier distance threshold copied from another embedding model's documentation is a guess, not a calibration -- verify it against your own model before trusting a "similar enough" match to skip a fresh answer.
- See [Production Checklist](https://www.cockroachlabs.com/docs/cockroachcloud/production-checklist) before treating any of the above as complete for a real deployment.

## References

- [Vector Indexes](https://www.cockroachlabs.com/docs/v25.2/vector-indexes.html)
- [Row-Level TTL](https://www.cockroachlabs.com/docs/stable/row-level-ttl)
- [CockroachDB MCP Server](https://www.cockroachlabs.com/docs/v26.2/cockroachdb-mcp-server)
- [ccloud CLI Command Reference](https://www.cockroachlabs.com/docs/cockroachcloud/ccloud-reference)
- [CockroachDB Resilience Demo](https://www.cockroachlabs.com/docs/stable/demo-cockroachdb-resilience)
- [Production Checklist](https://www.cockroachlabs.com/docs/cockroachcloud/production-checklist)
