---
name: configuring-sso-and-scim
description: Configures SSO authentication and SCIM 2.0 provisioning for CockroachDB at both the Cloud Console and database levels. Covers Cloud Console SSO (SAML/OIDC), Database-Level SSO via OIDC (JWT) or LDAP/AD authentication, SCIM 2.0 automated user provisioning on Cloud Console, and auto user provisioning on the database. Use when enabling centralized identity management, setting up SSO for compliance, or automating user lifecycle management.
compatibility: Requires CockroachDB Cloud organization admin for Console SSO/SCIM. Requires cluster admin for Database SSO configuration. SCIM 2.0 requires Enterprise plan. LDAP/AD authentication is self-hosted only (not available on CockroachDB Cloud) and requires v24.3+ for AD group-to-role mapping.
metadata:
  author: cockroachdb
  version: "1.1"
---

# Configuring SSO and SCIM

Configures Single Sign-On (SSO) and SCIM 2.0 provisioning for CockroachDB at multiple levels: Cloud Console SSO for web UI access, Database-Level SSO for SQL authentication (via OIDC/JWT or LDAP/AD), SCIM 2.0 for automated user lifecycle management on Cloud Console, and auto user provisioning for database-level identity mapping.

## When to Use This Skill

- Enabling centralized identity management via an IdP (Okta, Azure AD, Google Workspace, etc.)
- Meeting compliance requirements for SSO-only authentication
- Automating user provisioning and deprovisioning to prevent orphaned accounts
- Setting up SSO for SQL authentication to eliminate database-level passwords
- Configuring LDAP/AD authentication for self-hosted clusters in on-prem or hybrid environments
- Responding to a security audit finding about missing SSO or SCIM configuration
- Onboarding to a zero-trust authentication model

## Prerequisites

- **Cloud Console role:** Organization Admin (for Console SSO and SCIM)
- **SQL access:** Cluster admin role (for Database SSO configuration)
- **Identity Provider (IdP):** Configured and operational — Okta, Azure AD, Google Workspace, PingOne, or other SAML/OIDC-compatible provider
- **ccloud CLI** authenticated (`ccloud auth login`) — for Cloud Console SSO/SCIM
- **SCIM:** Enterprise plan required for SCIM 2.0
- **LDAP/AD:** Self-hosted CockroachDB cluster required (LDAP is not available on CockroachDB Cloud); v24.3+ required for LDAP group-to-role mapping

**Verify access:**
```bash
ccloud auth whoami
```

## Configuration Decisions

Before proceeding, determine which components the user needs. Ask which of the following options apply to their environment, then follow only the relevant sections below.

**Decision 1 — Cloud Console SSO protocol:**
- **SAML:** Best for enterprise IdPs with existing SAML infrastructure (Okta, Azure AD, PingOne). Mature standard with broad IdP support.
- **OIDC:** Simpler setup, supports Google Workspace and modern IdPs natively. Lighter-weight protocol.

**Decision 2 — SCIM 2.0 provisioning:**
- **Enable:** Automates user lifecycle (create/update/deactivate) between IdP and Cloud Console. Requires Enterprise plan.
- **Skip:** Manage Cloud Console users manually. Appropriate if the organization is small or does not have an Enterprise plan.

**Decision 3 — Database-Level SSO method:**
- **OIDC (JWT-based):** Cloud-native approach using JWT tokens. Supports auto user provisioning. Works on both CockroachDB Cloud and self-hosted clusters.
- **LDAP/AD:** Direct directory authentication against Active Directory or OpenLDAP. Best for on-premises AD environments. Self-hosted only (not available on CockroachDB Cloud).

## Steps

### Part 1: Cloud Console SSO

Cloud Console SSO enables SAML or OIDC authentication for the CockroachDB Cloud web console, replacing password-based login.

#### 1.1 Check Current SSO Configuration

Check SSO status in the Cloud Console UI (Organization Settings > Authentication). The `ccloud` CLI does not currently expose SSO configuration commands.

#### 1.2a Configure SAML SSO

Follow this section if the user selected **SAML** in Decision 1.

1. Navigate to **Organization Settings > Authentication** in the Cloud Console
2. Select **SAML** as the SSO provider type
3. Configure the SAML connection:
   - Enter the IdP metadata URL or upload the metadata XML
   - Copy the CockroachDB Cloud **ACS URL** and **Entity ID** to your IdP
   - Map IdP attributes to CockroachDB Cloud user fields (email, name)
