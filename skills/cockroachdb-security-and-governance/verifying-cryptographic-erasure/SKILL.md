---
name: verifying-cryptographic-erasure
description: Builds and verifies provable, statute-compliant crypto-erasure of personal data in CockroachDB by destroying a per-subject encryption key inside one SERIALIZABLE transaction that also retains a hash-chained, pseudonymized decision log. Use when a data subject invokes the right to erasure and you must prove the data is unrecoverable (not merely deleted) while retaining legally required audit logs, or when reconciling GDPR Article 17 erasure against retention duties like the EU AI Act Article 19 or MiFID II.
compatibility: Requires CockroachDB with SERIALIZABLE isolation (default). Row-level security steps require v25.2 or later.
metadata:
  author: erasure-proof contributors
  version: "1.0"
---

# Verifying Cryptographic Erasure

Implements and verifies the destroy-and-retain erasure pattern in CockroachDB: personal data is stored encrypted under a per-subject key, and erasure destroys that key inside one SERIALIZABLE transaction that also appends a pseudonymized, hash-chained decision-log entry. The result is data that is cryptographically unrecoverable (NIST SP 800-88 Rev. 2 cryptographic erase) while the legally required record of the erasure survives and is tamper-evident.

This solves a problem plain `DELETE` does not: deleting a row leaves recoverable copies in MVCC history, backups, and replica disks, and for AI systems a deleted embedding can be inverted back to the original text. Destroying the key makes every one of those copies unreadable at once.

## When to Use This Skill

- A data subject invokes the right to erasure and you must prove the data is genuinely unrecoverable, not just removed from the primary table
- You must erase personal data while a separate law (EU AI Act Article 19, MiFID II, DORA) requires you to retain a decision or audit log
- You are storing embeddings or other derived data that a plain delete would leave reconstructible
- A regulator or auditor asks you to demonstrate that a past erasure actually happened
- You are designing an agent-memory or multi-tenant store that needs per-subject erasability from day one

## Prerequisites

- **SQL access** with a role that can create tables and manage grants (setup), plus a dedicated low-privilege application role and an operator role for the erasure path
- **An external key manager** (for example AWS KMS, GCP KMS, or HashiCorp Vault) to wrap the per-subject key, so the plaintext key is never persisted
- **The forward-secrecy condition**, which the whole guarantee rests on: the plaintext key was never persisted and no wrapped key or key material was backed up, escrowed, or left in a KMS recovery window. Crypto-erasure protects the stored copy, not copies an attacker already exfiltrated.

## Data Model

Three tables carry the pattern. Encrypt content and any derived vectors with a per-subject data key; store only the KMS-wrapped key.

```sql
-- The encrypted memory. The embedding is stored ONLY as ciphertext for durability; a nullable
-- plaintext copy may exist for live vector search and is set NULL on erasure.
CREATE TABLE agent_memory (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id            UUID NOT NULL,
    content_ciphertext    BYTES NOT NULL,
    embedding             VECTOR(768),          -- nullable live copy; erasure sets NULL
    embedding_ciphertext  BYTES NOT NULL,
    wrapped_key           BYTES NOT NULL,       -- per-row key wrapped under the subject key
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The per-subject key, wrapped by the KMS, stored exactly once. Erasure deletes this row.
CREATE TABLE subject_keys (
    subject_id   UUID PRIMARY KEY,
    wrapped_key  BYTES NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The append-only, hash-chained decision log retained for compliance. subject_hash is a
-- pseudonym, never raw PII. seq is assigned prev + 1 inside the SERIALIZABLE transaction.
CREATE TABLE decision_log (
    seq           INT8 PRIMARY KEY,
    subject_hash  BYTES NOT NULL,       -- SHA-256(subject_id)
    action        STRING NOT NULL,      -- 'ingest' | 'erasure'
    lawful_basis  STRING NOT NULL,      -- e.g. 'gdpr_art_17'
    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    prev_hash     BYTES NOT NULL,       -- previous row's hash (genesis = 32 zero bytes)
    hash          BYTES NOT NULL        -- SHA-256(prev_hash || canonical_row_bytes)
);
CREATE INDEX decision_log_by_subject ON decision_log (subject_hash);
```

