# Zendesk Security Ticket Analysis — Skill Priority Ranking

## Context

Analyzed 22,489 Zendesk support tickets from `DATAMART_PROD.ZENDESK.DIM_TICKETS` in Snowflake, spanning 2016–2026. Searched SUBJECT and DESCRIPTION fields for security-related keywords across 11 categories. Goal: identify which security areas generate the most customer support volume, map them to existing skills, and rank gaps for new skill development.

## Data Source

- **Table:** `DATAMART_PROD.ZENDESK.DIM_TICKETS`
- **Total tickets:** 22,489
- **Date range:** 2016-08-09 to 2026-02-20
- **Method:** Keyword matching on SUBJECT and DESCRIPTION fields, with CASE-based categorization. Counts are approximate (tickets can match multiple categories; the CASE statement assigns each ticket to its first match).

## Ranked Security Categories (by ticket volume)

| Rank | Category | Tickets | Existing Skill | Status |
|------|----------|---------|----------------|--------|
| 1 | TLS / SSL / Certificates | ~1,009 | **None** | **GAP** |
| 2 | SSO / Identity Provider | ~629 | `configuring-sso-and-scim` | Covered |
| 3 | Authorization / RBAC / Privileges | ~562 | `hardening-user-privileges` | Covered |
| 4 | Password / Authentication | ~440 | `enforcing-password-policies` | Partial |
| 5 | Authentication (General) | ~256 | Overlap with SSO + Password | Partial |
| 6 | Encryption / CMEK | ~251 | `enabling-cmek-encryption` | Covered |
| 7 | Private Endpoints / PrivateLink | ~236 | **None** | **GAP** |
| 8 | Security (General) | ~160 | `auditing-cloud-cluster-security` | Covered |
| 9 | Compliance (SOC 2, PCI, HIPAA, GDPR) | ~100 | **None** | **GAP** |
| 10 | IP Allowlist | ~83 | `configuring-ip-allowlists` | Covered |
| 11 | VPC Peering | ~73 | **None** | **GAP** |
| 12 | Log Export (CloudWatch, Datadog) | ~68 | **None** | **GAP** |
| 13 | Audit Logging (SQL) | ~32 | `configuring-audit-logging` | Covered |
| 14 | Certificate Lifecycle (Rotation/Renewal) | ~26 | **None** | **GAP** (subset of #1) |
| 15 | SCIM / User Provisioning | ~16 | `configuring-sso-and-scim` | Covered |

## Priority Ranking for New Skills

| Priority | Proposed Skill | Ticket Volume | Rationale |
|----------|---------------|---------------|-----------|
| **P0** | `managing-tls-certificates` | ~1,009 | Highest volume security gap. Covers TLS connection troubleshooting, client cert auth, CA management, cert rotation. |
| **P1** | `configuring-private-connectivity` | ~309 | Combines Private Endpoints (236) + VPC Peering (73). High-value Cloud-only skill. |
| **P2** | `configuring-log-export` | ~68 | Cloud-only. CloudWatch, Datadog, GCP Cloud Logging integration. |
| **P3** | `preparing-compliance-documentation` | ~100 | SOC 2, PCI DSS, HIPAA, GDPR readiness. More of a checklist/guide than a configuration skill. |

## Existing Skills — Coverage Assessment

| Existing Skill | Tickets Covered | Coverage Quality |
|----------------|----------------|-----------------|
| `configuring-sso-and-scim` | ~645 (SSO + SCIM) | Good |
| `hardening-user-privileges` | ~562 | Good |
| `enforcing-password-policies` | ~137 (of 440) | Partial — policy settings only |
| `enabling-cmek-encryption` | ~251 | Good |
| `configuring-ip-allowlists` | ~83 | Good |
| `configuring-audit-logging` | ~32 | Good |
| `auditing-cloud-cluster-security` | N/A (meta-skill) | Good |

## Trending Analysis (subject-only, recent periods)

| Category | 2025-2026 | 2024 | 2023 | Trend |
|----------|-----------|------|------|-------|
| TLS/Certs | 37 | 36 | 42 | Stable |
| SSO | 27 | 30 | 33 | Stable |
| Authentication | 26 | 20 | 16 | **Rising** |
| Network | 20 | 17 | 18 | Stable |
| RBAC/Privileges | 17 | 14 | 40 | Declining |
| Encryption/CMEK | 10 | 20 | 19 | Declining |

*Analysis date: 2026-02-23*
