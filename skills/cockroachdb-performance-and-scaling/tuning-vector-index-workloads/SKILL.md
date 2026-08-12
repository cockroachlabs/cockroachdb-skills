---
name: tuning-vector-index-workloads
description: "Diagnose and fix vector-index performance and correctness problems in CockroachDB: filtered ANN queries that silently stop using the index, slow bulk loads of embeddings, and sizing Request Unit cost on Basic clusters. Use when a query with CREATE VECTOR INDEX is slower than expected, when EXPLAIN does not show a vector search node, when loading embeddings at scale, or when a covering index appears in an index recommendation for a table that has a vector index."
compatibility: Requires CockroachDB v25.4+ (vector indexing GA; feature.vector_index.enabled defaults to true). Works on Basic, Standard, Advanced and Self-Hosted. Needs a SQL connection with SELECT on the target table; the bulk-load section additionally needs privileges to DROP and CREATE INDEX.
metadata:
  author: cockroachdb
  version: "1.0"
---

## Tuning vector index workloads

Vector indexes fail differently from ordinary indexes. An ordinary index that is not used makes a
query slow. **A vector index that is not used still returns correct rows** — CockroachDB falls back
to an exact scan and sort — so the query gets slower and less scalable while every result stays
right. Nothing errors, and no index recommendation tells you a vector index went unused.

Every check below therefore starts from `EXPLAIN`, not from timings.

## How to apply this skill

### 1. Establish the baseline: is the vector index actually being used?

```sql
EXPLAIN
SELECT id, body
FROM items
WHERE tenant_id = '00000000-0000-0000-0000-000000000000'   -- a LITERAL, see step 3
  AND status = 'active'
ORDER BY embedding <=> '[0.1, ...]'
LIMIT 5;
```

A healthy plan contains a **`• vector search`** node naming the index, and — when the index has
prefix columns — a **`prefix spans:`** line:

```
• vector search
    table: items@items_vec
    target count: 5
    prefix spans: [/'0000…'/'active' - /'0000…'/'active']
```

An unhealthy plan shows `• scan` (or `• index join` over some other index) followed by a sort. If
you see that, the query is doing exact k-NN over the filtered set. Correct, but not what the index
was created for.

**Make this an assertion, not a habit.** Re-run it after every migration. The plan can regress from
a schema change that never touched the vector index — see step 2.

### 2. Check whether another index has out-competed the vector index

This is the most common cause, and it is counter-intuitive because **the optimizer will recommend
the index that causes it.** For a table with a vector index and a filtered ANN query, `EXPLAIN`
frequently emits:

```
index recommendations: 1
1. type: index creation
   SQL command: CREATE INDEX ON items (tenant_id, status) STORING (body, embedding);
```

Follow that advice and the covering index exactly matches the query's filter, so the optimizer
prefers scanning it — and the ANN path stops running entirely. The recommendation is sound in
isolation (it removes a lookup join back to the primary key) and wrong in context.

Confirm the diagnosis by hiding the suspect index and re-running `EXPLAIN`:

```sql
ALTER INDEX items@items_cover NOT VISIBLE;
-- re-run the EXPLAIN from step 1; if `• vector search` returns, this was the cause
```

Then decide:

- **Drop the covering index** if the ANN path is the important one. This is usually the answer.
- **Keep it `NOT VISIBLE`** if some other query needs it, and make that query use it explicitly.

Do not resolve this by hinting the vector index in the ANN query and leaving the covering index
visible — the next person to read the plan will not know why the hint is there.

### 3. Check that prefix-column values are literals or placeholders

Prefix columns only prune when the optimizer can see a constant. A correlated subquery defeats them
completely:

```sql
-- NO prefix spans: produces lookup joins
WHERE tenant_id = (SELECT tenant_id FROM tenant WHERE slug = 'demo')

-- prefix spans present
WHERE tenant_id = $1     -- resolved in application code, bound as a parameter
```

