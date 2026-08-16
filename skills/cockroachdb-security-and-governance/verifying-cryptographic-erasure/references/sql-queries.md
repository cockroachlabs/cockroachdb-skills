# SQL Queries for Cryptographic Erasure and Chain Verification

Reference queries for the destroy-and-retain erasure pattern. Placeholders: `$1` subject id,
`$2` decision-log seq, and so on. Adapt identifiers to your schema.

## Provisioning a subject

Store the KMS-wrapped per-subject key exactly once, and encrypt content and derived vectors under a
fresh per-row key wrapped beneath it (a two-level envelope). The plaintext keys never touch the
database.

```sql
INSERT INTO subject_keys (subject_id, wrapped_key) VALUES ($1, $2);

INSERT INTO agent_memory (subject_id, content_ciphertext, embedding, embedding_ciphertext, wrapped_key)
VALUES ($1, $3, $4, $5, $6);
```

## The erasure transaction (full)

```sql
BEGIN;
SELECT wrapped_key FROM subject_keys WHERE subject_id = $1 FOR UPDATE;
SELECT seq, hash FROM decision_log ORDER BY seq DESC LIMIT 1;
INSERT INTO decision_log (seq, subject_hash, action, lawful_basis, prev_hash, hash)
VALUES ($2, $3, 'erasure', $4, $5, $6);
DELETE FROM subject_keys WHERE subject_id = $1;
UPDATE agent_memory SET embedding = NULL WHERE subject_id = $1;
COMMIT;
```

## Verification

```sql
-- Key destroyed
SELECT count(*) = 0 AS key_destroyed FROM subject_keys WHERE subject_id = $1;

-- Live vector purged, durable ciphertext retained
SELECT
  count(*) FILTER (WHERE embedding IS NOT NULL) AS live_vectors,
  count(*)                                       AS rows_retained
FROM agent_memory WHERE subject_id = $1;

-- Erasure recorded with its lawful basis
SELECT seq, action, lawful_basis, occurred_at
FROM decision_log
WHERE subject_hash = digest($7, 'sha256')   -- $7 = subject_id text
ORDER BY seq;
```

## Hash-chain recomputation

Fetch the raw fields in seq order and recompute in application code, comparing each stored `hash`
against `SHA-256(prev_hash || canonical_row_bytes)` where the canonical row bytes are, byte for
byte, the same encoding used when the row was written. The first mismatch localizes the tampering.

```sql
SELECT seq, subject_hash, action, lawful_basis, prev_hash, hash
FROM decision_log
ORDER BY seq;
```

Reference recomputation (pseudocode):

```
prev = 32 zero bytes
for row in rows_ordered_by_seq:
    canonical = utf8("{seq}|{action}|{lawful_basis}") || row.subject_hash
    expected  = sha256(prev || canonical)
    assert expected == row.hash          # else: tamper at row.seq
    prev = row.hash
```

## Append-only enforcement (run as the agent role; both must be denied)

```sql
UPDATE decision_log SET action = 'tamper' WHERE seq = 1;   -- expect SQLSTATE 42501
DELETE FROM decision_log WHERE seq = 1;                    -- expect SQLSTATE 42501
```

## Row-level security matrix (run as the agent role)

```sql
-- No subject declared: fail-closed, zero rows
SELECT count(*) FROM agent_memory;                                    -- expect 0

-- Scoped to a subject: only that subject's rows
SET app.subject_id = '11111111-1111-4111-8111-111111111111';
SELECT count(*) FROM agent_memory;                                    -- expect that subject's count

-- Writing for another subject: denied by the WITH CHECK clause
INSERT INTO agent_memory (subject_id, content_ciphertext, embedding_ciphertext, wrapped_key)
VALUES ('22222222-2222-4222-8222-222222222222', x'01', x'02', x'03'); -- expect SQLSTATE 42501
```

## Exercising the retry path deterministically

```sql
SET inject_retry_errors_enabled = true;   -- every statement injects a retryable 40001 error
-- run the erasure transaction; the driver's retry wrapper must re-run the whole closure and commit
SET inject_retry_errors_enabled = false;
```