4. In your IdP, create a SAML 2.0 application:
   - Set the **Single sign-on URL** to the CockroachDB Cloud ACS URL
   - Set the **Audience URI (SP Entity ID)** to the CockroachDB Cloud Entity ID
   - Set **Name ID format** to Email Address
   - Map attributes: `email`, `firstName`, `lastName`
5. Assign users or groups to the SAML application in the IdP

See [configuration steps reference](references/configuration-steps.md) for IdP-specific SAML instructions (Okta, Azure AD).

#### 1.2b Configure OIDC SSO

Follow this section if the user selected **OIDC** in Decision 1.

1. Navigate to **Organization Settings > Authentication** in the Cloud Console
2. Select **OIDC** as the SSO provider type
3. Configure the OIDC connection:
   - Enter the OIDC discovery URL from your IdP (e.g., `https://accounts.google.com/.well-known/openid-configuration`)
   - Enter the **Client ID** and **Client Secret** from your IdP
   - Configure the redirect URI in the IdP to point to CockroachDB Cloud
4. In your IdP, create an OIDC/OAuth 2.0 application:
   - Set **Sign-in redirect URI** to the CockroachDB Cloud redirect URI
   - Grant scopes: `openid`, `profile`, `email`
5. Assign users or groups to the OIDC application in the IdP

See [configuration steps reference](references/configuration-steps.md) for IdP-specific OIDC instructions (Okta, Azure AD, Google Workspace).

#### 1.3 Test SSO Login

1. Open a new browser session (or incognito window)
2. Navigate to the CockroachDB Cloud Console login page
3. Select **Sign in with SSO**
4. Verify redirect to IdP, authenticate, and redirect back to Cloud Console

#### 1.4 Enforce SSO (Disable Password Login)

After verifying SSO works:

1. Navigate to **Organization Settings > Authentication**
2. Enable **Require SSO** to disable password-based login
3. Confirm a break-glass admin account exists (see Safety Considerations)

### Part 2: Database-Level SSO

Database-Level SSO enables SQL authentication via the IdP, replacing database-level passwords. Choose **Option A** (OIDC/JWT) or **Option B** (LDAP/AD) based on Decision 3.

#### Option A: OIDC (JWT-based SSO)

OIDC-based database SSO uses JWT tokens from an IdP for SQL authentication. Works on both CockroachDB Cloud and self-hosted clusters.

##### 2A.1 Check Current Cluster SSO Configuration

```sql
-- Check if OIDC authentication is enabled
SHOW CLUSTER SETTING server.oidc_authentication.enabled;

-- Check OIDC provider URL
SHOW CLUSTER SETTING server.oidc_authentication.provider_url;

-- Check client ID
SHOW CLUSTER SETTING server.oidc_authentication.client_id;
```

##### 2A.2 Configure Cluster SSO

```sql
-- Enable OIDC authentication for SQL
SET CLUSTER SETTING server.oidc_authentication.enabled = true;

-- Set the OIDC provider URL (your IdP's discovery endpoint)
SET CLUSTER SETTING server.oidc_authentication.provider_url = 'https://your-idp.example.com';

-- Set the client ID registered in your IdP
SET CLUSTER SETTING server.oidc_authentication.client_id = '<client-id>';

-- Set the client secret
SET CLUSTER SETTING server.oidc_authentication.client_secret = '<client-secret>';

-- Configure the claim field used for SQL username mapping
SET CLUSTER SETTING server.oidc_authentication.claim_json_key = 'email';

-- Configure the principal regex (extract username from claim)
SET CLUSTER SETTING server.oidc_authentication.principal_regex = '^([^@]+)';
```

##### 2A.3 Configure HBA for SSO Authentication

```sql
-- Add HBA rule to accept JWT authentication
-- This should be added before any password-based rules
SET CLUSTER SETTING server.host_based_authentication.configuration = '
host all all all jwt-token
host all all all password
';
```

##### 2A.4 Test Database SSO

```bash
# Authenticate via SSO and get a JWT token from your IdP
# Use the token to connect via cockroach sql
cockroach sql --url "postgresql://<username>:<jwt-token>@<cluster-host>:26257/defaultdb?sslmode=verify-full"
```

#### Option B: LDAP/AD Authentication

LDAP/AD-based database authentication validates SQL credentials directly against an LDAP directory (Active Directory or OpenLDAP). **Self-hosted only** — not available on CockroachDB Cloud.

##### 2B.1 Check Current HBA Configuration

```sql
-- Check current HBA rules
SHOW CLUSTER SETTING server.host_based_authentication.configuration;
```

##### 2B.2 Configure LDAP Authentication via HBA

