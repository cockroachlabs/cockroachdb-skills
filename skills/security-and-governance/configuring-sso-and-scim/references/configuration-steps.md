# IdP Configuration Steps for SSO and SCIM

This reference provides IdP-specific configuration steps for setting up SSO and SCIM with CockroachDB Cloud.

## Cloud Console SSO — IdP Configuration

### Okta (SAML)

1. In Okta Admin, go to **Applications > Create App Integration**
2. Select **SAML 2.0**
3. Configure:
   - **Single sign-on URL:** `<CockroachDB Cloud ACS URL>` (from Cloud Console SSO settings)
   - **Audience URI (SP Entity ID):** `<CockroachDB Cloud Entity ID>` (from Cloud Console SSO settings)
   - **Name ID format:** Email Address
   - **Application username:** Okta username (email)
4. Map attributes:
   - `email` -> `user.email`
   - `firstName` -> `user.firstName`
   - `lastName` -> `user.lastName`
5. Assign users/groups to the application

### Okta (OIDC)

1. In Okta Admin, go to **Applications > Create App Integration**
2. Select **OIDC - OpenID Connect** and **Web Application**
3. Configure:
   - **Sign-in redirect URIs:** `<CockroachDB Cloud redirect URI>` (from Cloud Console SSO settings)
   - **Sign-out redirect URIs:** `<CockroachDB Cloud logout URI>`
4. Copy the **Client ID** and **Client Secret** to Cloud Console SSO settings
5. Set the discovery URL: `https://<your-okta-domain>/.well-known/openid-configuration`
6. Assign users/groups to the application

### Azure AD (OIDC)

1. In Azure Portal, go to **Azure Active Directory > App registrations > New registration**
2. Configure:
   - **Name:** CockroachDB Cloud SSO
   - **Redirect URI:** `<CockroachDB Cloud redirect URI>` (Web platform)
3. Under **Certificates & secrets**, create a new client secret
4. Copy **Application (client) ID** and **Client secret** to Cloud Console SSO settings
5. Set the discovery URL: `https://login.microsoftonline.com/<tenant-id>/v2.0/.well-known/openid-configuration`
6. Under **API permissions**, grant `openid`, `profile`, `email`

### Google Workspace (OIDC)

1. In Google Cloud Console, go to **APIs & Services > Credentials**
2. Create an **OAuth 2.0 Client ID** (Web application)
3. Configure:
   - **Authorized redirect URIs:** `<CockroachDB Cloud redirect URI>`
4. Copy **Client ID** and **Client Secret** to Cloud Console SSO settings
5. Set the discovery URL: `https://accounts.google.com/.well-known/openid-configuration`

## Database SSO (Cluster SSO) — IdP Configuration

### Okta

1. In Okta Admin, create a new **API Services** or **Web** application for database SSO
2. Configure:
   - **Grant type:** Authorization Code
   - **Redirect URI:** `http://localhost` (for cockroach sql CLI flow)
3. Under **Security > API > Authorization Servers**, note the issuer URL
4. Configure CockroachDB cluster settings:

```sql
SET CLUSTER SETTING server.oidc_authentication.provider_url = 'https://<your-okta-domain>/oauth2/default';
SET CLUSTER SETTING server.oidc_authentication.client_id = '<client-id>';
SET CLUSTER SETTING server.oidc_authentication.client_secret = '<client-secret>';
```

### Azure AD

1. In Azure Portal, create a new App registration for database SSO
2. Configure:
   - **Redirect URI:** `http://localhost` (Mobile and desktop applications)
3. Grant API permissions: `openid`, `profile`, `email`
4. Configure CockroachDB cluster settings:

```sql
SET CLUSTER SETTING server.oidc_authentication.provider_url = 'https://login.microsoftonline.com/<tenant-id>/v2.0';
SET CLUSTER SETTING server.oidc_authentication.client_id = '<client-id>';
SET CLUSTER SETTING server.oidc_authentication.client_secret = '<client-secret>';
```

## SCIM 2.0 — IdP Configuration

### Okta

1. In Okta Admin, go to the CockroachDB Cloud application
2. Navigate to **Provisioning > Configure API Integration**
3. Enable API integration
4. Enter:
   - **SCIM connector base URL:** `<SCIM base URL from Cloud Console>`
   - **Unique identifier field:** `email`
   - **Authentication mode:** HTTP Header
   - **Authorization:** Bearer `<SCIM token from Cloud Console>`
5. Under **Provisioning > To App**, enable:
   - Create Users
   - Update User Attributes
   - Deactivate Users
6. Under **Assignments**, assign users/groups

### Azure AD

1. In Azure Portal, go to the CockroachDB Cloud Enterprise Application
2. Navigate to **Provisioning > Get started**
3. Set **Provisioning Mode** to **Automatic**
4. Under **Admin Credentials**, enter:
   - **Tenant URL:** `<SCIM base URL from Cloud Console>`
   - **Secret Token:** `<SCIM token from Cloud Console>`
5. Click **Test Connection** to verify
6. Under **Mappings**, configure attribute mappings:
   - `userPrincipalName` -> `userName`
   - `mail` -> `emails[type eq "work"].value`
   - `displayName` -> `displayName`
7. Start provisioning

### Google Workspace

Google Workspace does not natively support SCIM for third-party apps. Options:
- Use a SCIM bridge (e.g., BetterCloud, Sailpoint)
- Use Google Cloud Identity with an OIDC/SCIM adapter
- Manage users manually or via API automation

## Identity Mapping Examples

### Map Email to SQL Username

```sql
-- Map user@example.com -> user (strip domain)
SET CLUSTER SETTING server.identity_map.configuration = '
crdb /^(.*)@example\.com$ \1
';
```

### Map with Domain Prefix

```sql
-- Map user@example.com -> example_user (prefix with domain)
SET CLUSTER SETTING server.identity_map.configuration = '
crdb /^(.*)@(.*)\.com$ \2_\1
';
```

### Multiple Domain Mapping

```sql
-- Map users from multiple domains
SET CLUSTER SETTING server.identity_map.configuration = '
crdb /^(.*)@engineering\.example\.com$ \1
crdb /^(.*)@ops\.example\.com$ ops_\1
';
```

## Notes

- All IdP URLs and credentials should be stored securely
- Test SSO and SCIM with a small group before rolling out organization-wide
- Keep documentation of IdP configuration for disaster recovery
- IdP-specific UI and steps may change — refer to your IdP's official documentation for the most current instructions
- CockroachDB Cloud SSO settings are available in the Cloud Console under Organization Settings > Authentication
