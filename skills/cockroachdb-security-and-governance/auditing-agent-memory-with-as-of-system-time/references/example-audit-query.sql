-- Example "reconstruct the decision" query pattern for
-- auditing-agent-memory-with-as-of-system-time/SKILL.md.
-- Illustrative against the example schema from
-- designing-agentic-memory-schemas/references/example-migration.sql.

-- Given an audit_log entry_id for the decision being reviewed, and its
-- committed_at timestamp, reconstruct exactly which facts existed (and
-- their trust state) at that instant — not what those facts look like now.

-- Step 1: look up the decision's own audit row and timestamp. This read is
-- current-time; it is the anchor the historical read below is built from.
SELECT event_id, committed_at
FROM audit_log
WHERE shard_id = $1 AND seq = $2;

-- Step 2: historical read of the facts table AT that exact committed_at
-- timestamp. This is the query that actually answers "what did the system
-- believe when it acted" — everything below this line must carry the
-- resolved timestamp explicitly, never fall back to an implicit "now".
SELECT f.fact_id, f.fact_text, f.confidence, cluster_logical_timestamp() AS queried_as_of
FROM facts AS OF SYSTEM TIME '2026-06-01 14:32:00+00' f
JOIN provenance_edges AS OF SYSTEM TIME '2026-06-01 14:32:00+00' pe
  ON pe.fact_id = f.fact_id
WHERE f.tenant_id = $1
  AND pe.event_id = ANY($3); -- the recall_ids the decision actually cited

-- Step 3: if the query above raises a GC-threshold error, the decision
-- predates the retention window for this table. Surface that fact plainly
-- rather than falling back to a current-state read — see Step 2 and Step 3
-- of the parent SKILL.md.