LDAP authentication is configured through HBA (Host-Based Authentication) rules. The HBA rule specifies the LDAP server, search base, and attribute to match.

```sql
-- Configure HBA for LDAP authentication with a password fallback
SET CLUSTER SETTING server.host_based_authentication.configuration = '
host all all all ldap ldapserver=ldap.example.com ldapport=389 ldapbasedn="dc=example,dc=com" ldapsearchattribute=uid ldapbinddn="cn=readonly,dc=example,dc=com" ldapbindpasswd="<bind-password>"
host all all all password
';
```

Key LDAP HBA parameters:
- `ldapserver` — LDAP server hostname
- `ldapport` — LDAP server port (389 for LDAP, 636 for LDAPS)
- `ldapbasedn` — Base DN for user search
- `ldapsearchattribute` — Attribute matching the SQL username (e.g., `uid` for OpenLDAP, `sAMAccountName` for AD)
- `ldapbinddn` — DN of the service account used for LDAP bind/search
- `ldapbindpasswd` — Password for the bind DN service account

See [configuration steps reference](references/configuration-steps.md) for Active Directory, OpenLDAP, group mapping, and LDAPS examples.

##### 2B.3 Use LDAPS (TLS) for Production

For production environments, always use LDAPS (LDAP over TLS) to encrypt credentials in transit:

```sql
SET CLUSTER SETTING server.host_based_authentication.configuration = '
host all all all ldap ldapserver=ldap.example.com ldapport=636 ldaptls=1 ldapbasedn="dc=example,dc=com" ldapsearchattribute=uid ldapbinddn="cn=readonly,dc=example,dc=com" ldapbindpasswd="<bind-password>"
host all all all password
';
```

##### 2B.4 Configure LDAP Group-to-Role Mapping (v24.3+)

LDAP group mapping allows CockroachDB to assign SQL roles based on LDAP/AD group membership:

```sql
-- Enable LDAP authorization
SET CLUSTER SETTING server.ldap_authorization.enabled = true;

-- Configure the LDAP group lookup filter
SET CLUSTER SETTING server.ldap_authorization.group_list_filter = '(&(objectClass=group)(member={{.User.DN}}))';

-- Configure the group search base DN
SET CLUSTER SETTING server.ldap_authorization.group_search_base_dn = 'ou=Groups,dc=example,dc=com';

-- Configure the attribute containing the group name (mapped to SQL role)
SET CLUSTER SETTING server.ldap_authorization.group_search_attribute = 'cn';
```

##### 2B.5 Test LDAP Authentication

```bash
# Test with an LDAP user credential
cockroach sql --url "postgresql://<ldap-username>:<ldap-password>@<cluster-host>:26257/defaultdb?sslmode=verify-full"
```

```sql
-- Verify the user connected successfully
SELECT current_user();

-- If group mapping is enabled, verify role grants
SHOW GRANTS FOR <ldap-username>;
```

### Part 3: SCIM 2.0 on Cloud Console

> **Skip this section** if the user does not need automated user provisioning or does not have an Enterprise plan.

SCIM 2.0 enables automated user provisioning and deprovisioning on the Cloud Console, syncing user lifecycle with your IdP.

#### 3.1 Check Current SCIM Configuration

Check SCIM status in the Cloud Console UI (Organization Settings > Authentication > SCIM). The `ccloud` CLI does not currently expose SCIM configuration commands.

#### 3.2 Enable SCIM Endpoint

1. Navigate to **Organization Settings > Authentication > SCIM** in the Cloud Console
2. Enable the SCIM 2.0 endpoint
3. Copy the **SCIM base URL** and **Bearer token** for IdP configuration

#### 3.3 Configure IdP for SCIM

In your IdP (Okta, Azure AD, etc.):

1. Add a new SCIM provisioning integration
2. Enter the SCIM base URL from step 3.2
3. Enter the Bearer token for authentication
4. Configure provisioning actions:
   - **Create users** — New IdP users are created in CockroachDB Cloud
   - **Update user attributes** — Name and email changes sync
   - **Deactivate users** — Removed IdP users are deactivated in CockroachDB Cloud
5. Assign users or groups to the SCIM integration

See [configuration steps reference](references/configuration-steps.md) for IdP-specific SCIM setup.

#### 3.4 Verify SCIM Provisioning

1. Create a test user in your IdP and assign them to the SCIM integration
2. Check the Cloud Console — the user should appear within a few minutes
3. Remove the test user from the IdP SCIM assignment
4. Verify the user is deactivated in the Cloud Console

### Part 4: Auto User Provisioning on Database

