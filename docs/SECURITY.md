# Security Documentation

## Overview

BIOwerk implements enterprise-grade security practices across all layers of the application stack. This document outlines our security architecture, testing procedures, and compliance measures.

## Security Testing Framework

### 1. Multi-Layer Security Testing

BIOwerk employs a comprehensive security testing strategy:

#### Static Analysis
- **Bandit**: Python security linter for code vulnerabilities
- **Safety & pip-audit**: Dependency vulnerability scanning
- **TruffleHog**: Secrets and credential detection
- **MyPy**: Type checking to prevent type-related vulnerabilities

#### Dynamic Analysis
- **OWASP ZAP**: Web application security testing
  - Baseline scans on every push
  - Full scans weekly (Sundays at 3 AM UTC)
  - API-specific scans on demand
- **Trivy**: Container image vulnerability scanning

#### E2E Security Testing
- Authentication and authorization tests
- Input validation and sanitization
- Rate limiting and DoS protection
- GDPR compliance verification

### 2. OWASP ZAP Security Testing

#### Scan Types

**Baseline Scan (Quick)**
- Runtime: ~10-15 minutes
- Trigger: Every push to main/develop branches
- Coverage: Common vulnerabilities (OWASP Top 10)
- Configuration: `.github/zap-config/baseline-rules.conf`

**API Scan (Targeted)**
- Runtime: ~20-30 minutes
- Trigger: Manual workflow dispatch
- Coverage: REST API security (authentication, authorization, input validation)
- Configuration: `.github/zap-config/api-scan-rules.conf`

**Full Scan (Comprehensive)**
- Runtime: ~60-90 minutes
- Trigger: Weekly schedule + manual dispatch
- Coverage: Deep security analysis including business logic flaws
- Configuration: `.github/zap-config/full-scan-rules.conf`

#### Running ZAP Scans Manually

```bash
# Via GitHub Actions workflow_dispatch
# 1. Go to Actions tab in GitHub
# 2. Select "OWASP ZAP Security Testing"
# 3. Click "Run workflow"
# 4. Select scan type: baseline, api, or full

# Local ZAP scan using Docker
docker run -v $(pwd):/zap/wrk:rw \
  -t owasp/zap2docker-stable zap-baseline.py \
  -t http://localhost:8080 \
  -g baseline.conf \
  -r zap-report.html
```

### 3. Vulnerability Management

#### Severity Levels

| Level | Response Time | Action Required |
|-------|--------------|-----------------|
| CRITICAL | 24 hours | Immediate patch and deploy |
| HIGH | 7 days | Priority fix in next sprint |
| MEDIUM | 30 days | Scheduled remediation |
| LOW | 90 days | Backlog for future release |

#### Vulnerability Workflow

1. **Detection**: Automated scans identify vulnerabilities
2. **Triage**: Security team reviews and validates findings
3. **Prioritization**: Assign severity based on CVSS score and business impact
4. **Remediation**: Developers fix vulnerabilities
5. **Verification**: Re-scan to confirm fix
6. **Documentation**: Update security advisory

### 4. Security Features

#### Authentication & Authorization
- JWT-based authentication
- Role-based access control (RBAC)
- Session management with secure cookies
- OAuth2/OIDC integration support

#### Data Protection
- Encryption at rest (AES-256)
- Encryption in transit (TLS 1.2+)
- Field-level encryption for sensitive data
- Key rotation (90-day default)

#### API Security
- Rate limiting (configurable per endpoint)
- Input validation and sanitization
- Request size limits
- CORS configuration
- API versioning

#### Infrastructure Security
- Container image scanning (Trivy)
- Network segmentation
- Secrets management (see detailed section below)
- Database connection pooling (PgBouncer)
- Regular security updates

#### Secrets Management
- Environment variable-based configuration
- No hardcoded credentials in codebase
- Automated secret validation in CI/CD
- Pre-commit hooks to prevent secret leaks
- Production secrets via KMS (AWS Secrets Manager, HashiCorp Vault, Azure Key Vault)
- Regular secret rotation (90-day default)
- See **Secrets Management** section below for details

