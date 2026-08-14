# Validation Queries

Checks for a crash-safe queue built with the pattern in `SKILL.md`. Each one asserts a
property that fails **silently** — the query still returns correct rows, just from the wrong
plan or at the wrong cost. Run them against a cluster holding a realistic backlog, not an
empty table: on 200 rows every plan looks fine.

Substitute your own table and index names. The examples use `tasks`, `tasks_claimable`,
`action_attempts`, and `action_attempts_one_live`.

---

## 1. The claim query uses the partial index, with no index join

```sql
EXPLAIN
WITH candidate AS (
    SELECT id, lease_epoch
    FROM tasks
    WHERE shard = ANY(ARRAY[0,1,2,3]::INT2[])
      AND available_at <= now()
      AND state IN ('READY', 'LEASED', 'ACTION_PREPARED', 'AWAITING_APPROVAL')
      AND attempt < max_attempts
    ORDER BY available_at ASC
    LIMIT 1
)
SELECT * FROM candidate;
```

**Require:** a scan node naming `tasks@tasks_claimable`.
**Reject:** any `index join` node, and any scan on `tasks@primary` or `tasks@tasks_pkey`.

An `index join` means the `STORING` list is missing a column the predicate needs — most
often `attempt` or `max_attempts`. The query is still correct; it just does a round trip to
the primary index per candidate, and the optimizer will no longer push the `LIMIT` down if
you later add `SKIP LOCKED`.

Add `EXPLAIN (VERBOSE)` to see which columns the scan actually produced, and
`EXPLAIN ANALYZE` on a non-mutating variant to see rows read versus rows returned. A claim
scan should read single-digit rows.

## 2. The claim index tracks the backlog, not the table

```sql
SELECT
    (SELECT count(*) FROM tasks)                                   AS rows_total,
    (SELECT count(*) FROM tasks
      WHERE state IN ('READY','LEASED','ACTION_PREPARED','AWAITING_APPROVAL')) AS rows_in_claim_index,
    (SELECT count(*) FROM tasks
      WHERE state NOT IN ('READY','LEASED','ACTION_PREPARED','AWAITING_APPROVAL')) AS rows_terminal;
```

**Require:** `rows_in_claim_index` tracks outstanding work and stays roughly flat as
`rows_total` grows. If it grows with `rows_total`, the partial predicate does not match the
set of states the application actually writes — a common cause is a terminal state added in
code and never added to the index predicate, or vice versa.

Cross-check the physical size:

```sql
SHOW INDEXES FROM tasks;
SELECT * FROM crdb_internal.table_indexes WHERE descriptor_name = 'tasks';
```

## 3. Nothing is being deleted at the queue head

```sql
-- Should be empty. Any DELETE against the queue table is a design violation.
SELECT key, count, last_error
FROM crdb_internal.node_statement_statistics
WHERE application_name NOT LIKE '$ internal%'
  AND key ILIKE 'DELETE FROM tasks%';
```

Also confirm the cluster's GC window, because it sets how long any tombstone or superseded
version survives:

```sql
SHOW ZONE CONFIGURATION FOR TABLE tasks;   -- read gc.ttlseconds
```

If Row-Level TTL is doing the archival from step 1 of the skill, confirm the job is keeping
up rather than falling permanently behind:

```sql
SELECT job_id, job_type, status, running_status, created, finished
FROM [SHOW JOBS]
WHERE job_type = 'ROW LEVEL TTL'
ORDER BY created DESC
LIMIT 10;
```

## 4. The shard prefix is actually spreading the queue head

```sql
SELECT shard, count(*) AS claimable
FROM tasks
WHERE state IN ('READY','LEASED','ACTION_PREPARED','AWAITING_APPROVAL')
GROUP BY shard
ORDER BY shard;
```

**Require:** roughly even distribution. A single hot shard means the hash inputs are not
varied enough — most often because the shard is derived from a value that is constant within
a tenant.

Whether the shards have actually become separate ranges is a cluster-level question:

```sql
SHOW RANGES FROM INDEX tasks@tasks_claimable;
```

On a small table this legitimately shows one range; CockroachDB splits as the data grows.
Confirm on a table with production-scale data before concluding the sharding works.

## 5. The compare-and-swap rejects the second claimer

