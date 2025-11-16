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
- Secrets management (environment variables, KMS)
- Database connection pooling (PgBouncer)
- Regular security updates

### 5. GDPR Compliance

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

### Environment Variables for Security

```bash
# Authentication
JWT_SECRET_KEY=<strong-random-key>
REQUIRE_AUTH=true

# Encryption
ENCRYPTION_MASTER_KEY=<32-char-minimum>
ENCRYPTION_KEY_ROTATION_DAYS=90

# TLS/HTTPS
TLS_ENABLED=true
TLS_CERT_FILE=/path/to/cert.pem
TLS_KEY_FILE=/path/to/key.pem
TLS_MIN_VERSION=TLSv1.2

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60

# Audit Logging
AUDIT_ENABLED=true
AUDIT_ENCRYPT_SENSITIVE=true
```

---

**Last Updated**: 2025-11-16
**Document Version**: 1.0
**Security Team**: security@biowerk.example.com
