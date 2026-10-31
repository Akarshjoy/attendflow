# AttendFlow API load-test results

Date: 2026-10-31
Region: us-east-1
Endpoint: authenticated GET /prod/me

## Workload

Artillery started 50 virtual users over one second.
Each user repeatedly requested /me for approximately 60 seconds,
with a one-second pause between requests and a five-second request timeout.
The test reused one authenticated identity across all virtual users.

## Measured results

| Metric | Before | After |
|---|---:|---:|
| API default rate target | 10 requests/sec | 50 requests/sec |
| API default burst target | 20 | 100 |
| Users started | 50 | 50 |
| Users completed | 42 | 50 |
| Requests attempted | 1618 | 2340 |
| HTTP 200 | 622 | 2340 |
| HTTP 429 | 988 | 0 |
| Socket timeouts | 8 | 0 |
| Unsuccessful requests | 61.56% | 0% |
| Successful-response P50 | 273.2 ms | 267.8 ms |
| Successful-response P95 | 399.5 ms | 301.9 ms |
| Successful-response P99 | 713.5 ms | 320.6 ms |
| Artillery-reported request rate | 34/sec | 39/sec |

Capacity change commit: ec2eb44.
The change was deployed through GitHub Actions and verified on the live stage.

## Interpretation and limits

The original 10 requests/sec throttle explains the heavy HTTP 429 rate.
After increasing the default throttle targets, this repeat run returned
HTTP 200 for every request. The earlier eight timeouts did not recur;
their individual cause was not isolated.

This is a short authenticated API baseline, not a whole-application
capacity certification. It does not exercise Cognito login throughput,
DynamoDB operations, image uploads, Rekognition, or report generation.

A hypothetical 10x version of the observed 39 requests/sec workload
would offer approximately 390 requests/sec, exceeding the current
50 requests/sec target. That workload has not been tested.
Increasing the throttle alone would not establish backend capacity.

## Local evidence

Before: .aws-sam/load-results/me-20261031-000237.json
After: .aws-sam/load-results/me-after-20261031-115047.json

Keep authentication tokens out of committed files.