### 5. Secrets Management

BIOwerk implements a comprehensive secrets management strategy to ensure credentials are never exposed in the codebase.

#### Development Environment Secrets

**Setup Process:**

1. **Copy the example environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Generate strong passwords:**
   ```bash
   # PostgreSQL password
   openssl rand -base64 32

   # MongoDB password
   openssl rand -base64 32

   # JWT secret key
   openssl rand -hex 32

   # Encryption master key
   openssl rand -base64 32

   # Grafana admin password
   openssl rand -base64 32

   # Grafana secret key
   openssl rand -base64 32
   ```

3. **Update .env with generated secrets:**
   - Replace all `<GENERATE_STRONG_PASSWORD_HERE>` placeholders
   - Ensure all passwords are 32+ characters
   - Never reuse passwords across services

4. **Verify configuration:**
   ```bash
   # Check that secrets are properly configured
   ./scripts/check_secrets.sh

   # Start services (will fail if required secrets are missing)
   docker-compose up -d
   ```

**Security Requirements:**
- `.env` file MUST be in `.gitignore` (already configured)
- Never commit `.env` files to version control
- Use unique secrets for each environment (dev/staging/production)
- Rotate development secrets every 90 days

#### Production Secrets Management

**CRITICAL**: Never use `.env` files in production. Use a secrets management service:

##### AWS Secrets Manager

```python
# Example: Loading secrets from AWS Secrets Manager
import boto3
import json

def get_secret(secret_name):
    client = boto3.client('secretsmanager', region_name='us-east-1')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# Load database credentials
db_secrets = get_secret('biowerk/production/database')
postgres_password = db_secrets['postgres_password']
mongo_password = db_secrets['mongo_password']
```

**Setup:**
```bash
# Store secrets in AWS Secrets Manager
aws secretsmanager create-secret \
  --name biowerk/production/database \
  --secret-string '{
    "postgres_password": "SECURE_PASSWORD",
    "mongo_password": "SECURE_PASSWORD"
  }'

# Enable automatic rotation (90 days)
aws secretsmanager rotate-secret \
  --secret-id biowerk/production/database \
  --rotation-lambda-arn arn:aws:lambda:region:account:function:rotation \
  --rotation-rules AutomaticallyAfterDays=90
```

##### HashiCorp Vault

```python
# Example: Loading secrets from Vault
import hvac

client = hvac.Client(url='https://vault.example.com')
client.auth.approle.login(role_id='...', secret_id='...')

# Read database secrets
db_secrets = client.secrets.kv.v2.read_secret_version(path='biowerk/database')
postgres_password = db_secrets['data']['data']['postgres_password']
```

**Setup:**
```bash
# Enable KV secrets engine
vault secrets enable -path=biowerk kv-v2

# Store secrets
vault kv put biowerk/database \
  postgres_password="SECURE_PASSWORD" \
  mongo_password="SECURE_PASSWORD"

# Create policy for BIOwerk application
vault policy write biowerk-app - <<EOF
path "biowerk/*" {
  capabilities = ["read", "list"]
}
EOF
```

##### Azure Key Vault

```python
# Example: Loading secrets from Azure Key Vault
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

credential = DefaultAzureCredential()
client = SecretClient(
    vault_url="https://biowerk-vault.vault.azure.net/",
    credential=credential
)

postgres_password = client.get_secret("postgres-password").value
```

**Setup:**
```bash
# Create Key Vault
az keyvault create \
  --name biowerk-vault \
  --resource-group biowerk-rg \
  --location eastus

# Store secrets
az keyvault secret set \
  --vault-name biowerk-vault \
  --name postgres-password \
  --value "SECURE_PASSWORD"

# Grant access to managed identity
az keyvault set-policy \
  --name biowerk-vault \
  --object-id <managed-identity-id> \
  --secret-permissions get list
```

##### Google Cloud Secret Manager

```python
# Example: Loading secrets from GCP Secret Manager
from google.cloud import secretmanager

client = secretmanager.SecretManagerServiceClient()
name = "projects/PROJECT_ID/secrets/postgres-password/versions/latest"
response = client.access_secret_version(request={"name": name})
postgres_password = response.payload.data.decode("UTF-8")
```

