# AttendFlow operations and recovery runbook

## Initial triage

1. Record the time in UTC, affected operation, HTTP status and request/session ID.
2. Check CloudFormation stack status and the latest deployment run.
3. Inspect the AttendFlow dashboard and relevant Lambda/API metrics.
4. Query the affected function's logs and available traces.
5. Establish whether the issue affects login, API reads, image processing,
   reporting, cleanup or alert delivery.
6. Avoid recording tokens, raw images or employee details in incident notes.

## Symptom guide

| Symptom | First checks |
|---|---|
| HTTP 401 | Token freshness, correct ID token, user pool and API authorizer |
| HTTP 403 | Cognito group, app-client checks and endpoint authorization |
| HTTP 429 | API stage/account limits, bursts and caller retry behavior |
| HTTP 500 | API logs and dependency errors; Lambda Errors may remain zero |
| Capture remains pending | Queue age/backlog, worker logs, event mapping and session expiry |
| Capture rejected | Validation/eligibility/consent outcome; rejection is not necessarily infrastructure failure |
| Reports missing | Report logs, configured timezone, schedules and private S3 objects |
| Cleanup failing | Function errors, exact-version permissions and pending reconciliation |
| Alert absent | SNS confirmation, alarm actions and actual state transitions |

## Tracing

Inspect API Gateway -> Lambda -> application spans -> AWS dependencies.

API and Cleanup downstream coverage is verified. Recognition and Report
coverage must be assessed from their own invocations.

Use a recent time range. Trace sampling and ingestion delay can limit visibility.
A missing graph node alone does not prove the function failed.

## Deployment failure

1. Read CloudFormation UPDATE_FAILED events, not only the final waiter error.
2. Confirm whether rollback completed.
3. Correct the specific cause.
4. Re-run the appropriate CI job once the stack can accept an update.
5. Verify application behavior after deployment.

For the pinned OpenTelemetry layer, the deployment role needs GetLayerVersion
on its exact version ARN.

Do not delete and recreate the stack to resolve a routine update failure.

## Application rollback

Identify the faulty application/template commit, inspect the working tree and
prepare a reviewed revert. Use the existing tested-build pipeline to deploy it.

For a layer-related runtime regression, revert the layer and wrapper/environment
configuration together. Confirm login, API reads and asynchronous processing.

A rollback procedure is documented; a deliberate recovery drill has not been
demonstrated.

## Queue recovery

Investigate failure reason, message age, session state and availability of the
exact raw-image version before redriving. Expired sessions or deleted images
may make replay invalid.

Preserve idempotency and transaction guards. Do not blindly replay an entire
dead-letter queue.

## Data recovery

Check PITR availability and recovery time. Restore to a separate DynamoDB table,
validate records and plan controlled application configuration changes.

A restore creates a recovery resource; it does not automatically reconnect the
application or prove consistency across all tables. Test cross-record
relationships, permissions and application reads before cutover.

PITR configuration is not evidence of a completed restore drill.

## Privacy cleanup

Verify both current and noncurrent raw versions. Deletion markers alone do
not establish image-byte removal. Check enrolled vectors separately.

When consent removal is pending, confirm matching remains disabled and review
cleanup retries. Do not clear pending markers merely to hide failures.

## Routine review

- Review errors, p95 duration, DLQ depth and cleanup outcomes.
- Check actual AWS costs against the planning model.
- Review logs and tracing growth after instrumentation changes.
- Review access, root MFA, Cognito administrator controls and retention.
- Reconfirm report schedules and alert delivery after relevant changes.
