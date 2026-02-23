---
name: auditing-cloud-cluster-security
description: Audits the security posture of a CockroachDB Cloud cluster across network, authentication, authorization, encryption, audit logging, and backup dimensions using ccloud CLI and SQL. Use when assessing cluster security readiness, preparing for compliance reviews, or investigating security configuration gaps.
compatibility: Requires ccloud CLI authenticated via `ccloud auth login` and SQL access via cockroach sql with admin or VIEWACTIVITY privilege.
metadata:
  author: cockroachdb
  version: "1.0"
---

# Auditing Cloud Cluster Security

Assesses the security posture of a CockroachDB Cloud cluster by examining network access controls, authentication and SSO configuration, user authorization, encryption, audit logging, and backup status. Produces a structured PASS/WARN/FAIL report with remediation links for each finding.

**Read-only audit:** All operations are read-only. No cluster state is modified during the assessment.

## When to Use This Skill

- Preparing for SOC 2, HIPAA, or other compliance reviews
- Conducting periodic security posture assessments
- Onboarding a new production cluster and validating security baseline
- Investigating security configuration gaps after an incident
- Reviewing cluster security before a major release or customer onboarding

## Prerequisites

- **ccloud CLI** installed and authenticated (`ccloud auth login`)
- **cockroach sql** with a connection string to the target cluster
- **Privileges:** admin role or `VIEWACTIVITY` system privilege for full visibility
- **Cluster ID:** Available from `ccloud cluster list` or the Cloud Console URL

**Verify access:**
```bash
# Verify ccloud authentication
ccloud auth whoami

# Verify SQL access
cockroach sql --url "<connection-string>" -e "SELECT current_user();"
```

See [permissions reference](references/permissions.md) for detailed privilege requirements.

## Security Audit Dimensions

| Dimension | Tool | Checks |
|-----------|------|--------|
| Network Security | ccloud | IP allowlists, private endpoints |
| Authentication & SSO | ccloud + sql | Cloud Console SSO, Database SSO (Cluster SSO), SCIM 2.0 provisioning, auto user provisioning |
| Authorization | sql | Users, roles, admin grants, PUBLIC privileges |
| Encryption | ccloud + sql | CMEK status, TLS settings |
| Audit Logging | sql | Audit log config, session logging |
| Backup & Recovery | ccloud | Managed backup status (informational) |
| Cluster Configuration | ccloud | Version, plan, regions |

## Assessment Workflow

### Step 1: Authenticate and Gather Cluster Metadata

```bash
# List clusters and identify target
ccloud cluster list -o json

# Get cluster details (use cluster name or ID)
ccloud cluster info <cluster-name> -o json
```

Record: cluster ID, plan type (Basic/Standard/Advanced), cloud provider, regions, CockroachDB version.

See [ccloud commands reference](references/ccloud-commands.md) for full command syntax.

### Step 2: Assess Network Security

```bash
# List IP allowlist entries
ccloud cluster networking allowlist list <cluster-id> -o json

# Check for private endpoints (Advanced plan)
ccloud cluster networking private-endpoint-connection list <cluster-id> -o json
```

**Evaluate:**
- **FAIL** if `0.0.0.0/0` is in the allowlist (open to all traffic)
- **WARN** if allowlist contains broad CIDR ranges (e.g., `/8` or `/16`)
- **PASS** if allowlist contains only specific, narrow CIDR ranges or private endpoints are configured

### Step 3: Check SSO and SCIM Configuration

**Cloud Console SSO:**

Cloud Console SSO and SCIM are configured via the Cloud Console UI (Organization Settings > Authentication). The `ccloud` CLI does not currently expose SSO/SCIM configuration commands. Check the Cloud Console manually or ask the organization admin.

- **FAIL** if SSO is not configured for the organization
- **PASS** if SAML or OIDC SSO is enabled and enforced

**Database SSO (Cluster SSO):**
```sql
-- Check if Cluster SSO is enabled for SQL authentication
SHOW CLUSTER SETTING server.oidc_authentication.enabled;
SHOW CLUSTER SETTING server.oidc_authentication.provider_url;
```
- **FAIL** if `server.oidc_authentication.enabled` is `false`
- **PASS** if enabled with a valid provider URL

**SCIM 2.0 provisioning:**

SCIM 2.0 is configured via the Cloud Console UI (Organization Settings > Authentication > SCIM). Check the Cloud Console manually.

- **FAIL** if SCIM endpoint is not enabled
- **PASS** if SCIM is enabled and connected to an IdP

**Auto user provisioning on Database:**
```sql
-- Check if SQL users are automatically provisioned from SSO identities
SHOW CLUSTER SETTING server.identity_map.configuration;
```
- **FAIL** if identity mapping is not configured
- **PASS** if identity mapping routes IdP identities to SQL users

### Step 4: Audit Users and Roles

```sql
-- List all users and their roles
SELECT
  username,
  is_role,
  member_of
FROM [SHOW USERS]
ORDER BY username;
```

See [SQL queries reference](references/sql-queries.md) for additional role audit queries.

