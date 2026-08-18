---
name: retrying-agent-decisions-under-contention
description: Guides developers building LLM-driven or agent-driven writes on CockroachDB through what to do when a serialization failure invalidates a decision a model has already made. Covers checking first whether the constraint belongs in SQL instead, keeping model calls outside the transaction without replaying stale decisions, re-deriving rather than replaying on retry, refreshing retrieved context as well as database state, and instrumenting reasoning calls so a retry that failed to re-decide is detectable. Use when an agent reads state, calls a model, and writes a value derived from both; when a retry loop replays a decision computed against a stale read; or when a constraint the agent must respect lives in retrieved documents rather than in a column.
compatibility: "CockroachDB >= 23.2 for READ COMMITTED comparisons; >= 22.1 otherwise. Requires INSERT/SELECT privileges on the target tables."
metadata:
  author: racelab
  version: "1.0"
---

# Retrying Agent Decisions Under Contention

Guides application developers whose writes are chosen by a language model rather
than computed by deterministic code. Under SERIALIZABLE isolation those writes
hit `40001` like any others, but the standard remedy — retry the transaction —
behaves differently when the value being written was produced by a model call
that cannot be replayed inside the retry.

**Complement to existing skills.** For transaction scoping, retry loops with
backoff, and connection pooling, see
[designing-application-transactions](../designing-application-transactions/SKILL.md).
For measuring contention across transaction formulations, see
[benchmarking-transaction-patterns](../benchmarking-transaction-patterns/SKILL.md).
This skill covers only the case where the *decision* — not just the statement —
must be reconsidered.

## The gap this addresses

Two pieces of standard guidance are individually correct and, composed, produce a
silent bug.

`designing-application-transactions` step 14 says keep RPC and HTTP calls
**outside** the transaction. That is right: holding a transaction open across a
model call — often hundreds of milliseconds to several seconds — extends the
contention window and risks the transaction being aborted for age.

The same skill's step 3 says retry the unit of work on `40001` with backoff. Also
right.

Now compose them for an agent:

```python
# Outside the transaction, as step 14 requires.
decision = model.decide(context=retrieved_docs, observed_state=state)

# Retried on 40001, as step 3 requires.
def txn_logic(txn):
    txn.execute("INSERT INTO allocations (amount) VALUES (%s)", (decision.amount,))

execute_with_retry(conn, txn_logic)
```

The retry re-executes `txn_logic`. It does **not** re-execute `model.decide`,
because that call is deliberately outside. So every retry re-submits a value
derived from a state reading that the `40001` just proved is out of date.

This is the failure the same skill's safety note names —
*"do not use stale snapshot reads as authoritative preconditions for writes"* —
without saying what to do when the precondition passed through a model.

## When to Use This Skill

Use it when **all** of the following hold:

- A write's value is chosen by a model, or by application logic over retrieved
  documents, rather than computed arithmetically from the rows being written.
- The decision depends on state read from the database in the same logical unit
  of work.
- The correctness condition cannot be expressed as a predicate over columns.

**Do not use it when the constraint fits in SQL.** That case is solved, more
simply and more cheaply, by step 5 of
[designing-application-transactions](../designing-application-transactions/SKILL.md):
push the invariant into the statement and the read-modify-write race disappears.

```sql
-- If this expresses your rule, stop here. You do not need a retry protocol.
UPDATE customer_daily_limits
SET used_total = used_total + $2
WHERE customer_id = $1
  AND day = current_date
  AND used_total + $2 <= daily_limit;
```

A guarded `UPDATE` can only reference columns. The condition this skill exists
for is the one you cannot put in a `WHERE` clause: an approval ceiling stated in
a policy document, a tier rule retrieved by vector search, a spending cap that a
model inferred from unstructured text. There is no column to compare against.

## Prerequisites

- CockroachDB with SERIALIZABLE isolation (the default).
- A client that surfaces `40001` / `SerializationFailure` rather than retrying it
  invisibly inside the driver.
- A bounded, enumerable set of actions the agent may take. Free-form output makes
  step 6 impossible.
- Read [designing-application-transactions](../designing-application-transactions/SKILL.md)
  first, and confirm step 5 does not already solve your problem.

## Steps

### 1. Classify the constraint before writing any retry code