## Steps

### 1. Configure least-privilege roles

The agent role writes and reads memory and appends to the log, but can never touch keys or rewrite history. The operator role runs erasures.

```sql
CREATE ROLE agent_worker WITH LOGIN;
CREATE ROLE operator WITH LOGIN;

-- agent_worker: no access to subject_keys at all.
GRANT INSERT, SELECT ON agent_memory TO agent_worker;
GRANT INSERT, SELECT ON decision_log TO agent_worker;
REVOKE UPDATE, DELETE ON decision_log FROM agent_worker;  -- append-only to the agent

-- operator: runs the erasure. UPDATE on subject_keys is required for the locking read in step 3.
GRANT INSERT, SELECT, UPDATE, DELETE ON subject_keys TO operator;
GRANT INSERT, SELECT, UPDATE ON agent_memory TO operator;
GRANT INSERT, SELECT ON decision_log TO operator;
REVOKE UPDATE, DELETE ON decision_log FROM operator;      -- operator cannot rewrite history either
```

**Honest boundary:** append-only holds against `agent_worker` and `operator`, not against the table owner or an admin role, because CockroachDB privileges derive from ownership. State this; do not claim the table is immutable to everyone. Have a locked-down role own these tables and never log in as it.

### 2. Optionally scope the agent to one subject with row-level security

Defense in depth: a prompt-injected or buggy agent cannot read or write another subject's memory even with table-wide grants. Fail-closed when the session declares no subject.

```sql
ALTER TABLE agent_memory ENABLE ROW LEVEL SECURITY;

CREATE POLICY agent_subject_scope ON agent_memory
    FOR ALL TO agent_worker
    USING (subject_id = current_setting('app.subject_id', true)::UUID)
    WITH CHECK (subject_id = current_setting('app.subject_id', true)::UUID);

-- The operator (erasure is cross-subject) and any read-only auditor keep unrestricted policies.
CREATE POLICY operator_all ON agent_memory FOR ALL TO operator USING (true) WITH CHECK (true);
```

The application sets `SET app.subject_id = '<uuid>'` per session. `current_setting(..., true)` returns NULL when unset, so an undeclared session matches no rows.

### 3. Run the erasure in ONE serializable transaction

This is the core. Everything commits together or nothing does, so the key destruction and the retained log entry can never diverge. No network call (to a KMS or elsewhere) belongs inside this transaction, so a serialization retry is always safe.

```sql
BEGIN;

-- a. Lock the subject's key row. In CockroachDB, SELECT ... FOR UPDATE requires the UPDATE
--    privilege on the table, which is why the operator role is granted UPDATE on subject_keys
--    even though it only ever deletes the row. The lock orders this erasure against concurrent
--    writes for the same subject.
SELECT wrapped_key FROM subject_keys WHERE subject_id = $1 FOR UPDATE;

-- b. Read the current chain head (empty result = genesis).
SELECT seq, hash FROM decision_log ORDER BY seq DESC LIMIT 1;

-- c. Append the hash-chained decision-log row. seq = prev.seq + 1; the app computes
--    hash = SHA-256(prev_hash || "seq|action|lawful_basis" || SHA-256(subject_id)).
INSERT INTO decision_log (seq, subject_hash, action, lawful_basis, prev_hash, hash)
VALUES ($2, $3, 'erasure', $4, $5, $6);

-- d. The crypto-shred: delete the only wrapped copy of the subject key.
DELETE FROM subject_keys WHERE subject_id = $1;

-- e. Purge the live plaintext vector; the durable ciphertext stays as unreadable noise.
UPDATE agent_memory SET embedding = NULL WHERE subject_id = $1;

COMMIT;
```

**Wrap this in a retry loop.** Under SERIALIZABLE, concurrent erasures that compute the same `seq` conflict on the `decision_log` primary key and surface as a retryable serialization error (SQLSTATE `40001`), which is exactly how a gapless chain stays correct. Retry the whole transaction with exponential backoff and jitter; the official drivers provide a helper (for example `crdbpgx.ExecuteTx` in Go). Never write a SERIALIZABLE transaction without a retry path.