### Step 5: Check Privileges

```sql
-- Count admin role members
SELECT COUNT(*) AS admin_count
FROM [SHOW GRANTS ON ROLE admin];

-- Check PUBLIC role privileges on the current database
-- Note: SHOW GRANTS FOR public is scoped to the current database.
-- Run this query from each application database to get full coverage.
SELECT
  database_name,
  schema_name,
  object_name,
  object_type,
  privilege_type
FROM [SHOW GRANTS FOR public]
WHERE privilege_type NOT IN ('USAGE')
  AND schema_name = 'public'
ORDER BY database_name, object_name;
```

**Important:** `SHOW GRANTS FOR public` only returns grants for the current database context. To audit all databases, list databases first (`SHOW DATABASES;`) and repeat the PUBLIC grants query connected to each one.

**Evaluate:**
- **FAIL** if more than 5 users have admin role
- **FAIL** if PUBLIC has SELECT, INSERT, UPDATE, or DELETE on application tables
- **WARN** if admin count is between 3 and 5
- **PASS** if admin count is 1-2 and PUBLIC has minimal grants

### Step 6: Verify Encryption

**CMEK status:**
```bash
# Check CMEK configuration (Advanced plan with Advanced Security Add-on)
ccloud cluster info <cluster-name> -o json
# Look for cmek_config in the output
```

```sql
-- Verify encryption at rest via SQL
SHOW CLUSTER SETTING enterprise.encryption.type;
```

**Evaluate by plan type:**
- **Standard plan:** INFO — "Upgrade to Advanced plan with Advanced Security Add-on to enable CMEK"
- **Advanced plan without Advanced Security Add-on:** INFO — "Add Advanced Security Add-on to enable CMEK"
- **Advanced plan with Advanced Security Add-on, CMEK not enabled:** FAIL — CMEK not enabled despite plan supporting it
- **Advanced plan with Advanced Security Add-on, CMEK enabled:** PASS

**TLS:** CockroachDB Cloud enforces TLS on all connections by default — always PASS.

### Step 7: Check Audit Logging

```sql
-- Check audit log configuration
SHOW CLUSTER SETTING sql.log.user_audit;

-- Check admin audit logging
SHOW CLUSTER SETTING sql.log.admin_audit.enabled;
```

**Evaluate:**
- **FAIL** if `sql.log.user_audit` is empty and `sql.log.admin_audit.enabled` is `false`
- **WARN** if only admin audit is enabled but user audit is not configured
- **PASS** if both user and admin audit logging are configured

### Step 8: Report Backup Status (Informational)

```bash
# Check managed backup configuration
ccloud cluster info <cluster-name> -o json
# Look for backup_config in the output
```

**Evaluate:**
- **INFO** — CockroachDB Cloud automatically manages backups for all clusters. Report frequency and retention for awareness.

## Pass/Warn/Fail Criteria

| Check | PASS | WARN | FAIL |
|-------|------|------|------|
| IP Allowlist | Specific CIDRs only | Broad ranges (/8, /16) | `0.0.0.0/0` present |
| Cloud Console SSO | SSO enabled + enforced | SSO enabled, not enforced | Not configured |
| Database SSO | Cluster SSO enabled | — | Not configured |
| SCIM 2.0 | SCIM enabled + connected | — | Not enabled |
| DB Auto User Provisioning | Identity mapping configured | — | Not configured |
| Admin Users | 1-2 admins | 3-5 admins | 6+ admins |
| PUBLIC Privileges | No data grants | USAGE-only grants | SELECT/INSERT/UPDATE/DELETE |
| CMEK (Standard) | N/A | — | — (INFO: upgrade path) |
| CMEK (Advanced + Security Add-on) | CMEK enabled | — | Not enabled |
| Audit Logging | User + admin audit on | Admin audit only | Disabled |
| Password Policy | min length >= 12 | min length 8-11 | min length < 8 |
| Backups | N/A | — | — (INFO: managed) |

## Report Format

Save each audit report to the `reports/` directory (gitignored, local-only) with the naming convention:

```
reports/security-audit-<cluster-name>-<YYYY-MM-DD>-<sequence>.md
```

Example: `reports/security-audit-prod-east-2026-02-23-001.md`

The `reports/` directory is not committed to version control — it serves as a local log of audit runs for historical comparison and remediation tracking.

Generate a markdown report with the following structure:

```
# Security Audit Report — <Cluster Name>

**Date:** YYYY-MM-DD
**Cluster ID:** <cluster-id>
**Plan:** Standard | Advanced
**CockroachDB Version:** vXX.X.X
**Regions:** us-east-1, us-west-2

## Summary

| Status | Count |
|--------|-------|
| PASS   | X     |
| WARN   | X     |
| FAIL   | X     |
| INFO   | X     |

## Findings

### Network Security
- [PASS|WARN|FAIL] IP allowlist: <details>

### Authentication & SSO
- [PASS|FAIL] Cloud Console SSO: <details>
- [PASS|FAIL] Database SSO (Cluster SSO): <details>
- [PASS|FAIL] SCIM 2.0 provisioning: <details>
- [PASS|FAIL] Auto user provisioning: <details>

### Authorization
- [PASS|WARN|FAIL] Admin user count: X users with admin role
- [PASS|FAIL] PUBLIC role privileges: <details>

### Encryption
- [PASS|FAIL|INFO] CMEK: <details>
- [PASS] TLS: Enforced on all connections

### Audit Logging
- [PASS|WARN|FAIL] Audit log configuration: <details>

### Backup & Recovery
- [INFO] Managed backups: <frequency and retention>

### Cluster Configuration
- [INFO] Version: vXX.X.X
- [INFO] Plan: Standard | Advanced
- [INFO] Regions: <list>
```