Auto user provisioning creates SQL users automatically from IdP identities when they first connect via SSO. This applies to OIDC-based database SSO (Option A in Part 2).

#### 4.1 Check Current Identity Mapping

```sql
-- Check identity mapping configuration
SHOW CLUSTER SETTING server.identity_map.configuration;
```

#### 4.2 Configure Identity Mapping

```sql
-- Map IdP identities to SQL users
-- Format: <map-name> <system-identity-regex> <database-user>
SET CLUSTER SETTING server.identity_map.configuration = '
crdb /^(.*)@example\.com$ \1
';
```

This maps `user@example.com` from the IdP to SQL user `user`.

#### 4.3 Enable Auto User Creation

When combined with Cluster SSO (Part 2, Option A), users authenticated via SSO who do not yet have a SQL user account will be automatically created.

```sql
-- Verify HBA configuration includes identity mapping
SET CLUSTER SETTING server.host_based_authentication.configuration = '
host all all all jwt-token map=crdb
host all all all password
';
```

#### 4.4 Test Auto Provisioning

1. Authenticate a new IdP user via Cluster SSO
2. Verify the SQL user was created:
```sql
SELECT username FROM [SHOW USERS] WHERE username = '<expected-username>';
```

## Troubleshooting

### SSO Lockout Recovery

If SSO is enforced and the IdP becomes unavailable or misconfigured:

1. **Use the break-glass account:** Log in with the pre-configured password-based admin account
2. **Disable SSO enforcement:** Navigate to Organization Settings > Authentication and disable "Require SSO"
3. **If no break-glass account exists:** Contact CockroachDB Cloud support to disable SSO enforcement for your organization

**Prevention:** Always create and test a break-glass admin account before enforcing SSO.

### JWT Authentication Errors

**"ERROR: JWT authentication: invalid token"**
- Verify the OIDC provider URL is correct and accessible
- Check that the JWT token has not expired
- Verify the `claim_json_key` and `principal_regex` settings match your IdP's token format
- Inspect the token contents: `echo '<token>' | cut -d. -f2 | base64 -d | jq .`

**"ERROR: JWT authentication: issuer not configured"**
- The `server.oidc_authentication.provider_url` may have changed or been reset
- Re-apply the OIDC cluster settings (see Part 2, Option A above)

### OIDC Principal Regex Issues

**"OIDC: unable to match principal"**
- The `principal_regex` does not match the claim value from the token
- Test the regex against the actual claim value:

```sql
-- Check current regex
SHOW CLUSTER SETTING server.oidc_authentication.principal_regex;

-- Common patterns:
-- Email -> username (strip domain): '^([^@]+)'
-- Full email as username: '^(.+)$'
-- Domain prefix: '^([^@]+)@example\.com$'
```

**Complex regex not accepted:**
- CockroachDB uses Go's `regexp` syntax, which differs from PCRE
- Lookaheads and lookbehinds are not supported
- Test the regex at https://regex101.com/ with the "Golang" flavor

### LDAP Authentication Errors

**"ERROR: LDAP authentication: unable to bind"** — Verify the `ldapbinddn` and `ldapbindpasswd` are correct. Check that the bind service account has read access to the user search base. Test with: `ldapsearch -H ldap://ldap.example.com -D "cn=readonly,dc=example,dc=com" -W -b "dc=example,dc=com" "(uid=testuser)"`

**"ERROR: LDAP authentication: user not found"** — Verify `ldapbasedn` includes the OU where the user resides. Check that `ldapsearchattribute` matches the login attribute (`uid` for OpenLDAP, `sAMAccountName` for AD).

**LDAP server unreachable** — Verify network connectivity from CockroachDB nodes to the LDAP server. For LDAPS, ensure the TLS certificate is trusted. Check firewall rules for port 389 (LDAP) or 636 (LDAPS).

### Azure AD / Entra ID Specific Issues

**Token audience mismatch:**
- Azure AD tokens include an `aud` claim that must match the `client_id`
- Ensure the App Registration's Application ID URI matches if using a custom audience
- For standard setup, the `client_id` in CockroachDB settings should match the Azure AD Application (client) ID

**Multi-tenant vs single-tenant:**
- For single-tenant: use `https://login.microsoftonline.com/<tenant-id>/v2.0` as the provider URL
- For multi-tenant: use `https://login.microsoftonline.com/common/v2.0` (requires additional validation)

**Group claims for role mapping:**
- Azure AD can include group memberships in the JWT token
- Enable "Groups claim" in the App Registration > Token Configuration
- Map Azure AD groups to CockroachDB roles via identity mapping

