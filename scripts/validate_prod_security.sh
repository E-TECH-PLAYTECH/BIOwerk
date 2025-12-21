#!/usr/bin/env bash
# Guardrails to prevent insecure production deployments.
set -euo pipefail

failures=0

fail() {
  echo "❌ $1"
  failures=$((failures + 1))
}

section() {
  echo
  echo "==> $1"
}

section "Checking production docker-compose override"
if [[ ! -f docker-compose.prod.override.yml ]]; then
  fail "docker-compose.prod.override.yml is missing"
else
  rg --quiet 'REQUIRE_AUTH:\s*\"true\"' docker-compose.prod.override.yml || fail "Mesh REQUIRE_AUTH must be forced to true in docker-compose.prod.override.yml"
  rg --quiet 'TLS_ENABLED:\s*\"true\"' docker-compose.prod.override.yml || fail "Mesh TLS_ENABLED must be forced to true in docker-compose.prod.override.yml"
  rg --quiet '/run/secrets' docker-compose.prod.override.yml || fail "docker-compose.prod.override.yml must mount secrets from /run/secrets"
  if rg --quiet '"8080:8080"' docker-compose.prod.override.yml; then
    fail "docker-compose.prod.override.yml must not expose plaintext 8080 bindings"
  fi
fi

section "Checking production-minimal kustomize overlay"
if [[ ! -d k8s/overlays/production-minimal ]]; then
  fail "k8s/overlays/production-minimal is missing"
else
  rg --quiet 'environment:\s*\"production\"' k8s/overlays/production-minimal || fail "production-minimal overlay must force ENVIRONMENT=production"
  rg --quiet 'tls_enabled:\s*\"true\"' k8s/overlays/production-minimal || fail "production-minimal overlay must force tls_enabled=true"
  rg --quiet 'require_auth:\s*\"true\"' k8s/overlays/production-minimal || fail "production-minimal overlay must force require_auth=true"
  rg --quiet 'secretName:\s*tls-certs' k8s/overlays/production-minimal/patches/mesh-deployment.yaml || fail "Mesh deployment must require the tls-certs secret in production-minimal"
  if rg --quiet 'port:\s*80' k8s/overlays/production-minimal/patches/mesh-service.yaml; then
    fail "Mesh service should not publish plaintext HTTP in production-minimal"
  fi
fi

section "Checking Helm values for secure defaults"
if [[ -f helm/biowerk/values.yaml ]]; then
  rg -U --quiet 'tls:\s*\n\s*enabled:\s*true' helm/biowerk/values.yaml || fail "Helm values must default tls.enabled to true"
  rg --quiet 'requireAuth:\s*true' helm/biowerk/values.yaml || fail "Helm values must require authentication by default"
else
  fail "helm/biowerk/values.yaml is missing"
fi

section "Scanning for dev secret defaults in production configs"
for default_secret in "dev-secret-key-change-in-production" "change-this-master-key-in-production-min-32-chars-required"; do
  if rg --quiet "$default_secret" docker-compose.prod.override.yml k8s/overlays/production-minimal helm/biowerk/values.yaml; then
    fail "Found default secret marker '$default_secret' in production configurations"
  fi
done

echo
if [[ $failures -gt 0 ]]; then
  echo "Production guardrail violations: $failures"
  exit 1
fi

echo "✅ Production guardrails enforced."
