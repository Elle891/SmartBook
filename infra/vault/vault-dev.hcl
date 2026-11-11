ui = true

storage "file" {
  path = "/vault/data"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = true
}

# Dev mode: auto-unseal and root token
# NOTE: For production, replace with a proper seal configuration (e.g., AWS KMS auto-unseal)
# and disable the dev root token.
api_addr = "http://0.0.0.0:8200"
cluster_addr = "http://0.0.0.0:8201"

# Enable audit logging
# audit "file" {
#   path = "/vault/logs/audit.log"
# }

# Default lease TTL for secrets
default_lease_ttl = "168h"
max_lease_ttl     = "720h"