**Setup:**
```bash
# Create secret
gcloud secrets create postgres-password \
  --data-file=- <<< "SECURE_PASSWORD"

# Grant access to service account
gcloud secrets add-iam-policy-binding postgres-password \
  --member="serviceAccount:biowerk@PROJECT.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

#### Secret Rotation Procedures

**Automated Rotation (Recommended):**

1. **AWS Secrets Manager Rotation:**
   - Configure Lambda rotation function
   - Set rotation schedule (90 days default)
   - Automatic credential updates

2. **Vault Dynamic Secrets:**
   - Use database secret engine
   - Credentials generated on-demand
   - Automatic revocation on TTL expiry

**Manual Rotation Process:**

```bash
# 1. Generate new credentials
NEW_PASSWORD=$(openssl rand -base64 32)

# 2. Update database password
psql -U postgres -c "ALTER USER biowerk PASSWORD '$NEW_PASSWORD';"

# 3. Update secret in secrets manager
aws secretsmanager update-secret \
  --secret-id biowerk/production/database \
  --secret-string "{\"postgres_password\": \"$NEW_PASSWORD\"}"

# 4. Rolling restart of services to pick up new secret
kubectl rollout restart deployment/biowerk-mesh
```

**Rotation Schedule:**
- Production: Every 90 days (automated)
- Staging: Every 90 days
- Development: Every 90 days or on compromise
- Emergency rotation: Within 4 hours of suspected compromise

#### Secret Validation

**Pre-Commit Hook:**
Automatically runs before every commit to detect secrets:
```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Runs automatically on commit, or manually:
pre-commit run --all-files
```

**CI/CD Validation:**
Every PR and push is automatically scanned:
- Hardcoded password detection
- Default credential detection
- AWS key detection
- Private key detection
- TruffleHog secret scanning

**Manual Validation:**
```bash
# Run custom secrets check
./scripts/check_secrets.sh

# Expected output:
# ✓ No hardcoded secrets found
# ✓ No weak passwords detected
# ✓ .env.example exists and is clean
# ✓ No exposed credentials in connection strings
```

#### Docker Compose Secret Requirements

BIOwerk's `docker-compose.yml` enforces explicit secret configuration:

```yaml
# ❌ BEFORE: Hardcoded password (INSECURE)
environment:
  POSTGRES_PASSWORD: biowerk_dev_password

# ✅ AFTER: Required environment variable
environment:
  POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required - see .env.example}
