---
name: configuring-private-connectivity
description: Configures private network connectivity for CockroachDB Cloud clusters including AWS PrivateLink, GCP Private Service Connect, Azure Private Link, egress private endpoints, and VPC peering. Use when setting up private endpoints to eliminate public internet exposure, configuring egress to external services like Kafka, or establishing VPC peering.
compatibility: Requires CockroachDB Cloud Advanced or Standard plan. Private endpoints require cloud provider configuration (AWS, GCP, or Azure). VPC peering requires Advanced plan.
metadata:
  author: cockroachdb
  version: "1.0"
---

# Configuring Private Connectivity

Configures private network connectivity for CockroachDB Cloud clusters to eliminate public internet exposure for database traffic. Covers ingress private endpoints (AWS PrivateLink, GCP Private Service Connect, Azure Private Link), egress private endpoints for outbound connections to external services, and VPC peering.

## When to Use This Skill

- Setting up private endpoints to eliminate public internet exposure for database connections
- Configuring egress private endpoints for CDC changefeeds to Confluent Kafka or other external services
- Establishing VPC peering between a CockroachDB Cloud cluster and application VPCs
- Troubleshooting DNS resolution issues with private endpoints
- Resolving "stuck pending" or connection failure errors with private endpoints
- Automating private connectivity setup with Terraform

## Prerequisites

- **CockroachDB Cloud cluster** — Standard or Advanced plan (VPC peering requires Advanced)
- **ccloud CLI** authenticated with Cluster Admin role
- **Cloud provider access:**
  - **AWS:** IAM permissions to create VPC endpoints, modify DNS, and manage security groups
  - **GCP:** Permissions to create Private Service Connect endpoints and DNS records
  - **Azure:** Permissions to create private endpoints and manage DNS zones
- **Cluster ID and cloud provider details** from `ccloud cluster info`

**Verify access:**
```bash
ccloud auth whoami
ccloud cluster info <cluster-name> -o json
```

See [ccloud commands reference](references/ccloud-commands.md) for full command syntax.

## Steps

### Part 1: Ingress Private Endpoints

Private endpoints allow applications in your VPC to connect to CockroachDB Cloud without traversing the public internet.

#### 1.1 Get the Private Endpoint Service

```bash
# Get the private endpoint service information for the cluster
ccloud cluster networking private-endpoint-service list <cluster-id> -o json
```

This returns the cloud provider service name/ID needed to create the endpoint in your cloud account.

#### 1.2 Create the Private Endpoint (AWS PrivateLink)

```bash
# In your AWS account, create a VPC endpoint
aws ec2 create-vpc-endpoint \
  --vpc-id <your-vpc-id> \
  --service-name <service-name-from-ccloud> \
  --vpc-endpoint-type Interface \
  --subnet-ids <subnet-id-1> <subnet-id-2> \
  --security-group-ids <security-group-id>
```

**Security group requirements:**
- Allow inbound TCP port 26257 from your application subnets
- Allow outbound to the VPC endpoint

#### 1.3 Create the Private Endpoint (GCP Private Service Connect)

```bash
# Reserve an internal IP address
gcloud compute addresses create cockroachdb-psc \
  --region=<region> \
  --subnet=<subnet> \
  --addresses=<internal-ip>

# Create the Private Service Connect endpoint
gcloud compute forwarding-rules create cockroachdb-psc \
  --region=<region> \
  --network=<network> \
  --address=cockroachdb-psc \
  --target-service-attachment=<service-attachment-from-ccloud>
```

#### 1.4 Create the Private Endpoint (Azure Private Link)

```bash
# Create a private endpoint in your Azure subscription
az network private-endpoint create \
  --name cockroachdb-pe \
  --resource-group <resource-group> \
  --vnet-name <vnet-name> \
  --subnet <subnet-name> \
  --private-connection-resource-id <service-id-from-ccloud> \
  --connection-name cockroachdb-connection
```

#### 1.5 Register the Endpoint in CockroachDB Cloud

```bash
# Register the private endpoint connection with the cluster
ccloud cluster networking private-endpoint-connection create <cluster-id> \
  --endpoint-id <cloud-provider-endpoint-id>
```

Wait for the connection status to become `AVAILABLE`:
```bash
ccloud cluster networking private-endpoint-connection list <cluster-id> -o json
```

#### 1.6 Configure DNS

Private endpoints require DNS configuration so clients resolve the cluster hostname to the private endpoint IP instead of the public IP.

**AWS:** Create a Route 53 private hosted zone with the cluster hostname pointing to the VPC endpoint DNS name.

**GCP:** Create a Cloud DNS private zone with an A record pointing to the reserved internal IP.

**Azure:** Create a private DNS zone with an A record pointing to the private endpoint IP.

See [cloud provider setup reference](references/cloud-provider-setup.md) for detailed DNS configuration steps.

### Part 2: Egress Private Endpoints

Egress private endpoints allow CockroachDB Cloud to connect to external services (e.g., Confluent Kafka for CDC) over a private network path.

#### 2.1 Create an Egress Private Endpoint

```bash
# Create an egress endpoint to an external service
ccloud cluster networking egress-endpoint create <cluster-id> \
  --service-name <external-service-name> \
  --cloud-provider <aws|gcp|azure>
```

