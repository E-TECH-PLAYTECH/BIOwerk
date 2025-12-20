# API Rate-Limit & Budget Testing Guide

This guide covers fuzzing and validation of rate-limit enforcement for both external API users and operators. It uses the mesh gateway (`/v1/{agent}/{endpoint}`) and the built-in rate limiter defined in `matrix/rate_limiter.py` and configured via `matrix/config.py` settings such as `rate_limit_requests`, `rate_limit_window`, `rate_limit_strategy`, `rate_limit_per_ip`, and `rate_limit_per_user`.

## Goals

- Verify **hard limits** (strict block) and **soft budgets** (warn/log before enforce) for operators and API consumers.
- Validate per-IP and per-user behavior, burst handling (`rate_limit_burst`), and excluded paths (`rate_limit_exclude_paths`).
- Confirm correct 429 payloads and headers (e.g., `Retry-After`) and that mesh audit events record limit hits.

## Test Inputs

- Mesh base URL (default `http://localhost:8080`).
- Auth contexts: API key, authenticated user token, and anonymous.
- Identifier strategies: IP-based and user-based (toggle via `rate_limit_per_ip`/`rate_limit_per_user`).
- Workload mix: read-heavy vs. write-heavy endpoints; combine fast calls (health) and heavier calls (LLM-backed).

## Quick Smoke (Soft Budget)

Use a low limit to prove enforcement quickly:

```bash
export RATE_LIMIT_REQUESTS=5
export RATE_LIMIT_WINDOW=30
export RATE_LIMIT_STRATEGY=sliding_window
docker compose up mesh

# Burst 6 requests to the same endpoint/user
python examples/run_demo_requests.py --repeat 2 --focus osteon/outline
```

Expect one failure with 429; verify logs show the rate-limit event and the response includes `retry_after`.

## Fuzzing with k6

```bash
cat > /tmp/rate-limit.js <<'JS'
import http from "k6/http";
import { check, sleep } from "k6";

const base = __ENV.MESH_URL || "http://localhost:8080";
const payload = JSON.stringify({
  origin: "k6",
  target: "nucleus",
  intent: "plan",
  input: { goal: "saturation-test", requirements: ["resilience"] }
});

export const options = {
  vus: 10,
  duration: "45s",
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(95)<1500"]
  }
};

export default function () {
  const res = http.post(`${base}/v1/nucleus/plan`, payload, { headers: { "Content-Type": "application/json" } });
  check(res, {
    "429 when limit exceeded": (r) => r.status === 429 || r.status === 200,
  });
  sleep(0.2);
}
JS

k6 run /tmp/rate-limit.js
```

- Validate counters in Redis (`mesh_rate_limit_*` keys) match expectation.
- For **soft budgets**, configure alert-only by setting `RATE_LIMIT_REQUESTS` high but enabling log-based monitors; confirm no 429 but warnings emitted.

## Operator vs. API User Scenarios

| Scenario | Identifier | Expected Behavior |
| --- | --- | --- |
| Anonymous IP spike | IP hash | Blocks after limit; returns 429 with `Retry-After` |
| Authenticated user burst | user id | Limits even when IP is shared (NAT/VPN) |
| Operator override | privileged role | Either higher budget or bypass; document and audit |
| Mixed burst + steady | IP + user | Sliding window smooths edges; token bucket respects `rate_limit_burst` |

## Assertions & Instrumentation

- Mesh logs should include `rate_limit.remaining`, `rate_limit.reset`, and identifier hashes (no PII).
- 429 responses must set `Retry-After` and include JSON body with limit/window context.
- Prometheus: add alerts on sustained 429 spikes; Grafana dashboard should graph remaining tokens per identifier.
- Audit trail (see `matrix/audit.py`) should capture limit hits with `EventCategory.SECURITY` and `Severity.WARNING`.

## Cleanup & Guardrails

- Reset Redis counters between tests: `redis-cli FLUSHDB` (only in non-prod) or delete `mesh_rate_limit_*` keys.
- Restore production defaults for `RATE_LIMIT_*` environment variables post-test.
- Document tested limits and outcomes in release notes to guide operators and API consumers.