```

**Behavior:**
- Docker Compose will FAIL to start if required secrets are not set
- No default passwords are provided
- Clear error messages guide developers to `.env.example`

**Example error when secrets are missing:**
```
ERROR: The POSTGRES_PASSWORD variable is not set. POSTGRES_PASSWORD is required - see .env.example
```

#### Secret Storage Best Practices

**DO:**
- ✅ Use environment variables for all secrets
- ✅ Use secrets management services in production
- ✅ Rotate secrets regularly (90-day default)
- ✅ Use strong, randomly generated passwords (32+ chars)
- ✅ Different secrets for each environment
- ✅ Backup encryption keys securely offline
- ✅ Audit secret access logs
- ✅ Use least privilege access

**DON'T:**
- ❌ Never commit secrets to version control
- ❌ Never hardcode secrets in code
- ❌ Never reuse passwords across environments
- ❌ Never share secrets via email/Slack
- ❌ Never log secrets in application logs
- ❌ Never use default/weak passwords
- ❌ Never skip secret rotation

#### Emergency Secret Compromise Response

If a secret is compromised:

1. **Immediate Actions (within 1 hour):**
   ```bash
   # 1. Rotate compromised credential immediately
   NEW_SECRET=$(openssl rand -base64 32)

   # 2. Update in secrets manager
   aws secretsmanager update-secret --secret-id COMPROMISED_SECRET --secret-string "$NEW_SECRET"

   # 3. Restart affected services
   kubectl rollout restart deployment/affected-service

   # 4. Invalidate active sessions if auth secret compromised
   redis-cli FLUSHDB  # Flush session cache
   ```

2. **Investigation (within 4 hours):**
   - Review audit logs for unauthorized access
   - Identify scope of compromise
   - Check for lateral movement

3. **Communication (within 8 hours):**
   - Notify security team
   - Document incident timeline
   - Prepare post-mortem

4. **Follow-up (within 24 hours):**
   - Rotate all related secrets
   - Review and update security controls
   - Conduct team training if needed

#### Monitoring & Alerting

**Secret Access Monitoring:**
- All secret reads from KMS are logged
- Unusual access patterns trigger alerts
- Failed authentication attempts monitored

**Alerts:**
- Multiple failed authentication attempts (>5 in 1 hour)
- Secret access from unusual IP/location
- Secret read without corresponding deployment
- Expired secrets detected
- Weak password patterns detected

**Dashboards:**
- Secret rotation status
- Secret age (days since last rotation)
- Secret access frequency
- Failed authentication attempts

#### Compliance Requirements

**GDPR/HIPAA:**
- Encryption keys must be rotated every 90 days
- Access to secrets must be audited
- Secrets must be encrypted at rest and in transit

**SOC 2:**
- Documented secret management procedures
- Regular access reviews
- Incident response for compromised secrets
- Annual penetration testing

**ISO 27001:**
- Classified secret inventory
- Access control based on least privilege
- Regular security awareness training
- Documented key management procedures

### 6. GDPR Compliance

BIOwerk includes dedicated GDPR compliance features:

- **Right to Access**: User data export functionality
- **Right to Erasure**: Automated data deletion
- **Data Minimization**: Configurable retention policies
- **Consent Management**: Audit logging of consent
- **Data Portability**: Structured data exports
- **Breach Notification**: Automated alerting

See `services/gdpr/` for implementation details.

### 6. Secure Development Lifecycle

#### Pre-Commit
- Git hooks for secret detection
- Code formatting and linting
- Local security checks

#### CI/CD Pipeline
- Unit tests with security assertions
- E2E security tests
- Dependency vulnerability scanning
- Container image scanning
- Static code analysis
- OWASP ZAP security testing

#### Deployment
- Infrastructure as Code (IaC) security scanning
- Production secrets from KMS
- Blue-green deployments
- Automated rollback on security alerts

### 7. Security Monitoring

#### Logging & Auditing
- All authentication attempts logged
- GDPR operations audited
- Failed requests tracked
- Anomaly detection

#### Distributed Tracing
- OpenTelemetry integration
- Request correlation IDs
- Performance and security insights
- Jaeger/Zipkin compatible

#### Metrics & Alerting
- Prometheus metrics exposed
- Security event dashboards
- Automated alerting on anomalies
- SLA monitoring

### 8. Incident Response

#### Security Incident Procedure

1. **Detection**: Automated alerts or manual report
2. **Containment**: Isolate affected systems
3. **Investigation**: Root cause analysis
4. **Eradication**: Remove threat and patch vulnerability
5. **Recovery**: Restore normal operations
6. **Post-Incident**: Review and improve processes

#### Contact

For security issues, contact:
- Email: security@biowerk.example.com
- PGP Key: [Link to public key]
- Bug Bounty: [Link to program]

### 9. Security Best Practices

#### For Developers

1. **Never commit secrets**: Use environment variables
2. **Validate all inputs**: Sanitize and validate user data
3. **Use parameterized queries**: Prevent SQL injection
4. **Implement rate limiting**: Protect against DoS
5. **Follow principle of least privilege**: Minimal permissions
6. **Keep dependencies updated**: Regular security patches
7. **Review security scan results**: Address findings promptly

#### For Operations

1. **Rotate credentials regularly**: 90-day default
2. **Monitor security logs**: Daily review
3. **Apply patches promptly**: Within SLA timelines
4. **Backup encryption keys**: Secure key management
5. **Test disaster recovery**: Quarterly DR drills
6. **Maintain security documentation**: Keep current

### 10. Compliance & Certifications

BIOwerk is designed to support:

- **GDPR**: EU General Data Protection Regulation
- **HIPAA**: Health Insurance Portability and Accountability Act (via configuration)
- **SOC 2**: Service Organization Control 2
- **ISO 27001**: Information Security Management

### 11. Security Testing Schedule

| Test Type | Frequency | Duration | Automation |
|-----------|-----------|----------|------------|
| Unit Security Tests | Every commit | 5 min | Fully automated |
| E2E Security Tests | Every PR | 10 min | Fully automated |
| ZAP Baseline Scan | Every push | 15 min | Fully automated |
| ZAP API Scan | On demand | 30 min | Manual trigger |
| ZAP Full Scan | Weekly | 90 min | Scheduled |
| Dependency Scan | Daily | 10 min | Fully automated |
| Container Scan | Every build | 15 min | Fully automated |
| Penetration Test | Quarterly | N/A | External vendor |
| Security Audit | Annually | N/A | External vendor |

### 12. Reporting Security Vulnerabilities

If you discover a security vulnerability:

1. **Do not** create a public GitHub issue
2. Email security@biowerk.example.com with:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if available)
3. Allow up to 48 hours for initial response
4. Coordinate disclosure timeline

### 13. Security Updates

Subscribe to security advisories:
- GitHub Security Advisories
- Project mailing list
- RSS feed: [Link]

---

## Quick Reference

### Running Security Scans Locally

```bash
# Run all unit tests including security tests
pytest tests/ -v

