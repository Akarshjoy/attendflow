# Monitoring, logging and tracing

## Configuration

- Four Lambda functions have active tracing.
- API Gateway stage tracing is enabled.
- Lambda log retention is 14 days.
- The monitoring helper configures eight additional alarms and one dashboard.
- Existing alarms are preserved.

The configured alarm set includes four Lambda error-count alarms, a queue
alarm, four Lambda error-rate alarms and four Lambda p95-duration alarms.

| Alarm family | Condition |
|---|---|
| Lambda error count | Sum greater than zero over 300 seconds |
| Lambda error rate | Greater than 5% over 300 seconds |
| Lambda duration | p95 greater than 3,000 ms over 300 seconds |
| Dead-letter queue | Visible messages greater than zero |

The error-rate expression handles zero invocations. These are Lambda metrics:
application HTTP 500 responses caught by the handler and SQS partial-batch
failures may require separate log or application-level monitoring.

The dashboard shows invocation, error and p95-duration metrics for the functions.

## Alert-delivery evidence

SNS email subscription and delivery were verified through a manual alarm-state
transition. This verifies the notification route; it is not evidence of an
actual workload breaching an alarm threshold.

## OpenTelemetry deployment

Pinned layer:

arn:aws:lambda:us-east-1:615299751070:layer:AWSOpenTelemetryDistroPython:32

AWS metadata listed Python 3.14 and x86_64 as compatible.

Environment settings:

- AWS_LAMBDA_EXEC_WRAPPER=/opt/otel-instrument
- OTEL_AWS_APPLICATION_SIGNALS_ENABLED=false
- OTEL_METRICS_EXPORTER=none
- OTEL_LOGS_EXPORTER=none

The configuration is applied through scripts/apply_tracing.py and its existing
build_template.py hook. Additional OpenTelemetry log/metric exports are disabled;
ordinary Lambda logs and metrics remain available.

The initial update failed because the deployment role lacked GetLayerVersion.
A policy allowing that action on the exact pinned layer version resolved the
failure. The retried deployment succeeded for commit 616aa8e.

## Verified service graph

The subsequent 15-minute query showed:

| Source | Observed downstream services |
|---|---|
| attendflow/prod API Gateway stage | API Lambda service |
| API Lambda function | Instrumented API application |
| Instrumented API application | DynamoDB and S3 |
| Cleanup Lambda function | Instrumented Cleanup application |
| Instrumented Cleanup application | DynamoDB, S3 and Rekognition |

Observed nodes reported 11 API stage requests, 6 API application requests and
3 Cleanup application requests. Dependency nodes reported 24 DynamoDB,
4 S3 and 3 Rekognition requests.

These are graph observations, not complete workload counts. Do not add Lambda
service, function and application node counts together as unique requests.
Count differences do not by themselves demonstrate failed requests.

Other projects appearing in the account graph are excluded from this report.

Recognition-worker and Report-function downstream coverage have not yet been
demonstrated. Rekognition activity under Cleanup does not verify Recognition.

## Three CloudWatch Logs Insights queries

Select the appropriate AttendFlow log groups and a relevant time range.
These queries are provided for operational use; execution results for all
three have not been supplied.

### 1. Error-pattern volume by function

```text
fields @timestamp, @log, @message
| filter @message like /ERROR|Traceback|Task timed out|Runtime\./
| stats count(*) as matching_log_events by @log, bin(5m)
```

This counts matching log events, not unique failed invocations.

### 2. Lambda execution duration and billed duration

```text
filter @type = "REPORT"
| stats count(*) as invocations,
    pct(@duration, 50) as p50_ms,
    pct(@duration, 95) as p95_ms,
    pct(@duration, 99) as p99_ms,
    avg(@billedDuration) as average_billed_ms,
    max(@maxMemoryUsed) as maximum_memory_bytes
  by @log
```

Lambda execution duration is not browser-to-result latency.

### 3. Capture-outcome logging volume

```text
fields @timestamp, @message
| filter @message like /capture_outcome/
| stats count(*) as outcome_log_events by bin(5m)
```

Use the Recognition log group. This counts emitted outcome events; it does not
establish recognition accuracy or a successful-match rate.

## Operational limits

Review sampled trace attributes before treating telemetry as privacy-approved.
Do not intentionally add tokens, image bytes, full request bodies or employee
records to logs or trace attributes.

A complete asynchronous user-flow trace and end-to-end capture latency remain
separate acceptance gates.