Ask where the rule lives. The answer selects the whole approach.

| The rule is | Example | Use |
|---|---|---|
| A column, or arithmetic on columns | `used_total + $2 <= daily_limit` | Guarded `UPDATE` (step 5 of the transactions skill). Stop. |
| A schema-level integrity rule | uniqueness, foreign keys | Constraints. Stop. |
| An aggregate over many rows in another table | `SUM(child.amount) <= parent.limit` | A materialized counter with a guarded update, if the limit is a column. |
| Retrieved text, or a model's inference over it | "ceiling reduced to $60, effective immediately" | This skill. |

Only the last row needs what follows. Classifying wrongly costs you a retry
protocol where one `WHERE` clause would have done.

### 2. Keep the model call outside the transaction, and know what that costs

Do not hold a transaction open across a model call. A multi-second inference
inside a transaction widens the contention window for every competing writer and
invites `40001` on transactions that would otherwise have committed.

The cost of obeying this is the gap above: the decision now lives outside the
retry boundary. Steps 3 and 4 close it deliberately rather than by accident.

### 3. Re-derive the decision on retry; do not replay it

Structure the unit of work so the reasoning step is **inside** the retried
closure while the *network call* is still outside the transaction. In practice:
open the transaction, read state, close nothing, call the model, then write —
with the whole sequence retried, and the model re-invoked each time.

```python
def run_with_reconsideration(conn, decide, read_state, apply, max_attempts=5):
    """On 40001, discard the decision and derive a new one from fresh state."""
    for attempt in range(max_attempts):
        try:
            conn.execute("BEGIN")
            state = read_state(conn)          # fresh read, every attempt
            decision = decide(state, attempt)  # re-invoked, every attempt
            apply(conn, decision)
            conn.execute("COMMIT")
            return decision
        except SerializationFailure:
            conn.execute("ROLLBACK")
            # Another transaction changed state relevant to this decision. It
            # does not follow that the decision was wrong -- only that it was
            # derived from a reading that no longer holds.
            continue
    raise RetriesExhausted()
```

The model call sits between `BEGIN` and `COMMIT` here, which contradicts step 2
if taken literally. Resolve it one of two ways, and pick deliberately:

- **Short inference, low contention:** accept the call inside the transaction and
  keep `max_attempts` low. Simplest, and fine when inference is fast.
- **Slow inference, or high contention:** read state in its own short
  transaction, call the model outside any transaction, then open a second short
  transaction that **re-reads and re-validates** before writing. If the re-read
  disagrees with what the decision assumed, discard it and go round again. This
  keeps transactions short at the cost of one extra read.

The second pattern is the one to reach for in production. What both share, and
what matters, is that **a new attempt produces a new decision.**

### 4. Refresh retrieved context, not only database state

Re-reading rows is not sufficient when the constraint lives in retrieved text.
If a policy document changed while the agent was working, the database rows can
be perfectly current while the rule the agent is applying is stale.

On retry, re-run retrieval as well as the state read:

```python
def decide(state, attempt):
    if attempt > 0:
        context = retrieve(query, k=4)   # the policy may have changed too
    return model.decide(context=context, observed_state=state)
```

Ordering matters: retrieval is a read against possibly-different rows, so run it
**outside** the transaction that will do the write — before `BEGIN` or after
`ROLLBACK`, never between. A retrieval issued inside the racing transaction adds
its read set to that transaction's refresh span and changes the conflict rate you
are trying to measure.