# Run E2E security tests
pytest tests/e2e/test_security.py -v

# Run dependency vulnerability scan
pip-audit --requirement requirements.txt
safety check --file requirements.txt

# Run code security analysis
bandit -r matrix/ mesh/ services/

# Run container security scan
trivy image biowerk-mesh:latest
```

### Required Environment Variables

All secrets must be configured via environment variables. See `.env.example` for a complete list.

**Critical Secrets (REQUIRED):**
```bash
# Database Credentials (generate with: openssl rand -base64 32)
POSTGRES_PASSWORD=<GENERATE_STRONG_PASSWORD>
MONGO_INITDB_ROOT_PASSWORD=<GENERATE_STRONG_PASSWORD>

# Application Secrets (generate with: openssl rand -hex 32)
JWT_SECRET_KEY=<GENERATE_STRONG_SECRET>
ENCRYPTION_MASTER_KEY=<GENERATE_STRONG_KEY>

# Grafana Credentials
GRAFANA_ADMIN_PASSWORD=<GENERATE_STRONG_PASSWORD>
GRAFANA_SECRET_KEY=<GENERATE_STRONG_SECRET>
```

**Security Configuration (OPTIONAL):**
```bash
# TLS/HTTPS
TLS_ENABLED=true
TLS_CERT_FILE=/path/to/cert.pem
TLS_KEY_FILE=/path/to/key.pem
TLS_MIN_VERSION=TLSv1.2

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60

# Authentication
REQUIRE_AUTH=false  # Set to true in production

# Audit Logging
AUDIT_ENABLED=true
AUDIT_ENCRYPT_SENSITIVE=true

# Key Rotation
ENCRYPTION_KEY_ROTATION_DAYS=90
```

**Secret Generation Commands:**
```bash
# Generate all required secrets at once
cat > .env << 'EOF'
# Database Credentials
POSTGRES_PASSWORD=$(openssl rand -base64 32)
MONGO_INITDB_ROOT_PASSWORD=$(openssl rand -base64 32)

# Application Secrets
JWT_SECRET_KEY=$(openssl rand -hex 32)
ENCRYPTION_MASTER_KEY=$(openssl rand -base64 32)

# Grafana Credentials
GRAFANA_ADMIN_PASSWORD=$(openssl rand -base64 32)
GRAFANA_SECRET_KEY=$(openssl rand -base64 32)
EOF

# Then manually replace the $(...) with actual generated values
```

---

**Last Updated**: 2025-11-17
**Document Version**: 2.0
**Security Team**: security@biowerk.example.com

**Version History:**
- v2.0 (2025-11-17): Added comprehensive secrets management documentation
- v1.0 (2025-11-16): Initial security documentation
