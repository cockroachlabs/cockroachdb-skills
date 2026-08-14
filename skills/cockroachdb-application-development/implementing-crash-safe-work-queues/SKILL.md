---
name: implementing-crash-safe-work-queues
description: Guides developers in building a durable work queue on CockroachDB that survives worker crashes without duplicating external side effects, covering the partial claim index that keeps finished work out of the hot path, an explicit shard column instead of USING HASH, fencing tokens instead of leases as the correctness mechanism, state transitions instead of DELETE so no tombstones accumulate behind the queue head, and a GENERATED STORED idempotency key that cannot be minted at call time. Use when implementing a job queue, task queue, outbox, or agent execution layer on CockroachDB; when workers can be SIGKILLed, OOM-killed, or reclaimed mid-operation; when a queue table has become a hotspot or its claim query has slowed as the table grew; or when a retry after a crash must not re-issue a payment, email, or other non-idempotent external call.
compatibility: "CockroachDB >= 22.2 for the queue pattern (partial indexes, computed columns, SELECT FOR UPDATE). SELECT ... FOR UPDATE SKIP LOCKED requires >= 22.2. Works against any cluster; the validation steps need a live SQL connection with privileges on the target tables."
metadata:
  author: axiom-project
  version: "1.0"
  source: https://github.com/Dhruvjain35/axiom
---

# Implementing Crash-Safe Work Queues

Guides the design of a work queue whose workers can die at any instant — SIGKILL, OOM,
spot reclamation, a GC pause long enough to lose a lease — without losing work, running
work twice, or turning the queue table into a hotspot.

CockroachDB's own guidance names queues as a hotspot anti-pattern: they "require data to
be ordered by write, which necessitates indexing in a way that is likely to create a
hotspot," and deleting rows as they are read "tends to accumulate an ordered set of
garbage data behind the live data." Both statements are true of the naive design. This
skill is the set of schema and protocol decisions that make a queue viable anyway, and it
treats crash safety and hotspot avoidance as the same problem, because the two usual
fixes for one make the other worse.

**Scope boundary.** This skill covers the queue: its DDL, its claim protocol, and the
handoff to a non-transactional external call. For general transaction design, retry
loops, and connection pooling see
[designing-application-transactions](../designing-application-transactions/SKILL.md).

## When to Use This Skill

- Designing a job, task, or work queue table on CockroachDB
- Implementing a transactional outbox that dispatches to an external API
- Building an agent or workflow execution layer where a step has a real-world effect
- Workers run on preemptible or autoscaled infrastructure and can be killed mid-operation
- A queue's claim query has slowed as the table grew, or one range is absorbing all writes
- A crash has caused a duplicate payment, email, webhook, or provisioning call
- Deciding between `DELETE`-on-complete and state transitions
- Deciding between `USING HASH` and an application-managed shard column
- Deciding between a lease timeout and a fencing token
- Reviewing a queue implementation for correctness under concurrency

## Prerequisites

- A CockroachDB cluster (any topology) and privileges to create tables and indexes
- Familiarity with SERIALIZABLE isolation and client-side `40001` retry loops
- An external system whose API supports idempotency keys, if the queue drives side effects
- Understanding that MVCC garbage is reclaimed only after `gc.ttlseconds`, not at `DELETE`

## Steps

### 1. Complete Work With a State Transition, Never a DELETE

Do not delete a row when its work finishes. Transition its `state` to a terminal value and
leave it in place.

```sql
-- Anti-pattern: the queue head accumulates tombstones the claim scan must step over.
DELETE FROM tasks WHERE id = $1;

-- Correct: the row stays, and step 2 makes it leave the index that matters.
UPDATE tasks SET state = 'SUCCEEDED', updated_at = now() WHERE id = $1;
```

**Why it matters.** A `DELETE` in CockroachDB writes a deletion tombstone at the same key.
The key range that a queue scans is, by construction, ordered by write time, so every
tombstone lands directly in front of the next scan. Those tombstones survive until
`gc.ttlseconds` elapses — 4 hours by default, and often longer on managed clusters — so a
queue that deletes on completion pays a scan cost proportional to recent throughput rather
than to the depth of the backlog. The row also *is* the audit record: what ran, when, under
whose lease, with what result. Deleting it destroys the only evidence of the side effect it
caused.

