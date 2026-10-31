# AttendFlow: hardening documentation

Evidence date: 31 October 2026
Scope: AttendFlow only
AWS Region: us-east-1
CloudFormation stack: attendflow
Git branch: production-hardening

## Documentation index

1. [Architecture and application design](01-architecture.md)
2. [Monitoring, logging and tracing](02-observability.md)
3. [Security and IAM review](03-security-and-iam.md)
4. [Cost model and optimization assessment](04-costs.md)
5. [CI/CD and deployment controls](05-ci-cd.md)
6. [Performance and capacity evidence](06-performance.md)
7. [Operations and recovery runbook](07-operations-runbook.md)
8. [Validation and outstanding work](08-validation.md)

## Verified outcomes

- GitHub Actions built, tested and deployed the SAM application.
- An intentionally failing test blocked deployment; the test was subsequently removed.
- Missing and invalid API tokens returned HTTP 401.
- All five DynamoDB tables were verified active with deletion protection enabled.
- The configured API throttle was raised from 10 requests/second, burst 20,
  to 50 requests/second, burst 100.
- The follow-up authenticated /me test returned 2,340 HTTP 200 responses,
  with no failed virtual users and no recorded HTTP 429 responses.
- Observed /me latency was p50 267.8 ms, p95 301.9 ms and p99 320.6 ms.
- OpenTelemetry deployment succeeded for commit 616aa8e.
- The subsequent service graph showed API dependencies on DynamoDB and S3,
  and Cleanup dependencies on DynamoDB, S3 and Rekognition.

## Evidence boundaries

Results come from the command output, screenshots and source excerpts supplied
during the hardening work. This package does not assert an independent audit
of every source file or AWS resource.

Successful deployment and API tests do not establish biometric accuracy,
liveness, payroll suitability or complete production readiness.

Recognition-worker and Report-function downstream trace coverage, a measured
cost-saving experiment, and a recovery drill remain outstanding.

## Existing repository documentation

This package supplements the existing design, deployment, schema, security,
load-test, cost, tracing and validation documents. Historical records remain
useful; this package distinguishes their scope from the latest evidence.
