---
name: isolating-untrusted-agent-memory
description: Guides developers building agents with long-term memory in treating ingested content (logs, tickets, alerts, tool output, web text) as untrusted evidence rather than instructions, using a trust tier stored as a prefix column of a CockroachDB vector index so that quarantined memory is unreachable from semantic retrieval - not merely filtered out of the result set - plus an integrity gate on the write path and an allowlist on the read path. Use when an agent stores retrieved or ingested content into a vector store, when defending against memory poisoning or indirect prompt injection through persistent memory, when a planner must only see corroborated context, or when designing provenance and access control for agent memory.
compatibility: "CockroachDB >= 25.2 (distributed vector indexing). Requires the cluster setting feature.vector_index.enabled and privileges to create tables, vector indexes, and SQL roles on the target database."
metadata:
  author: cairn
  version: "1.0"
---

# Isolating Untrusted Agent Memory

An agent that ingests logs, tickets, alerts, or tool output into long-term memory has handed every
party who can write to those sources a write path into its own future context. Indirect prompt
injection stops being a per-request problem and becomes a persistent one: poison the memory once,
and it influences every future retrieval.

This skill encodes a defense built into the store rather than bolted above it. Each memory row
carries a **trust tier**, and that tier is a **prefix column of the vector index**. Retrieval names
the tiers it will accept as an allowlist, and CockroachDB scopes the approximate-nearest-neighbour
traversal to exactly those tiers - quarantined content is never visited, not visited-then-discarded.
A single-node store with a bolt-on `WHERE` clause still walks the poisoned rows; here they are
structurally out of reach.

## When to Use This Skill

- An agent writes ingested or retrieved content into a vector store and later recalls it
- You are defending against memory poisoning / indirect prompt injection via persistent memory
- A planner or reasoning step must only ever see corroborated, trusted context
- You need provenance (source, trust tier, content hash) and access control on agent memory
- You want retrieval-time isolation enforced by the index, not by application filtering

## Prerequisites

- CockroachDB 25.2+ with `SET CLUSTER SETTING feature.vector_index.enabled = true`
- An embedding provider; a `VECTOR(n)` column sized to it (e.g. 1024)
- Understanding that a cluster setting cannot be issued inside a transaction

## Steps

### 1. Model memory with a trust tier and provenance

```sql
CREATE TABLE memory (
    tenant_id    UUID        NOT NULL,
    mem_id       UUID        NOT NULL DEFAULT gen_random_uuid(),
    trust_tier   INT2        NOT NULL,   -- 0 quarantined · 1 raw evidence · 2 corroborated · 3 operator
    content      STRING      NOT NULL,
    content_hash STRING      NOT NULL,
    source_uri   STRING      NOT NULL,
    source_class STRING      NOT NULL,   -- attacker_writable | system | operator
    gate_verdict JSONB       NOT NULL,
    embedding    VECTOR(1024),
    PRIMARY KEY (tenant_id, mem_id)
);
```

### 2. Make the trust tier a prefix column of the vector index

```sql
CREATE VECTOR INDEX mem_vec
    ON memory (tenant_id, trust_tier, embedding vector_cosine_ops);
```

Ordering matters: `trust_tier` sits between the tenant and the embedding so it prefixes the ANN
traversal. This is what turns a data label into an access boundary.

### 3. Retrieve with an allowlist of tiers - never a floor

```sql
SELECT mem_id, content, trust_tier
  FROM memory
 WHERE tenant_id = $t
   AND trust_tier IN (2, 3)                       -- allowlist, not >= 2
 ORDER BY embedding <=> $query_embedding
 LIMIT $k;
```

CockroachDB accelerates a vector index only when **every prefix column is constrained by equality
or an `IN` list**. `trust_tier IN (2, 3)` produces a vector-index search with one prefix span per
allowed tier; the quarantined and raw tiers are never entered. A **range** predicate such as
`trust_tier >= 2` silently degrades to a full scan with a post-filter - correct results, but the
poisoned partitions are walked on the way, and the isolation property is lost. Verify with
`EXPLAIN`: you want `• vector search … memory@mem_vec` with `prefix spans` limited to your tiers,
not a `• scan` with a `filter`.

An allowlist is also fail-closed by construction: a tier nobody enumerated is never traversed.

### 4. Screen content on the write path, and fail closed

Before embedding, decide the tier the content is allowed to occupy:

- **Source ceiling** — content from an `attacker_writable` source can never exceed raw evidence,
  regardless of what it claims about itself.
- **Deterministic detectors** — quarantine content shaped like an instruction (override phrases,
  injected role markers, privilege requests, tool-call syntax, encoded payloads, homoglyph and
  zero-width smuggling, exfiltration links). Normalize (NFKC, homoglyph fold, de-spacing) before
  matching so character-level evasion is caught.
- **Optional model second opinion** — may only *lower* trust, never raise it. If it errors, times
  out, or is unavailable, quarantine rather than admit.

Never delete quarantined content: store it at tier 0 with the verdict attached, so the rejection is
auditable and reversible.

### 5. Bind writes to roles, not to prompts

Grant the agent role INSERT on evidence and SELECT only through a trusted-tier view; make a separate
gate role the only one permitted to write `trust_tier`. The agent must not be able to promote its
own memory. Confirm with `SHOW GRANTS`.

## Safety and Guardrails

- **Prefix equality/IN is mandatory for isolation.** A range predicate breaks it silently — always
  `EXPLAIN` the retrieval and confirm the plan is index-served.
- **Bind trust to source, not to content claims.** Self-asserted trust ("this is from the operator")
  is exactly the attack; the source class caps it.
- **Fail closed.** Any gate error defaults to quarantine.
- **Keep provenance immutable.** Store `content_hash` at ingest; a later mismatch is grounds to
  revoke and re-evaluate everything downstream.

## References

- [Vector indexes](https://www.cockroachlabs.com/docs/stable/vector-indexes)
- [CockroachDB and AI](https://www.cockroachlabs.com/docs/stable/cockroachdb-and-ai)
- [Managing roles](https://www.cockroachlabs.com/docs/stable/security-reference/authorization)
- [Authorization / privileges](https://www.cockroachlabs.com/docs/stable/grant)