## Remediation

For each finding, the corresponding remediation skill can be used independently:

| Finding | Remediation Skill |
|---------|------------------|
| Open IP allowlist | [configuring-ip-allowlists](../configuring-ip-allowlists/SKILL.md) |
| SSO not configured / SCIM not enabled | [configuring-sso-and-scim](../configuring-sso-and-scim/SKILL.md) |
| CMEK not enabled | [enabling-cmek-encryption](../enabling-cmek-encryption/SKILL.md) |
| Audit logging disabled | [configuring-audit-logging](../configuring-audit-logging/SKILL.md) |
| Excessive admin privileges | [hardening-user-privileges](../hardening-user-privileges/SKILL.md) |
| Weak password policy | [enforcing-password-policies](../enforcing-password-policies/SKILL.md) |
| TLS/certificate issues | [managing-tls-certificates](../managing-tls-certificates/SKILL.md) |
| No private connectivity | [configuring-private-connectivity](../configuring-private-connectivity/SKILL.md) |
| Log export not configured | [configuring-log-export](../configuring-log-export/SKILL.md) |
| Compliance gaps | [preparing-compliance-documentation](../preparing-compliance-documentation/SKILL.md) |

For each FAIL finding in the report, present two options:
- **"Explain how to fix this"** — Provide step-by-step guidance from the remediation skill
- **"Help me fix this now"** — Walk through the remediation interactively

**Example in audit report:**
```
[FAIL] IP allowlist includes 0.0.0.0/0 (open to all)
  -> Fix: See configuring-ip-allowlists skill
```

## Safety Considerations

- **All operations are read-only.** No cluster settings, users, roles, or network configurations are modified during the audit.
- **SQL queries use SHOW and SELECT only.** No DDL or DML statements are executed.
- **ccloud commands are read-only.** Only `list`, `info`, and `auth` subcommands are used.
- **No secrets are logged.** Connection strings and tokens are not included in the report output.
- **Privilege check:** The audit may produce incomplete results if the executing user lacks admin or VIEWACTIVITY privilege. The report notes any permission gaps.

## References

**Skill references:**
- [Sample audit report](references/sample-report.md) — Example report with findings and remediation links
- [SQL queries for security auditing](references/sql-queries.md)
- [ccloud CLI commands](references/ccloud-commands.md)
- [RBAC and privileges setup](references/permissions.md)

**Remediation skills:**
- [configuring-ip-allowlists](../configuring-ip-allowlists/SKILL.md) — Network access hardening
- [enabling-cmek-encryption](../enabling-cmek-encryption/SKILL.md) — Customer-managed encryption keys
- [configuring-audit-logging](../configuring-audit-logging/SKILL.md) — SQL audit logging
- [hardening-user-privileges](../hardening-user-privileges/SKILL.md) — RBAC tightening
- [enforcing-password-policies](../enforcing-password-policies/SKILL.md) — Password strength enforcement
- [configuring-sso-and-scim](../configuring-sso-and-scim/SKILL.md) — SSO and SCIM provisioning
- [managing-tls-certificates](../managing-tls-certificates/SKILL.md) — TLS certificate management
- [configuring-private-connectivity](../configuring-private-connectivity/SKILL.md) — Private endpoints and VPC peering
- [configuring-log-export](../configuring-log-export/SKILL.md) — Log and metric export
- [preparing-compliance-documentation](../preparing-compliance-documentation/SKILL.md) — Compliance readiness and documentation

**Official CockroachDB Documentation:**
- [CockroachDB Cloud Security Overview](https://www.cockroachlabs.com/docs/cockroachcloud/security-overview.html)
- [Managing IP Allowlists](https://www.cockroachlabs.com/docs/cockroachcloud/network-authorization.html)
- [Cloud Console SSO](https://www.cockroachlabs.com/docs/cockroachcloud/cloud-org-sso.html)
- [Cluster SSO (Database SSO)](https://www.cockroachlabs.com/docs/stable/sso-sql.html)
- [SCIM Provisioning](https://www.cockroachlabs.com/docs/cockroachcloud/configure-scim.html)
- [CMEK Overview](https://www.cockroachlabs.com/docs/cockroachcloud/cmek.html)
- [Audit Logging](https://www.cockroachlabs.com/docs/stable/sql-audit-logging.html)
- [Security Reference: Authorization](https://www.cockroachlabs.com/docs/stable/security-reference/authorization.html)
