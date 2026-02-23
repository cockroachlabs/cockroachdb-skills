# ccloud CLI Commands for Private Connectivity

This reference provides ccloud CLI commands for managing private endpoints, VPC peering, and egress endpoints on CockroachDB Cloud clusters.

## Private Endpoint Services

### List Private Endpoint Services

```bash
# List available private endpoint services for a cluster
ccloud cluster networking private-endpoint-service list <cluster-id> -o json
```

**Key fields to inspect:**
- `cloud_provider` — AWS, GCP, or Azure
- `service_name` — The cloud provider service name/ID to use when creating the endpoint
- `region` — The region where the service is available
- `status` — Should be AVAILABLE

## Private Endpoint Connections (Ingress)

### List Private Endpoint Connections

```bash
# List all private endpoint connections for a cluster
ccloud cluster networking private-endpoint-connection list <cluster-id> -o json
```

**Key fields to inspect:**
- `endpoint_id` — The cloud provider endpoint ID
- `status` — PENDING, AVAILABLE, REJECTED, or DELETED
- `region` — Region of the endpoint

### Create a Private Endpoint Connection

```bash
# Register a cloud provider endpoint with the cluster
ccloud cluster networking private-endpoint-connection create <cluster-id> \
  --endpoint-id <cloud-provider-endpoint-id>
```

### Delete a Private Endpoint Connection

```bash
# Remove a private endpoint connection
ccloud cluster networking private-endpoint-connection delete <cluster-id> \
  --endpoint-id <endpoint-id>
```

## Egress Private Endpoints

### List Egress Endpoints

```bash
# List all egress endpoints for a cluster
ccloud cluster networking egress-endpoint list <cluster-id> -o json
```

**Key fields to inspect:**
- `id` — The egress endpoint ID
- `service_name` — The external service being connected to
- `status` — PENDING, AVAILABLE, REJECTED, or FAILED
- `endpoint_type` — The type of private connectivity

### Create an Egress Endpoint

```bash
# Create an egress endpoint to an external service
ccloud cluster networking egress-endpoint create <cluster-id> \
  --service-name <external-service-name> \
  --cloud-provider <aws|gcp|azure>
```

### Delete an Egress Endpoint

```bash
# Remove an egress endpoint
ccloud cluster networking egress-endpoint delete <cluster-id> \
  --endpoint-id <egress-endpoint-id>
```

## VPC Peering

### List VPC Peering Connections

```bash
# List all VPC peering connections for a cluster
ccloud cluster networking peering list <cluster-id> -o json
```

**Key fields to inspect:**
- `id` — The peering connection ID
- `status` — PENDING, ACTIVE, FAILED, or DELETED
- `peer_vpc_id` or `peer_network` — The peered VPC/network
- `peer_cidr` — The CIDR block of the peered network

### Create VPC Peering (AWS)

```bash
ccloud cluster networking peering create <cluster-id> \
  --peer-account-id <aws-account-id> \
  --peer-vpc-id <vpc-id> \
  --peer-vpc-region <region> \
  --peer-cidr <cidr-block>
```

### Create VPC Peering (GCP)

```bash
ccloud cluster networking peering create <cluster-id> \
  --peer-project-id <gcp-project-id> \
  --peer-network <network-name>
```

### Delete VPC Peering

```bash
ccloud cluster networking peering delete <cluster-id> \
  --peering-id <peering-id>
```

## IP Allowlist (Related)

Private endpoints bypass the IP allowlist, but the allowlist still applies to public connections.

```bash
# List current allowlist (for comparison with private endpoint setup)
ccloud cluster networking allowlist list <cluster-id> -o json
```

## Output Formatting

All commands support `-o json` for machine-readable output, which is useful for scripting and Terraform integration.

```bash
# JSON output
ccloud cluster networking private-endpoint-connection list <cluster-id> -o json

# Default table output
ccloud cluster networking private-endpoint-connection list <cluster-id>
```

## Notes

- Private endpoint connections require the cloud provider endpoint to be created first
- Egress endpoints require the external service to accept the connection
- VPC peering requires non-overlapping CIDR ranges between the CockroachDB Cloud VPC and the peer VPC
- Private endpoint changes can take several minutes to propagate
- Some commands may require specific ccloud CLI versions — run `ccloud version` to check