Also note prefix columns match on `=` and `IN` only. A range predicate on a prefix column
(`created_at >= $2`) silently drops the acceleration. Move range filters out of the prefix.

### 4. Check that the opclass matches the distance operator

One index accelerates one metric.

| Opclass | Operator |
|---|---|
| `vector_l2_ops` (default) | `<->` |
| `vector_cosine_ops` | `<=>` |
| `vector_ip_ops` | `<#>` |

An index built with the default `vector_l2_ops` will **not** accelerate a `<=>` cosine query — the
usual RAG case. There is no warning; you get a full scan.

If your embeddings are unit-normalised, L2 ordering and cosine ordering are identical
(`‖a−b‖² = 2 − 2·cos(a,b)`), so either opclass ranks the same — but you must still query with the
operator the index was built for.

### 5. Tune the search, not the build

- `SET vector_search_beam_size = 16;` — the accuracy/latency knob. Raise it for recall, lower it for
  latency. Session-scoped, so it is safe to experiment with.
- `build_beam_size` (a storage parameter) is **not** the knob to reach for; the docs advise against
  changing it and it only affects index construction.

### 6. Bulk loading embeddings: drop the index, load, rebuild

Incremental index maintenance dominates a bulk load, and concurrency makes it worse rather than
better when rows share an index prefix — all the vectors land in the same partition tree, writers
contend for the same partitions, and partition splits rewrite entries other writers are touching.

The symptom is throughput that **decays as the table grows**, which distinguishes it from a client
or network bottleneck.

Diagnose it by asking the cluster rather than guessing:

```sql
SELECT substring(query, 1, 90), count(*), max(now() - start)
FROM [SHOW QUERIES]
WHERE application_name = 'your-loader'
GROUP BY 1 ORDER BY 2 DESC;
```

If every worker is parked on the same `INSERT`, the bottleneck is index maintenance, not your code.

The fix is the pattern the documentation already prescribes for bulk work — and it is the same
reason `IMPORT INTO` is unsupported on a table carrying a vector index:

```sql
DROP INDEX items@items_vec;
-- load all rows (row at a time; batching vector inserts is documented as harmful)
CREATE VECTOR INDEX items_vec ON items (tenant_id, status, embedding vector_cosine_ops);
-- then re-run the step 1 EXPLAIN assertion
```

Note the index build is an asynchronous schema-change job. `SHOW INDEXES` will not list the index
until the backfill finishes, and a client that times out has not cancelled it:

```sql
SELECT status, fraction_completed, description FROM [SHOW JOBS]
WHERE description ILIKE '%CREATE VECTOR INDEX%' ORDER BY created DESC LIMIT 1;
```

### 7. Sizing Request Unit cost on Basic

The documented ~10–25 RU band is for an **ordinary** insert. A vector insert additionally performs a
partition search and can trigger splits, so measure rather than assume.

On Basic, `crdb_internal.tenant_usage_details` **returns zero rows** and reading it at all requires
`SET allow_unsafe_internals = true`. The usable meter is the billing API:

```bash
ccloud billing invoice list -o json   # look for quantity_unit == "REQUEST_UNITS"
```

Read the meter, insert a known number of rows one statement at a time, wait for the meter to settle
(it lags by roughly a minute), and divide. Size the real load from that number.

## When NOT to use this skill

- The table has no vector index — use `cockroachdb-sql` for general query tuning.
- The problem is recall quality rather than plan choice (wrong results, not slow results). That is an
  embedding or chunking issue, not an index one.
- You are choosing whether to add a vector index at all — see the vector index documentation.

## References

- [Vector indexes](https://www.cockroachlabs.com/docs/stable/vector-indexes)
- [VECTOR data type](https://www.cockroachlabs.com/docs/stable/vector)
- [`CREATE VECTOR INDEX`](https://www.cockroachlabs.com/docs/stable/create-index)
- [`EXPLAIN`](https://www.cockroachlabs.com/docs/stable/explain)