### 4. Verify the erasure

```sql
-- The key row is gone: without it the wrapped per-row keys can never be unwrapped.
SELECT count(*) AS keys_remaining FROM subject_keys WHERE subject_id = $1;   -- expect 0

-- The live vector is purged; only the durable ciphertext remains.
SELECT count(*) AS live_vectors FROM agent_memory
WHERE subject_id = $1 AND embedding IS NOT NULL;                             -- expect 0

-- The erasure was logged with its lawful basis.
SELECT seq, action, lawful_basis, occurred_at FROM decision_log
WHERE subject_hash = digest($2, 'sha256') AND action = 'erasure';
```

To prove tamper-evidence, recompute the hash chain from genesis and confirm each stored `hash` matches `SHA-256(prev_hash || canonical_row_bytes)`; a mismatch localizes the tampered `seq`. Keep the canonical byte encoding identical across every language that computes or verifies it. See [chain verification](references/sql-queries.md) for the recomputation query.

### 5. Confirm the append-only property holds

```sql
-- As agent_worker, both of these must fail with a permission error (SQLSTATE 42501).
UPDATE decision_log SET action = 'tamper' WHERE seq = 1;
DELETE FROM decision_log WHERE seq = 1;
```

## Safety Considerations

- **Erasure is irreversible by design.** Once the key row is deleted and the KMS material is gone, the ciphertext is permanently unreadable. Confirm you are erasing the correct `subject_id` before committing; there is no rollback of the data.
- **Never persist the plaintext key**, never log a key or a nonce, and never reuse a (key, nonce) pair. The forward-secrecy condition in Prerequisites is the guarantee; a single backed-up wrapped key defeats it.
- **Watch the GC window.** The nulled plaintext vector remains in MVCC history until `gc.ttlseconds` elapses (fixed at 4500s on CockroachDB Cloud Basic). Durable copies are ciphertext, but state the window honestly rather than implying instant physical removal.
- **Do not put a KMS or network call inside the transaction.** Destroy imported key material in the KMS after the transaction commits (as a second, immediate kill switch), never inside the retried closure.
- **Test the retry path** with `SET inject_retry_errors_enabled = true` so the transaction is exercised under forced 40001 errors.

## Rollback

There is no rollback of an erased subject's data; that is the point. What is recoverable and testable:

- If the post-commit KMS destruction fails, the primary erasure (key row deleted) already succeeded; re-run only the KMS destruction, do not re-run the transaction.
- To undo the SCHEMA (roles, policies) during setup, drop the policies and roles; this does not affect already-erased data.

```sql
-- Remove RLS during development
ALTER TABLE agent_memory DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS agent_subject_scope ON agent_memory;
```

## References

**Skill references:**
- [SQL queries for erasure and chain verification](references/sql-queries.md)

**Related skills:**
- [hardening-user-privileges](../hardening-user-privileges/SKILL.md): least-privilege RBAC that this pattern depends on
- [preparing-compliance-documentation](../preparing-compliance-documentation/SKILL.md): assembling the audit evidence for a regulator

**Official CockroachDB Documentation:**
- [Transactions and SERIALIZABLE isolation](https://www.cockroachlabs.com/docs/stable/transactions.html)
- [Client-side transaction retries (40001)](https://www.cockroachlabs.com/docs/stable/transaction-retry-error-reference.html)
- [SELECT FOR UPDATE](https://www.cockroachlabs.com/docs/stable/select-for-update.html)
- [Row-Level Security](https://www.cockroachlabs.com/docs/stable/row-level-security.html)
- [GRANT](https://www.cockroachlabs.com/docs/stable/grant.html) and [REVOKE](https://www.cockroachlabs.com/docs/stable/revoke.html)
- [Vector indexing (C-SPANN)](https://www.cockroachlabs.com/docs/stable/vector-indexes.html)

**Standards:**
- NIST SP 800-88 Rev. 2, Media Sanitization (cryptographic erase / Purge)