**Common egress targets:**
- Confluent Cloud Kafka (most common use case)
- Amazon MSK
- Self-managed Kafka on PrivateLink
- Other SaaS services with PrivateLink support

#### 2.2 Accept the Endpoint Connection

The external service owner must accept the pending connection request. For Confluent Cloud:

1. Log into Confluent Cloud Console
2. Navigate to **Networking > Private Link Access**
3. Accept the pending connection from the CockroachDB Cloud account

#### 2.3 Verify Egress Endpoint Status

```bash
# Check egress endpoint status (should transition from PENDING to AVAILABLE)
ccloud cluster networking egress-endpoint list <cluster-id> -o json
```

**Troubleshooting "stuck pending":**
- Verify the external service has accepted the connection
- Check that the external service is in the same cloud provider region
- Contact the external service admin to accept the pending connection

#### 2.4 Use the Egress Endpoint in CDC Changefeeds

```sql
-- Create a changefeed using the egress endpoint
CREATE CHANGEFEED FOR TABLE orders
  INTO 'kafka://<private-kafka-endpoint>:9092?topic_prefix=crdb_'
  WITH updated, resolved;
```

### Part 3: VPC Peering

VPC peering creates a direct network connection between your VPC and the CockroachDB Cloud VPC.

#### 3.1 Initiate VPC Peering

```bash
# AWS
ccloud cluster networking peering create <cluster-id> \
  --peer-account-id <aws-account-id> \
  --peer-vpc-id <vpc-id> \
  --peer-vpc-region <region> \
  --peer-cidr <cidr-block>

# GCP
ccloud cluster networking peering create <cluster-id> \
  --peer-project-id <gcp-project-id> \
  --peer-network <network-name>
```

#### 3.2 Accept the Peering Request

**AWS:** Accept the peering request in the VPC Console:
```bash
aws ec2 accept-vpc-peering-connection \
  --vpc-peering-connection-id <peering-id>
```

**GCP:** Peering is established automatically if the peer network configuration is correct.

#### 3.3 Configure Route Tables

After peering is established, update route tables to route traffic to the CockroachDB Cloud CIDR through the peering connection.

```bash
# AWS — add a route to the CockroachDB Cloud CIDR
aws ec2 create-route \
  --route-table-id <route-table-id> \
  --destination-cidr-block <cockroachdb-cidr> \
  --vpc-peering-connection-id <peering-id>
```

#### 3.4 Verify VPC Peering

```bash
# Check peering status
ccloud cluster networking peering list <cluster-id> -o json
```

Test connectivity from your VPC:
```bash
# From an instance in your peered VPC
cockroach sql --url "<connection-string>" -e "SELECT 1;"
```

## Safety Considerations

| Impact Type | Severity | Recommendation |
|-------------|----------|----------------|
| Private endpoint creation | Low | Does not affect existing connections; additive change |
| DNS configuration change | Medium | Incorrect DNS can break existing connections |
| IP allowlist interaction | Medium | Private endpoints bypass IP allowlists; review security implications |
| VPC peering CIDR overlap | High | Overlapping CIDRs will prevent peering; plan IP space carefully |
| Egress endpoint creation | Low | Does not affect cluster operation |

**Do not:**
- Delete a private endpoint that has active connections without migrating traffic first
- Configure overlapping CIDR ranges between peered VPCs
- Remove DNS records for private endpoints while clients are connected
- Assume private endpoints replace all other security controls (authentication and authorization still apply)

**When to prefer private endpoints over IP allowlists:**
- When the IP allowlist entry limit is insufficient for your number of source IPs
- When you need to eliminate public internet exposure entirely
- When compliance requirements mandate private network paths

## Rollback

**Remove a private endpoint:**
```bash
# Delete the endpoint connection in CockroachDB Cloud
ccloud cluster networking private-endpoint-connection delete <cluster-id> \
  --endpoint-id <endpoint-id>

# Delete the endpoint in your cloud provider
# AWS
aws ec2 delete-vpc-endpoints --vpc-endpoint-ids <endpoint-id>
```

**Remove VPC peering:**
```bash
ccloud cluster networking peering delete <cluster-id> --peering-id <peering-id>
```

After removing private connectivity, ensure the IP allowlist is configured to allow connections from the public internet if needed.

## References

**Skill references:**
- [ccloud networking commands](references/ccloud-commands.md)
- [Cloud provider setup steps](references/cloud-provider-setup.md)

**Related skills:**
- [configuring-ip-allowlists](../configuring-ip-allowlists/SKILL.md) — IP-based network access control
- [auditing-cloud-cluster-security](../auditing-cloud-cluster-security/SKILL.md) — Run a full security posture audit

**Official CockroachDB Documentation:**
- [Network Authorization](https://www.cockroachlabs.com/docs/cockroachcloud/network-authorization.html)
- [AWS PrivateLink](https://www.cockroachlabs.com/docs/cockroachcloud/aws-privatelink.html)
- [GCP Private Service Connect](https://www.cockroachlabs.com/docs/cockroachcloud/gcp-private-service-connect.html)
- [Azure Private Link](https://www.cockroachlabs.com/docs/cockroachcloud/azure-private-link.html)
- [VPC Peering](https://www.cockroachlabs.com/docs/cockroachcloud/network-authorization.html#vpc-peering)
- [Egress Perimeter Controls](https://www.cockroachlabs.com/docs/cockroachcloud/egress-perimeter-controls.html)
