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

## Database SSO — LDAP/AD Configuration

### Active Directory Example

Active Directory uses `sAMAccountName` as the login attribute and organizes users in OUs.

```sql
-- Configure HBA for Active Directory authentication
SET CLUSTER SETTING server.host_based_authentication.configuration = '
host all all all ldap ldapserver=ad.corp.example.com ldapport=636 ldaptls=1 ldapbasedn="ou=Users,dc=corp,dc=example,dc=com" ldapsearchattribute=sAMAccountName ldapbinddn="cn=crdb-svc,ou=ServiceAccounts,dc=corp,dc=example,dc=com" ldapbindpasswd="<service-account-password>"
host all all all password
';
```

Notes:
- `sAMAccountName` maps the Windows login name (e.g., `jsmith`) to the SQL username
- The `ldapbinddn` service account needs only **Read** permissions on the user OU
- Use `ldaptls=1` with port 636 for LDAPS (required for production AD environments)

### OpenLDAP Example

OpenLDAP typically uses `uid` as the login attribute.

```sql
-- Configure HBA for OpenLDAP authentication
SET CLUSTER SETTING server.host_based_authentication.configuration = '
host all all all ldap ldapserver=ldap.example.com ldapport=636 ldaptls=1 ldapbasedn="ou=People,dc=example,dc=com" ldapsearchattribute=uid ldapbinddn="cn=readonly,dc=example,dc=com" ldapbindpasswd="<bind-password>"
host all all all password
';
```

### LDAP Group-to-Role Mapping

LDAP group mapping (v24.3+) assigns CockroachDB SQL roles based on LDAP/AD group membership. The LDAP group name (CN) is mapped directly to a SQL role name — the role must already exist in CockroachDB.

#### Active Directory Group Mapping

```sql
-- Enable LDAP authorization
SET CLUSTER SETTING server.ldap_authorization.enabled = true;

-- Search for groups where the user is a member
-- AD uses 'member' attribute with full user DN
SET CLUSTER SETTING server.ldap_authorization.group_list_filter = '(&(objectClass=group)(member={{.User.DN}}))';

-- Base DN for group search
SET CLUSTER SETTING server.ldap_authorization.group_search_base_dn = 'ou=Groups,dc=corp,dc=example,dc=com';

-- Use the group's CN as the SQL role name
SET CLUSTER SETTING server.ldap_authorization.group_search_attribute = 'cn';
```

Example: If AD user `jsmith` is a member of the `db_admins` group, they receive the `db_admins` SQL role. Create the role first:

```sql
CREATE ROLE IF NOT EXISTS db_admins;
GRANT admin TO db_admins;
```

#### OpenLDAP Group Mapping

```sql
SET CLUSTER SETTING server.ldap_authorization.enabled = true;

-- OpenLDAP uses 'memberUid' with the uid value (not full DN)
SET CLUSTER SETTING server.ldap_authorization.group_list_filter = '(&(objectClass=posixGroup)(memberUid={{.User.Username}}))';

SET CLUSTER SETTING server.ldap_authorization.group_search_base_dn = 'ou=Groups,dc=example,dc=com';
SET CLUSTER SETTING server.ldap_authorization.group_search_attribute = 'cn';
```

### LDAPS (TLS) Configuration

LDAPS encrypts all traffic between CockroachDB and the LDAP server. This is required for production environments to prevent credential exposure.

**Standard LDAPS (port 636):**

```sql
SET CLUSTER SETTING server.host_based_authentication.configuration = '
host all all all ldap ldapserver=ldap.example.com ldapport=636 ldaptls=1 ldapbasedn="dc=example,dc=com" ldapsearchattribute=uid ldapbinddn="cn=readonly,dc=example,dc=com" ldapbindpasswd="<bind-password>"
host all all all password
';
```

**Verifying LDAPS connectivity** (run from a CockroachDB node):

```bash
# Test LDAPS connection and check certificate
openssl s_client -connect ldap.example.com:636 -showcerts </dev/null

# Test LDAP search over TLS
ldapsearch -H ldaps://ldap.example.com:636 -D "cn=readonly,dc=example,dc=com" -W -b "dc=example,dc=com" "(uid=testuser)"
```

If the LDAP server uses a private CA, the CA certificate must be in the system trust store on all CockroachDB nodes.

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
