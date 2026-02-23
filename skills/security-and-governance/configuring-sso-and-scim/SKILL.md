---
name: configuring-sso-and-scim
description: Configures SSO authentication and SCIM 2.0 provisioning for CockroachDB Cloud at both the Cloud Console and database levels. Covers Cloud Console SSO (SAML/OIDC), Database/Cluster SSO for SQL authentication, SCIM 2.0 automated user provisioning on Cloud Console, and auto user provisioning on the database. Use when enabling centralized identity management, setting up SSO for compliance, or automating user lifecycle management.
compatibility: Requires CockroachDB Cloud organization admin for Console SSO/SCIM. Requires cluster admin for Database SSO configuration. SCIM 2.0 requires Enterprise plan.
metadata:
  author: cockroachdb
  version: "1.0"
---

# Configuring SSO and SCIM

Configures Single Sign-On (SSO) and SCIM 2.0 provisioning for CockroachDB Cloud at multiple levels: Cloud Console SSO for web UI access, Database SSO (Cluster SSO) for SQL authentication, SCIM 2.0 for automated user lifecycle management on Cloud Console, and auto user provisioning for database-level identity mapping.

## When to Use This Skill

- Enabling centralized identity management via an IdP (Okta, Azure AD, Google Workspace, etc.)
- Meeting compliance requirements for SSO-only authentication
- Automating user provisioning and deprovisioning to prevent orphaned accounts
- Setting up SSO for SQL authentication to eliminate database-level passwords
- Responding to a security audit finding about missing SSO or SCIM configuration
- Onboarding to a zero-trust authentication model

## Prerequisites

- **Cloud Console role:** Organization Admin (for Console SSO and SCIM)
- **SQL access:** Cluster admin role (for Database SSO configuration)
- **Identity Provider (IdP):** Configured and operational — Okta, Azure AD, Google Workspace, PingOne, or other SAML/OIDC-compatible provider
- **ccloud CLI** authenticated (`ccloud auth login`)
- **SCIM:** Enterprise plan required for SCIM 2.0

**Verify access:**
```bash
ccloud auth whoami
```

## Steps

### Part 1: Cloud Console SSO

Cloud Console SSO enables SAML or OIDC authentication for the CockroachDB Cloud web console, replacing password-based login.

#### 1.1 Check Current SSO Configuration

Check SSO status in the Cloud Console UI (Organization Settings > Authentication). The `ccloud` CLI does not currently expose SSO configuration commands.

#### 1.2 Configure SSO in Cloud Console

1. Navigate to **Organization Settings > Authentication** in the Cloud Console
2. Select SSO provider type: **SAML** or **OIDC**
3. Configure the IdP connection:

**For SAML:**
- Enter the IdP metadata URL or upload the metadata XML
- Copy the CockroachDB Cloud ACS URL and Entity ID to your IdP
- Map IdP attributes to CockroachDB Cloud user fields (email, name)

**For OIDC:**
- Enter the OIDC discovery URL (e.g., `https://accounts.google.com/.well-known/openid-configuration`)
- Enter the Client ID and Client Secret from your IdP
- Configure redirect URI in the IdP to point to CockroachDB Cloud

See [configuration steps reference](references/configuration-steps.md) for detailed IdP-specific instructions.

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

### Part 2: Database SSO (Cluster SSO)

Database SSO enables SQL authentication via the IdP, replacing database-level passwords with JWT/OIDC tokens.

#### 2.1 Check Current Cluster SSO Configuration

```sql
-- Check if OIDC authentication is enabled
SHOW CLUSTER SETTING server.oidc_authentication.enabled;

-- Check OIDC provider URL
SHOW CLUSTER SETTING server.oidc_authentication.provider_url;

-- Check client ID
SHOW CLUSTER SETTING server.oidc_authentication.client_id;
```

#### 2.2 Configure Cluster SSO

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

#### 2.3 Configure HBA for SSO Authentication

```sql
-- Add HBA rule to accept JWT authentication
-- This should be added before any password-based rules
SET CLUSTER SETTING server.host_based_authentication.configuration = '
host all all all jwt-token
host all all all password
';
```

#### 2.4 Test Database SSO

```bash
# Authenticate via SSO and get a JWT token from your IdP
# Use the token to connect via cockroach sql
cockroach sql --url "postgresql://<username>:<jwt-token>@<cluster-host>:26257/defaultdb?sslmode=verify-full"
```

### Part 3: SCIM 2.0 on Cloud Console

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

Auto user provisioning creates SQL users automatically from IdP identities when they first connect via SSO.

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

When combined with Cluster SSO (Part 2), users authenticated via SSO who do not yet have a SQL user account will be automatically created.

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

**Database SSO risks:**
- **HBA misconfiguration:** Incorrect HBA rules can block all SQL authentication. Always keep a password-based fallback rule.
- **Identity mapping errors:** Incorrect regex can map users to wrong SQL accounts or fail to match. Test with known identities first.

## Rollback

### Disable Cloud Console SSO Enforcement

1. Log in with the break-glass admin account
2. Navigate to **Organization Settings > Authentication**
3. Disable **Require SSO** to re-enable password login
4. Users can now log in with passwords again

### Disable Database SSO

```sql
-- Disable OIDC authentication
SET CLUSTER SETTING server.oidc_authentication.enabled = false;

-- Restore password-only HBA configuration
SET CLUSTER SETTING server.host_based_authentication.configuration = '
host all all all password
';
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

**Official CockroachDB Documentation:**
- [Cloud Console SSO](https://www.cockroachlabs.com/docs/cockroachcloud/cloud-org-sso.html)
- [Cluster SSO (Database SSO)](https://www.cockroachlabs.com/docs/stable/sso-sql.html)
- [SCIM Provisioning](https://www.cockroachlabs.com/docs/cockroachcloud/configure-scim.html)
- [Cluster Settings](https://www.cockroachlabs.com/docs/stable/cluster-settings.html)
- [HBA Configuration](https://www.cockroachlabs.com/docs/stable/security-reference/authentication.html)
