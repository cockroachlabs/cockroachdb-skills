---
name: designing-durable-agent-execution
description: Guides developers building autonomous agents or workflow workers in making each side-effecting step durable and exactly-once on CockroachDB, using a write-ahead intent ledger, deterministic idempotency keys, and lease-with-epoch fencing under SERIALIZABLE isolation so a worker that crashes mid-step can be resumed by another without double-applying effects. Use when an agent or job runner takes external actions such as remote calls, deployments, or payments, when a step must not run twice after a crash or retry, when coordinating multiple workers over shared work, or when designing resume-after-failure for long-running processes.
compatibility: "CockroachDB >= 22.1 (SERIALIZABLE default). Requires a SQL connection with privileges to create tables and to read and write the ledger tables on the target database."
metadata:
  author: cairn
  version: "1.0"
---

# Designing Durable Agent Execution

An agent that only produces text can retry freely. An agent that *acts* - calls an API, changes a
deployment, moves money - cannot: a crash between the action and the record of it leaves the
outside world changed with no memory that it happened. Naive replay double-applies; abandoning the
run leaves it half-done.

This skill encodes the pattern that makes each step durable and exactly-once on CockroachDB: write
the intent before the effect, make the effect idempotent under a deterministic key, and fence
ownership with a lease epoch so a superseded worker cannot record a stale result. CockroachDB's
SERIALIZABLE isolation is what makes the coordination race-free without advisory locks, and its
distributed replication is what keeps the ledger readable when the node or region running the
worker is lost.

## When to Use This Skill

- An agent or worker performs external, side-effecting actions that must happen exactly once
- A step must survive a process crash, a lost container, or a retimed retry without double-applying
- Multiple workers share a pool of work and must not both execute the same step
- You need resume-after-failure: a fresh worker finishes what a dead one started
- You want an auditable record of what was *about* to happen, not only what completed

## Prerequisites

- Familiarity with CockroachDB's SERIALIZABLE isolation and client-side retry on `40001`
- Effects that can be made idempotent by a caller-supplied key (most APIs support this)
- A SQL connection to the target cluster

## Steps

### 1. Record the intent before the effect

Persist what you are about to do, committed, before doing it. The intent carries a deterministic
idempotency key so a replay of the same logical step produces the same key.

```sql
CREATE TABLE step_intent (
    tenant_id  UUID   NOT NULL,
    idem_key   STRING NOT NULL,           -- sha256(run_id ‖ step_no ‖ effector ‖ canonical(params))
    run_id     UUID   NOT NULL,
    step_no    INT    NOT NULL,
    effector   STRING NOT NULL,
    params     JSONB  NOT NULL,
    lease_owner      STRING,
    lease_expires_at TIMESTAMPTZ,
    lease_epoch      INT NOT NULL DEFAULT 0,
    PRIMARY KEY (tenant_id, idem_key),
    INDEX by_run (tenant_id, run_id, step_no)
);
```

Derive `idem_key` from the run, the step, the effector, and a **canonical** serialization of the
parameters (sort object keys; render numbers uniformly). Logically identical steps must hash
identically, so `INSERT … ON CONFLICT (tenant_id, idem_key) DO NOTHING` collapses a replay onto the
original row.

### 2. Claim a step with a lease, and fence it with an epoch

A worker takes the lowest-numbered step that has no result and no live lease, bumping an epoch each
time it is claimed. The epoch, not the wall-clock expiry, is what later proves ownership.

```sql
UPDATE step_intent
   SET lease_owner = $worker,
       lease_expires_at = now() + ($lease_seconds::FLOAT8 * INTERVAL '1 second'),
       lease_epoch = lease_epoch + 1
 WHERE (tenant_id, idem_key) IN (
         SELECT i.tenant_id, i.idem_key
           FROM step_intent i
           LEFT JOIN step_result r
                  ON r.tenant_id = i.tenant_id AND r.idem_key = i.idem_key
          WHERE i.tenant_id = $tenant AND i.run_id = $run
            AND r.idem_key IS NULL
            AND (i.lease_owner IS NULL OR i.lease_expires_at < now())
          ORDER BY i.step_no
          LIMIT 1)
RETURNING idem_key, step_no, effector, params, lease_epoch;
```

Under SERIALIZABLE, two workers racing on the same row cannot both win - one retries and finds the
step already claimed. Do **not** weaken isolation here; the guarantee depends on it.

> **Note:** `make_interval(secs => …)` is not available in CockroachDB. Compute intervals with
> `x::FLOAT8 * INTERVAL '1 second'`.

### 3. Execute the effect, keyed by the idempotency key

Pass `idem_key` to the effector. The effector must be idempotent under that key: either the target
API accepts an idempotency key, or you dedupe with an append-only `effect_log` whose primary key is
`idem_key` and return the previously recorded outcome on a repeat.

```sql
-- inside the effector, one transaction
SELECT observed_state FROM effect_log WHERE tenant_id = $t AND idem_key = $k;  -- already applied?
-- if not present: perform the change, then
INSERT INTO effect_log (tenant_id, idem_key, applied_by, observed_state) VALUES ($t, $k, $worker, $obs);
```

### 4. Record the result, fenced by the epoch

Write the outcome only if this worker still holds the epoch it was granted. A worker whose lease
lapsed and was taken over by another is locked out even if its own clock disagrees.

```sql
INSERT INTO step_result (tenant_id, idem_key, outcome, observed_state, lease_epoch)
SELECT $t, $k, $outcome, $obs, $epoch
 WHERE EXISTS (SELECT 1 FROM step_intent
                WHERE tenant_id = $t AND idem_key = $k AND lease_epoch = $epoch);
-- rowcount 0 => this worker was superseded; discard and stop.
```

### 5. Resume by replaying the ledger

Recovery needs no special path: a fresh worker simply runs steps 2–4 in a loop. It claims the
first step with no result whose lease has lapsed, re-executes it (a no-op at the effector if it
already ran), records the result, and continues until the run is drained.

## Safety and Guardrails

- **Verify against real external state, not a self-reported counter.** After a resume, read the
  target system back (a service's task-definition revision, an order's status) and assert it
  advanced exactly once. A counter you increment yourself proves nothing.
- **Keep the transaction short.** The intent write and the result write are each their own small
  transaction; the effect runs *between* them, never inside a database transaction (see the
  [designing-application-transactions](https://github.com/cockroachlabs/cockroachdb-skills/tree/main/skills/cockroachdb-application-development/designing-application-transactions)
  skill).
- **Do not lower isolation** to avoid retries. Handle `40001` with client-side retry instead.
- **Idempotency keys must be deterministic and canonical.** A key that varies with map ordering or
  float formatting defeats the whole design.

## References

- [Transactions](https://www.cockroachlabs.com/docs/stable/transactions)
- [SERIALIZABLE isolation](https://www.cockroachlabs.com/docs/stable/demo-serializable)
- [Client-side transaction retries](https://www.cockroachlabs.com/docs/stable/advanced-client-side-transaction-retries)
- [Coordinate agent state](https://www.cockroachlabs.com/docs/stable/cockroachdb-and-ai)