Store the retrieved documents in CockroachDB and this stays one system: see
[pgvector and vector indexes](https://www.cockroachlabs.com/docs/stable/vector-indexes)
for keeping embeddings, relational rows and agent state transactionally
consistent.

### 5. Count reasoning invocations, not just retries

The failure mode of this protocol is silent. A retry loop that re-reads state but
reuses a cached decision produces plausible numbers and no errors, and no
assertion about the final state will catch it — the value written is a value the
model really did choose, just not for the state it was written against.

Instrument the mechanism:

```python
calls = {"n": 0}
def counted(state, attempt):
    calls["n"] += 1
    return decide(state, attempt)

result = run_with_reconsideration(conn, counted, ...)

# A conflict-aware attempt must have reasoned once per attempt.
assert calls["n"] == result.attempts, (
    f"{result.attempts} attempts but {calls['n']} reasoning calls: "
    "a retry replayed a decision instead of re-deriving it"
)
```

Assert this in tests and in staging. An off-by-one here is the difference between
the protocol working and the protocol appearing to work.

### 6. Bound the action space and validate the model's output

Constrain the model to an enumerated set of actions and **validate the value you
get back.** A tool or function schema that declares an `enum` is guidance to the
model, not a contract enforced by the API; models do return values outside a
declared enum, particularly when the "obviously right" answer is not in the set.

```python
VALID = {"allocate(45)", "allocate(40)", "allocate(35)", "abstain"}

if action not in VALID:
    # Re-ask with the violation named. Do not coerce, and do not silently
    # substitute a deterministic fallback -- that reports your arithmetic as the
    # model's judgement, and nothing in the output would show it happened.
    raise OutOfActionSpace(action)
```

Never fall back to a hand-computed value on a malformed response. A quiet
substitution produces a number with nothing to indicate where it came from.

### 7. Record what the agent believed, not only what it wrote

Log, per attempt: the state observed, the constraint the agent inferred from
retrieved context, the action chosen, and the retrieved document ids. Without the
inferred constraint you cannot distinguish "the model reasoned badly" from "the
model reasoned correctly over a stale document", and those need opposite fixes.

```sql
CREATE TABLE agent_decisions (
    decision_id       UUID PRIMARY KEY,
    unit_of_work_id   TEXT NOT NULL,
    attempt_no        INT  NOT NULL,
    observed_state    JSONB,
    inferred_constraint JSONB,
    action            TEXT NOT NULL,
    retrieved_ids     TEXT[],
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Write these **outside** the transaction under test. A telemetry insert inside it
joins that transaction's read-write set and perturbs the contention you are
recording.

## Decision Guide

| Situation | Approach |
|---|---|
| Rule expressible over columns | Guarded `UPDATE`; skip this skill |
| Deterministic read-modify-write | Standard retry loop; the closure re-derives correctly |
| Model chooses the value, fast inference, low contention | Model call inside the retried transaction (step 3, first option) |
| Model chooses the value, slow inference or high contention | Read, decide outside, re-validate in a second short transaction (step 3, second option) |
| Constraint lives in retrieved documents | Refresh retrieval on retry as well (step 4) |
| Need confidence the retry re-decided | Assert reasoning calls per attempt (step 5) |

## Safety Considerations

- **Do not replay a decision derived from a read that `40001` invalidated.** The
  serialization failure is evidence that the state the decision rested on has
  changed. It is not evidence the decision was wrong, and it is not a reason to
  submit it again unchanged.
- **Do not hold a transaction open across a slow model call** without measuring
  the effect on contention. Use the two-transaction pattern in step 3 instead.
- **Do not run retrieval inside the transaction that performs the write.** It
  widens the refresh span and changes conflict behaviour.
- **Do not treat a schema `enum` as validation.** Check the returned action
  against the permitted set in application code.
- **Do not substitute a deterministic fallback for a malformed model response.**
  Fail loudly; a silent substitution is unattributable afterwards.
- **Bound retries and handle exhaustion explicitly.** An agent that never
  commits is a different failure from an agent that declines to act, and the two
  should be distinguishable in your telemetry.
- **`40003` is not retryable the same way.** An ambiguous commit may already have
  applied; do not blindly re-run non-idempotent work.
- Re-reading state protects constraints that live in the database. It does
  nothing for a constraint that changed in a document, and it cannot revoke a
  write that was already valid when it committed.

## References

- [designing-application-transactions](../designing-application-transactions/SKILL.md)
  — transaction scoping, retry loops with backoff, pushing invariants into SQL
- [benchmarking-transaction-patterns](../benchmarking-transaction-patterns/SKILL.md)
  — measuring contention across formulations
- [Transaction Retry Error Reference](https://www.cockroachlabs.com/docs/stable/transaction-retry-error-reference)
- [SERIALIZABLE and READ COMMITTED isolation](https://www.cockroachlabs.com/docs/stable/read-committed)
- [Vector indexes](https://www.cockroachlabs.com/docs/stable/vector-indexes)
- [CockroachDB and AI](https://www.cockroachlabs.com/docs/stable/cockroachdb-and-ai)
