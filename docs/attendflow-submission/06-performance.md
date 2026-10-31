# Performance and capacity evidence

## Test scope

Tool: Artillery
Route: authenticated GET /prod/me
Virtual users created: 50
Intended activity duration: approximately 60 seconds per user
Identity model: one authenticated identity

The scenario is not a mixed-route benchmark, recognition benchmark or a claim
of 50 simultaneous Lambda executions. The /me route returns roles/timezone and
does not exercise DynamoDB.

## Results

| Metric | Before | After |
|---|---:|---:|
| Stage steady throttle, requests/second | 10 | 50 |
| Stage burst limit | 20 | 100 |
| Requests sent | 1,618 | 2,340 |
| HTTP 200 | 622 | 2,340 |
| HTTP 429 | 988 | 0 |
| Socket timeouts | 8 | 0 recorded |
| Completed virtual users | 42 | 50 |
| Failed virtual users | 8 | 0 |
| Reported request rate | 34/second | 39/second |

Before-change received responses: 1,610. The remaining eight requests timed out.

The measured pre-change traffic exceeded the configured steady stage limit.
The follow-up test demonstrated a successful run at its observed traffic level
after the capacity change.

## Successful-response latency

| Metric | Before, HTTP 2xx | After, all responses HTTP 200 |
|---|---:|---:|
| p50 | 273.2 ms | 267.8 ms |
| p95 | 399.5 ms | 301.9 ms |
| p99 | 713.5 ms | 320.6 ms |

After-change mean: 274.6 ms; maximum: 521 ms.

Do not compare the earlier aggregate latency directly with successful-response
latency without noting that the aggregate included many fast HTTP 429 responses.

## Interpretation

The follow-up /me test met a three-second p95 objective for this route and
scenario. It does not establish a three-second capture-to-attendance result,
cold-start behavior across all functions or performance under a different
geographic/network distribution.

Observed success at 39 requests/second does not establish maximum sustainable
application capacity.

## Ten-times traffic assessment

Ten times the observed 39 requests/second is approximately 390 requests/second.
That exceeds the configured 50 requests/second steady limit.

This is arithmetic, not a measured ten-times load test. Bursts, account-level
limits, Lambda concurrency, queue backlog, DynamoDB access patterns, polling
and Rekognition quotas would also need assessment.

## Reproduction and artifacts

- Scenario: tests/load/me-load.json
- Helper: tests/load/me-load.cjs
- Existing narrative: docs/hardening-load-test.md
- Before artifact: me-20261031-000237.json
- After artifact: .aws-sam/load-results/me-after-20261031-115047.json

Use a fresh authorized token supplied locally. Do not commit tokens or put
them into documentation. Preserve raw results with timestamps and configuration
when comparing future runs.
