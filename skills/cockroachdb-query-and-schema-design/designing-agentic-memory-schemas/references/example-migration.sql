-- Example migration combining the five patterns from
-- designing-agentic-memory-schemas/SKILL.md into one runnable schema.
-- Illustrative, not production configuration — adjust TTL windows, shard
-- counts, and vector dimensions to your own workload before using this.

-- Step 1: idempotent event ingestion.
-- The primary key is the caller-supplied idempotency key, not a generated
-- id, so a redelivered write is a no-op rather than a duplicate row.
CREATE TABLE episodes (
  event_id         UUID NOT NULL DEFAULT gen_random_uuid(),
  idempotency_key  STRING NOT NULL,
  subject_key      STRING NOT NULL,
  content          STRING NOT NULL,
  occurred_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (subject_key, idempotency_key),
  UNIQUE INDEX (event_id)
);

-- Step 4: episodic decay. Raw episodes expire; the facts distilled from
-- them do not (facts table below has no TTL).
ALTER TABLE episodes SET (ttl_expire_after = '90 days');

-- Step 3: tenant-prefixed vector index. tenant_id leads both the primary
-- key and the vector index key, so isolation is a property of key
-- ordering, not just a WHERE clause.
CREATE TABLE facts (
  tenant_id    UUID NOT NULL,
  fact_id      UUID NOT NULL DEFAULT gen_random_uuid(),
  fact_text    STRING NOT NULL,
  confidence   FLOAT4 NOT NULL DEFAULT 0.0,
  embedding    VECTOR(1536),
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, fact_id),
  VECTOR INDEX (tenant_id ASC, embedding)
);

-- Step 2: provenance graph. Composite primary key doubles as the index a
-- cascade/blast-radius query walks; add the reverse index below if your
-- workload also needs "which facts cite this event" as a hot path.
CREATE TABLE provenance_edges (
  fact_id     UUID NOT NULL REFERENCES facts(fact_id),
  event_id    UUID NOT NULL REFERENCES episodes(event_id),
  session_id  UUID NOT NULL,
  source_category STRING NOT NULL,
  PRIMARY KEY (fact_id, event_id),
  INDEX (event_id)
);

-- Step 5: sharded, hash-chained audit log. shard_id is typically
-- hash(subject_key) % shard_count, computed by the application, so writes
-- to different subjects land on different chain-head rows and don't
-- serialize against each other.
CREATE TABLE audit_log (
  shard_id    INT4 NOT NULL,
  seq         INT8 NOT NULL,
  event_id    UUID NOT NULL,
  op          STRING NOT NULL,
  entry_hash  BYTES NOT NULL,
  prev_hash   BYTES NOT NULL,
  committed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (shard_id, seq)
);

-- Enforces that every episode insert carries a matching audit_log row in
-- the same transaction. Adapt the trigger body for your own table set;
-- the point is that this is a database-level refusal, not an
-- application-level convention.
CREATE FUNCTION require_audit_row() RETURNS TRIGGER AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM audit_log
    WHERE event_id = NEW.event_id AND op = 'episode_written'
  ) THEN
    RAISE EXCEPTION 'episode insert without a matching audit_log row is refused';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER episodes_require_audit
  AFTER INSERT ON episodes
  FOR EACH ROW
  EXECUTE FUNCTION require_audit_row();