### SSO + Roles Interaction

**"SSO User Roles: UI does not show roles inherited from user groups"**
- Cloud Console roles assigned via SCIM groups may not display in the individual user's role list
- Check the group assignments: the user's effective role is the union of direct and group-inherited roles
- Verify in SCIM logs that group membership changes are syncing correctly

## Safety Considerations

**SSO misconfiguration can lock out users.** If SSO is enforced and the IdP is down or misconfigured, no one can log in.

**Mitigation — Break-glass account:**
1. Before enforcing SSO, ensure at least one organization admin account uses password authentication
2. Document the break-glass account credentials in a secure vault (e.g., 1Password, HashiCorp Vault)
3. Test the break-glass account periodically to ensure it still works
4. For Database SSO, keep at least one SQL user with password authentication as a fallback

**SCIM risks:**
- **Mass deprovisioning:** If the IdP SCIM assignment is accidentally removed, all provisioned users may be deactivated. Start with a small group before enabling for the full organization.
- **Attribute mapping errors:** Incorrect attribute mapping can create users with wrong names or emails. Test with a single user first.

**Database SSO risks (OIDC):**
- **HBA misconfiguration:** Incorrect HBA rules can block all SQL authentication. Always keep a password-based fallback rule.
- **Identity mapping errors:** Incorrect regex can map users to wrong SQL accounts or fail to match. Test with known identities first.

**Database SSO risks (LDAP/AD):**
- **LDAP server unavailability blocks authentication:** If the LDAP server is down, users authenticating via LDAP cannot connect. Always keep a password-based fallback HBA rule after the LDAP rule.
- **Use a restricted service account for LDAP bind:** The `ldapbinddn` account should have minimal read-only permissions — only enough to search for user entries. Never use a domain admin account.
- **Credential exposure without LDAPS:** LDAP without TLS transmits passwords in cleartext. Always use LDAPS (`ldaptls=1`, port 636) in production.

## Rollback

### Disable Cloud Console SSO Enforcement

1. Log in with the break-glass admin account
2. Navigate to **Organization Settings > Authentication**
3. Disable **Require SSO** to re-enable password login
4. Users can now log in with passwords again

### Disable Database SSO (OIDC)

```sql
-- Disable OIDC authentication
SET CLUSTER SETTING server.oidc_authentication.enabled = false;

-- Restore password-only HBA configuration
SET CLUSTER SETTING server.host_based_authentication.configuration = '
host all all all password
';
```

### Disable Database SSO (LDAP/AD)

```sql
-- Revert HBA to password-only authentication
SET CLUSTER SETTING server.host_based_authentication.configuration = '
host all all all password
';

-- If LDAP group mapping was enabled, disable it
SET CLUSTER SETTING server.ldap_authorization.enabled = false;
```

### Disable SCIM

1. Navigate to **Organization Settings > Authentication > SCIM**
2. Disable the SCIM endpoint
3. Remove the SCIM integration from your IdP
4. Manually manage user provisioning/deprovisioning going forward

### Remove Identity Mapping

```sql
-- Clear identity mapping
SET CLUSTER SETTING server.identity_map.configuration = '';
```

## References

**Skill references:**
- [IdP configuration steps](references/configuration-steps.md)

**Related skills:**
- [auditing-cloud-cluster-security](../auditing-cloud-cluster-security/SKILL.md) — Run a full security posture audit
- [enforcing-password-policies](../enforcing-password-policies/SKILL.md) — Strengthen password policies as an alternative to SSO
- [managing-tls-certificates](../managing-tls-certificates/SKILL.md) — Certificate-based authentication as an alternative to SSO

**Official CockroachDB Documentation:**
- [Cloud Console SSO](https://www.cockroachlabs.com/docs/cockroachcloud/cloud-org-sso.html)
- [Cluster SSO (Database SSO)](https://www.cockroachlabs.com/docs/stable/sso-sql.html)
- [SCIM Provisioning](https://www.cockroachlabs.com/docs/cockroachcloud/configure-scim.html)
- [Cluster Settings](https://www.cockroachlabs.com/docs/stable/cluster-settings.html)
- [HBA Configuration](https://www.cockroachlabs.com/docs/stable/security-reference/authentication.html)
- [JWT Authentication](https://www.cockroachlabs.com/docs/stable/sso-sql.html)
- [LDAP Authorization](https://www.cockroachlabs.com/docs/stable/ldap-authorization)
- [Authentication Reference](https://www.cockroachlabs.com/docs/stable/security-reference/authentication)