**Bounding growth honestly.** "Never delete" cannot mean "grow forever." Reclaim space
*behind* the queue head, never at it: use [Row-Level TTL](https://www.cockroachlabs.com/docs/stable/row-level-ttl)
with a long `ttl_expiration_expression` on terminal rows, or periodically move terminal
rows to an archive table. Both run far from the live key range and neither competes with
the claim scan. Verify the TTL job is keeping up before relying on it.

### 2. Make the Claim Index PARTIAL on Non-Terminal States

One index serves the claim loop, and it is partial.

```sql
CREATE INDEX tasks_claimable
    ON tasks (shard ASC, available_at ASC)
    STORING (state, tenant_id, lease_epoch, lease_owner, attempt, max_attempts, task_type)
    WHERE state IN ('READY', 'LEASED', 'ACTION_PREPARED', 'AWAITING_APPROVAL');
```

A terminal `UPDATE` from step 1 causes the row to fall **out** of this index. The index
therefore tracks the size of the backlog, not the size of the table: a queue that has
processed ten million rows and has forty outstanding has a forty-entry claim index. This is
the direct answer to the "ordered set of garbage data behind the live data" warning — the
garbage is never in the index in the first place, and because nothing was deleted, there
are no tombstones either.

See [Partial Indexes](https://www.cockroachlabs.com/docs/stable/partial-indexes). The
predicate must be immutable; enumerate the states explicitly rather than writing
`WHERE state NOT IN (...)` if the terminal set is the one likely to grow.

### 3. Prefix the Claim Index With an Explicit Shard Column

The claim index is ordered by time, which means without a prefix the head of the queue is a
single range and every worker contends on it.

```sql
shard INT2 NOT NULL AS (
    mod(fnv32(crdb_internal.datums_to_bytes(tenant_id::STRING || ':' || dedupe_key)), 16)::INT2
) STORED,
```

`fnv32(crdb_internal.datums_to_bytes(...))` is the same hash CockroachDB's own
[hash-sharded indexes](https://www.cockroachlabs.com/docs/stable/hash-sharded-indexes)
compute internally. Making it a declared column rather than using `USING HASH` costs one
line and buys two things:

- **Workers can target a shard subset.** `WHERE shard = ANY($1)` gives static work
  partitioning across a worker pool, the way a Kafka consumer group assigns partitions. The
  `crdb_internal_..._shard_N` column that `USING HASH` synthesizes is not a stable
  application-facing name and should not be filtered on by application code.
- **The bucket count is visible in the schema** next to the reasoning for it.

Choose the bucket count deliberately: enough to spread writes across nodes, not so many
that each claim scan touches many ranges. Start near the number of concurrent workers and
measure. `USING HASH` remains the right tool where the key is genuinely monotonic and no
one needs to address a bucket — an append-only event timeline indexed by time, for example.

### 4. Store the Columns the Claim Predicate Reads

`STORING` in step 2 is not a latency micro-optimization. It keeps the candidate `SELECT`
index-only, so a predicate like `attempt < max_attempts` is evaluated without an index join
back to the primary index — and the optimizer will not push a `LIMIT` through an index join
when `SKIP LOCKED` is in play, so a covering index is what makes the optional `SKIP LOCKED`
path viable at all.

Do **not** store a large `JSONB` payload. It doubles the index's storage, and returning it
from the claim statement pushes the result toward the buffer size past which CockroachDB
can no longer transparently retry the statement server-side. Claim the row, then read the
payload by primary key.

### 5. Claim in One Statement, With a Compare-and-Swap on the Fence

```sql
WITH candidate AS (
    SELECT id, lease_epoch
    FROM tasks
    WHERE shard = ANY($1::INT2[])
      AND available_at <= now()
      AND state IN ('READY', 'LEASED', 'ACTION_PREPARED', 'AWAITING_APPROVAL')
      AND attempt < max_attempts
    ORDER BY available_at ASC
    LIMIT 1
)
UPDATE tasks t
SET lease_epoch  = t.lease_epoch + 1,
    lease_owner  = $2,
    available_at = now() + $3::INTERVAL,
    state        = CASE WHEN t.state IN ('READY', 'AWAITING_APPROVAL')
                        THEN 'LEASED' ELSE t.state END,
    updated_at   = now()
FROM candidate c
WHERE t.id = c.id AND t.lease_epoch = c.lease_epoch
RETURNING t.id, t.tenant_id, t.state, t.lease_epoch, t.attempt, t.max_attempts;
```

`t.lease_epoch = c.lease_epoch` is the compare-and-swap. Two workers that select the same
candidate cannot both succeed: the loser's `UPDATE` matches zero rows and returns nothing.

**Returning zero rows is not an error.** It means "nothing claimable, or someone else won" —
two conditions the caller must treat identically, by backing off and trying again. Code that
raises on an empty claim will page someone every time the queue drains.

Under heavy contention, `SELECT ... FOR UPDATE SKIP LOCKED` in the candidate CTE reduces
retries by letting each worker skip locked candidates instead of colliding on them. It is an
optimization on top of the CAS, not a replacement for it: `SKIP LOCKED` is advisory within a
transaction's lifetime and says nothing about a worker that is already gone.

### 6. Use a Fencing Token, Not the Lease, as the Correctness Mechanism

The lease is a liveness optimization. The fence is the invariant. Every write after the
claim re-checks the token the worker holds:

```sql
SELECT lease_epoch, lease_owner FROM tasks WHERE id = $1;
-- if lease_epoch <> the epoch this worker holds, abort. Do not write.
```

**Why a timeout is not enough.** A lease expiring does not stop a worker; nothing stops a
worker. A process inside a 30-second GC pause, or blocked in a socket read to a payment
API, is still going to return and try to write its result — after the queue has already
handed the task to someone else. `lease_epoch` is monotonic **per row**, so it is not a
global sequence and creates no hotspot, and the takeover incremented it. The zombie's write
matches nothing and lands nowhere.

Make the fence a structural invariant rather than a convention:

```sql
CONSTRAINT tasks_lease_ck CHECK (
    (state IN ('LEASED', 'ACTION_PREPARED')) = (lease_owner IS NOT NULL)
)
```

### 7. Let One Column Be Both Earliest-Run-Time and Lease Expiry — and Delete the Reaper

Give the row a single `available_at TIMESTAMPTZ`. Claim sets it to `now() + lease`;
heartbeat pushes it forward; a retryable failure sets it to `now() + backoff`.

The claim predicate `available_at <= now()` then means "ready to run **or** the owner is
dead," with no reaper process and no second index.

**Why this matters more than it looks.** A reaper is a periodic, large, multi-row
transaction that scans for expired leases — landing on precisely the rows the claim loop is
trying to read, at intervals, forever. It is the most common way a queue design that avoided
one hotspot acquires another. A self-expiring lease has no such process. The queue heals
itself as a side effect of the query it already runs.

### 8. Generate the Idempotency Key; Do Not Let Callers Mint One

If the task causes an external effect, write a receipt row before the call, and derive its
idempotency key from immutable columns in the database:

```sql
CREATE TABLE action_attempts (
    id          UUID NOT NULL DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL,
    task_id     UUID NOT NULL REFERENCES tasks(id),
    step_name   STRING NOT NULL,
    step_seq    INT4 NOT NULL DEFAULT 1,

    idempotency_key STRING NOT NULL AS (
        'idem_' || substring(
            sha256(tenant_id::STRING || ':' || task_id::STRING || ':' ||
                   step_name || ':' || step_seq::STRING)
            FROM 1 FOR 48)
    ) STORED,

    lease_epoch INT8 NOT NULL,
    state       STRING NOT NULL DEFAULT 'PREPARED',
    CONSTRAINT action_attempts_pkey PRIMARY KEY (id),
    CONSTRAINT action_attempts_key_uniq UNIQUE (tenant_id, idempotency_key)
);
```

**This is the single most consequential line in the design.** The lethal bug in this class
of system is a key minted at call time from `gen_random_uuid()`, a timestamp, the worker id,
the attempt number, or the lease epoch. All five look reasonable in review. All five mean
that the worker which takes over after a crash computes a *different* key, the provider sees
a brand-new request, and the payment goes out twice. A
[computed column](https://www.cockroachlabs.com/docs/stable/computed-columns) removes the
possibility from the codebase instead of from the code review, because there is no code path
that can supply the value.

Derive it only from columns that cannot change: tenant, task, step name, step sequence.
Bump `step_seq` only on an explicit, recorded decision that a genuinely new external call is
required — never on a retry of the same logical call.

### 9. Enforce "At Most One In-Flight Call Per Step" With a Unique Partial Index

```sql
CREATE UNIQUE INDEX action_attempts_one_live
    ON action_attempts (tenant_id, task_id, step_name)
    WHERE state IN ('PREPARED', 'DISPATCHED');
```

Two workers racing to start the same step: the loser gets `23505`, not a second refund. The
index is partial so that terminal rows leave it, which keeps a legitimate later `step_seq`
representable after a terminal rejection.

Checking for a live receipt in application code first is worth doing — it turns a database
error into an explicit control-flow branch — but the index is what makes the guarantee true
when the check races.

### 10. Commit the Receipt Before the Call, and Keep the Call Outside Every Transaction

The ordering is the whole design:

```
BEGIN;  insert receipt (state=PREPARED, fence re-checked);  COMMIT;   -- durable intent
        call the external API with receipt.idempotency_key             -- no transaction
BEGIN;  fence re-checked; record outcome; state=SUCCEEDED;   COMMIT;   -- durable outcome
```

Because the receipt commits **before** anything can be sent, the question "might an effect
have happened?" is a point read on an index, not an inference about timing. Every crash
point has a defined answer:

| Crash point | Effect possible? | Recovery |
| --- | --- | --- |
| After claim, before the receipt commits | No | Re-claim under a new epoch; re-plan freely |
| After the receipt commits, before the send | Yes, unknowably | Re-send under the **same** stored key |
| Mid-flight, outcome unknown | Yes | Same as above; the two are indistinguishable and must be treated identically |
| Provider responded, before the outcome commits | Yes — it landed | Re-send under the same key; the provider returns the original result |
| Zombie settles after takeover | Yes | Rejected on a stale `lease_epoch` (step 6) |

Never place the external call inside the transaction. A `40001` retry re-executes the whole
transaction body, so an HTTP call inside it is an HTTP call that runs twice.

**State the guarantee precisely: this is effectively-once, not exactly-once.** No system
that calls an API it does not control can promise exactly-once delivery of a side effect.
What this design promises is a durable receipt, a stable derived key, and a defined outcome
in every crash window — which is what "the money moves once" actually requires in practice.

### 11. Fingerprint the Request Body; the Same Key With a Different Body Is Not a Retry

Store `request_fingerprint STRING NOT NULL` — a hash of the canonicalized request body —
alongside the receipt, and compare it before re-sending.

A recovering worker that reconstructs the request from upstream state (or from a model, in
an agent system) can produce a subtly *different* body: a different amount, a different
destination. Re-sending that under the original key is not a retry, it is a new intent
wearing an old key. Treat a fingerprint mismatch as a hard stop and escalate; do not send.

Stripe's API applies the same rule from the other side, rejecting a reused key with changed
parameters, so a mismatch you fail to catch becomes an error at the provider rather than a
silent overwrite. Catch it before the call.

### 12. Validate the Design Against the Cluster, Not the Diagram

Every property above degrades **silently** — the rows still come back correct, just from the
wrong plan. Assert on plans:

```sql
EXPLAIN WITH candidate AS (SELECT id, lease_epoch FROM tasks
    WHERE shard = ANY(ARRAY[0,1]::INT2[]) AND available_at <= now()
      AND state IN ('READY','LEASED') AND attempt < max_attempts
    ORDER BY available_at ASC LIMIT 1) SELECT * FROM candidate;
```

Require the plan to name `tasks@tasks_claimable` and show no index join. Full queries for
this and the other checks — index size against backlog depth rather than table size, no
tombstone accumulation, the CAS rejecting the second claimer, the fence rejecting a zombie
write — are in [references/validation-queries.md](references/validation-queries.md).

Then test the crash itself. `SIGKILL` a worker mid-operation, repeatedly, while the queue is
running, and reconcile the external system's ledger against your own afterward. `SIGTERM` is
not a test: it runs signal handlers and `finally` blocks, and every one of the bugs this
skill prevents lives in the path where none of that runs.

## Decision Guide

| Scenario | Recommended Pattern |
| --- | --- |
| Work finished | `UPDATE ... SET state = <terminal>`, never `DELETE` |
| Terminal rows growing unboundedly | Row-Level TTL or archival, far behind the queue head |
| Keeping the claim index small | Partial index on non-terminal states |
| Spreading the queue head across ranges | Explicit computed `shard` column, prefixed on the claim index |
| Genuinely monotonic key, no need to address buckets | `USING HASH` |
| Two workers select the same candidate | CAS on `lease_epoch` in the `UPDATE ... WHERE` |
| High contention on the candidate scan | Add `FOR UPDATE SKIP LOCKED`, keep the CAS |
| Worker that may be paused, not dead | Fencing token re-checked on every write |
| Expired leases | `available_at` doubling as lease expiry — no reaper |
| External call that must not repeat | `GENERATED STORED` idempotency key + receipt committed before the call |
| Two workers starting the same step | Unique partial index over in-flight receipts |
| Recovered worker rebuilt the request | Compare `request_fingerprint`; mismatch is a hard stop |

## Safety Considerations

- **Never call an external API inside a transaction.** A `40001` retry re-runs the body, and
  a non-idempotent call inside it runs twice.
- **Never derive an idempotency key from anything mutable** — not the attempt number, not the
  lease epoch, not the worker id, not a timestamp. A recovering worker must compute the same
  key the dead one used, or the design provides nothing.
- **Do not claim "exactly-once."** Say effectively-once, and document what happens in each
  crash window.
- **An empty claim result is normal.** Do not alert on it.
- **Do not add a reaper process** to expire leases. It reintroduces the hotspot the partial
  index removed.
- **Verify `gc.ttlseconds` on the target cluster** before assuming deleted or updated rows
  stop costing anything. Managed clusters often set it well above the 4-hour default.
- **Test with `SIGKILL`, not `SIGTERM`,** and reconcile against the external ledger — the one
  system you cannot enlist in your transaction — rather than against your own records.
- **Measure the shard count** against real worker concurrency. Too few leaves a hotspot; too
  many makes every claim scan touch every range.

## References

- [Understand Hotspots](https://www.cockroachlabs.com/docs/stable/understand-hotspots) — the queueing anti-pattern this skill works around
- [SQL Performance Best Practices](https://www.cockroachlabs.com/docs/stable/performance-best-practices-overview)
- [Partial Indexes](https://www.cockroachlabs.com/docs/stable/partial-indexes)
- [Computed Columns](https://www.cockroachlabs.com/docs/stable/computed-columns)
- [Hash-Sharded Indexes](https://www.cockroachlabs.com/docs/stable/hash-sharded-indexes)
- [`SELECT ... FOR UPDATE` and `SKIP LOCKED`](https://www.cockroachlabs.com/docs/stable/select-for-update)
- [Row-Level TTL](https://www.cockroachlabs.com/docs/stable/row-level-ttl)
- [Transaction Retry Error Reference (`40001`)](https://www.cockroachlabs.com/docs/stable/transaction-retry-error-reference)
- [Configure Replication Zones — `gc.ttlseconds`](https://www.cockroachlabs.com/docs/stable/configure-replication-zones)
- [Architecture: Storage Layer](https://www.cockroachlabs.com/docs/stable/architecture/storage-layer) — why a `DELETE` is a write
- [Martin Kleppmann, "How to do distributed locking"](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html) — the origin of the fencing-token argument
- [Stripe API: Idempotent Requests](https://docs.stripe.com/api/idempotent_requests) — the provider-side contract steps 8–11 are written against
- [AXIOM](https://github.com/Dhruvjain35/axiom) — an open-source reference implementation of this pattern, with a test per crash window and a chaos harness that `SIGKILL`s workers mid-refund
