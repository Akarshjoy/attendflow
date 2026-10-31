# Validation record and outstanding work

Evidence date: 31 October 2026

Status terminology:

- Verified: supported by supplied live output or CI/test evidence.
- Configured: visible in configuration/source, without complete behavior proof.
- Pending: required evidence has not been supplied.

## Evidence matrix

| Area | Status | Evidence / limit |
|---|---|---|
| Backend tests | Verified | Earlier local run: 54 passed; later tracing CI build/test job green |
| Frontend DOM smoke | Verified | Mocked login, rendering, attendance controls, logout and role UI |
| SAM template validation | Verified | Generated template passed validation/linting |
| OIDC deployment | Verified | Successful deployment after provider-audience correction |
| Failed tests block deployment | Verified | ad4772c failed; deploy skipped; demo removed by 6d999a5 |
| Missing/invalid API tokens | Verified | Both probes returned HTTP 401 |
| DynamoDB deletion protection | Verified | Five ACTIVE tables reported protection true |
| Scheduler trust restriction | Verified | Account/region/default-group restriction checked |
| Monitoring configuration | Configured | Dashboard, log retention and alarm definitions |
| SNS notification route | Verified | Manual alarm-state test delivered email |
| Actual metric-threshold incident | Pending | Manual notification test does not prove a real threshold breach |
| API throttle 50/100 | Verified | Live stage output |
| Authenticated /me capacity test | Verified | 2,340 HTTP 200; zero failed virtual users |
| API downstream SDK tracing | Verified | DynamoDB and S3 edges |
| Cleanup downstream SDK tracing | Verified | DynamoDB, S3 and Rekognition edges |
| Recognition downstream tracing | Pending | Not present in supplied post-change graph |
| Report downstream tracing | Pending | Not present in supplied post-change graph |
| Trusted Advisor selected checks | Verified | Account-level screenshots; limited scope |
| Cost scenario arithmetic | Documented | Explicit assumptions and excluded services |
| Measured cost savings | Pending | No controlled before/after cost experiment |
| Complete IAM effective-access audit | Pending | Explicit roles reviewed; generic helper changed zero roles |
| Three Logs Insights queries | Documented | Execution evidence for the full set not supplied |
| Live biometric accuracy/liveness | Pending | Mock tests and rejected capture do not establish accuracy |
| Full raw-version/vector deletion acceptance | Pending | Design/local tests are not complete live proof |
| PITR recovery drill | Pending | Configuration is not recovery validation |
| Complete capture-to-result latency | Pending | /me timings do not measure this flow |

## Key commit record

| Commit | Purpose |
|---|---|
| ec2eb44 | Deploy API throttle increase |
| ad4772c | Intentional failed-test deployment-gate demonstration |
| 6d999a5 | Remove demonstration test and record evidence |
| 6641298 | Load tools, runbook and cost assumptions |
| 50806e2 | Security review, tracing coverage and validation documentation |
| 616aa8e | OpenTelemetry SDK tracing deployment |

## What can be claimed

AttendFlow has demonstrated a working tested-build deployment pipeline,
specific authentication/storage controls, a successful scoped API load test
and live downstream instrumentation for API and Cleanup.

## What must not be claimed

- All AWS services or all four application functions have complete tracing.
- The whole application supports 390 requests/second.
- Every attendance capture completes within three seconds.
- A green Trusted Advisor subset proves complete security.
- Cost estimates are actual charges or enforced budgets.
- A cost optimization has produced measured savings.
- The system is certified for biometric, employment or payroll use.

## Next acceptance priorities

1. Verify Recognition and Report through authorized live operations.
2. Inspect representative trace attributes and telemetry handling.
3. Execute and retain results for the operational log queries.
4. Complete a controlled cost-optimization measurement.
5. Perform recovery and privacy-deletion acceptance tests.

Documentation completion does not change a pending technical check to verified.