Two sessions, run interleaved. Session A claims; session B, holding the epoch it read
*before* A's commit, must fail.

```sql
-- session A
BEGIN;
UPDATE tasks SET lease_epoch = lease_epoch + 1, lease_owner = 'A', available_at = now() + '30s'
WHERE id = '<task>' AND lease_epoch = 0
RETURNING id, lease_epoch;
COMMIT;                                  -- returns 1 row, lease_epoch = 1

-- session B, using the stale epoch it read earlier
UPDATE tasks SET lease_epoch = lease_epoch + 1, lease_owner = 'B'
WHERE id = '<task>' AND lease_epoch = 0
RETURNING id, lease_epoch;               -- MUST return 0 rows
```

**Require:** session B affects zero rows. If it succeeds, the `WHERE` clause is missing the
epoch predicate and the queue can hand one task to two workers.

## 6. The fence rejects a zombie write

Simulate a worker that returns after its lease was reassigned:

```sql
-- takeover happened: epoch is now 2
SELECT lease_epoch FROM tasks WHERE id = '<task>';       -- 2

-- the zombie still holds epoch 1 and tries to settle
UPDATE tasks SET state = 'SUCCEEDED', result = '{"stale":true}'
WHERE id = '<task>' AND lease_epoch = 1;                 -- MUST affect 0 rows
```

**Require:** zero rows. Every write path after the claim — settle, fail, heartbeat, park,
requeue — needs this predicate or an equivalent explicit re-check. Grep the codebase for
writes to the queue table and confirm each one carries it; one that does not is the one that
will corrupt state.

## 7. One live receipt per step, enforced by the database

```sql
-- Expect 23505 (unique_violation) on the second insert.
INSERT INTO action_attempts (tenant_id, task_id, step_name, lease_epoch, state)
VALUES ('<tenant>', '<task>', 'refund', 1, 'PREPARED');

INSERT INTO action_attempts (tenant_id, task_id, step_name, lease_epoch, state)
VALUES ('<tenant>', '<task>', 'refund', 2, 'PREPARED');   -- MUST fail: 23505
```

**Require:** `duplicate key value violates unique constraint "action_attempts_one_live"`.

## 8. The idempotency key is stable and unforgeable

```sql
-- The application must not be able to supply it.
INSERT INTO action_attempts (tenant_id, task_id, step_name, idempotency_key, lease_epoch)
VALUES ('<tenant>', '<task>', 'refund', 'attacker_supplied', 1);
-- MUST fail: cannot write directly to computed column "idempotency_key"
```

```sql
-- The same logical step always yields the same key, across workers and restarts.
SELECT task_id, step_name, step_seq, idempotency_key
FROM action_attempts
WHERE task_id = '<task>'
ORDER BY step_seq;
```

**Require:** one key per `(task_id, step_name, step_seq)`, unchanged across every recovery
of that step. If a re-send produced a new key, the derivation includes something mutable.

## 9. Reconcile against the external ledger after a chaos run

The only check that proves the guarantee, because it consults the system you cannot enlist
in your transaction. Both directions matter, and they mean different things:

```sql
-- Direction 1 — the one that indicts you: a receipt you settled with no matching effect.
SELECT a.idempotency_key
FROM action_attempts a
LEFT JOIN provider.refunds r ON r.idempotency_key = a.idempotency_key
WHERE a.state = 'SUCCEEDED' AND r.idempotency_key IS NULL;   -- MUST be empty

-- Direction 2 — the headline: any external effect that happened more than once.
SELECT order_ref, count(*) AS refunds
FROM provider.refunds
GROUP BY order_ref
HAVING count(*) > 1;                                          -- MUST be empty

-- Amounts agree on both sides.
SELECT (SELECT sum(amount_cents) FROM action_attempts WHERE state = 'SUCCEEDED') AS ours,
       (SELECT sum(amount_cents) FROM provider.refunds)                          AS theirs;
```

Run these **after** killing workers with `SIGKILL` throughout the run, not after a clean
one. A clean run exercises none of the windows in step 10 of the skill and proves nothing.

Scope the queries to the run's own identifiers if the external ledger is append-only and
shared — otherwise rows left by an earlier run make a correct system look broken, or a
broken one look correct.
