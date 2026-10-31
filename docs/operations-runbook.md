# AttendFlow operations runbook

Stack: attendflow
Region: us-east-1
CLI profile: my-account
Dashboard: attendflow-us-east-1-operations
Deployment branch: production-hardening

## First response

1. Record the incident time in UTC, affected operation and user impact.
2. Open the operations dashboard. Check invocations, errors and P95 duration.
3. Check CloudFormation status and the most recent deployment.
4. Inspect the affected Lambda log group:
   /aws/lambda/attendflow-ApiFunction
   /aws/lambda/attendflow-Recognition
   /aws/lambda/attendflow-Cleanup
   /aws/lambda/attendflow-Report
5. Correlate request IDs, trace IDs and capture session IDs.
   Keep authorization tokens, photos and personal data out of incident notes.

## Symptoms and checks

| Symptom | Check and response |
|---|---|
| HTTP 401 | Refresh login; verify token expiry, audience and configured user pool. |
| HTTP 403 | Check the user's Cognito groups and the route's authorization rules. |
| HTTP 429 | Check API throttling and Lambda throttles. Current stage targets: 50 RPS, burst 100. Review traffic before changing limits. |
| HTTP 500 | Inspect api_aws_error and api_failure logs. Check AWS permissions and downstream errors. |
| Capture REJECTED | Inspect capture_outcome reason. face_validation indicates a validation rejection; follow the capture guidance shown in the UI. |
| Capture stays pending | Check Recognition logs, UploadQueue backlog, message age and dead-letter queues. |
| Missing report | Check Report logs and Scheduler delivery failures; verify the requested business date. |
| Slow responses | Check P95, Lambda duration/throttles and traces; identify the slow dependency. |

## Monitoring interpretation

- Configured Lambda error-rate alarms: greater than 5% over 5 minutes.
- Configured Lambda P95 duration alarms: greater than 3 seconds over 5 minutes.
- SNS email delivery was verified using a simulated alarm transition.
- A handled HTTP 500 may not increment Lambda Errors.
- SQS partial-batch failures need queue/log monitoring as well.
- A quiet Lambda error alarm alone does not establish application health.

## Recovery

- For a failed deployment, inspect CloudFormation events and rollback status.
- For an application regression, revert the identified application change,
  run the existing checks and deploy through the established workflow.
- Review the change set for infrastructure or data-affecting changes.
- Do not delete the stack or disable table protection as a troubleshooting step.
- Investigate failed queue messages before replaying them; verify session state
  and whether the original image still exists.
- DynamoDB PITR recovery requires a separate restore-and-cutover procedure.
  A successful recovery drill has not yet been recorded.

## Verify recovery

- Confirm the stack is stable.
- Verify login and authenticated GET /me.
- Verify the operation affected by the incident.
- Check errors, latency and queue backlog over the next monitoring periods.
- Record cause, fix, deployment commit and supporting evidence.

## Evidence and limits

- Load test: 50 virtual users, authenticated GET /me, approximately 60 seconds.
- After tuning: 2,340 HTTP 200 responses; zero reported failures.
- P95: 301.9 ms; P99: 320.6 ms; reported throughput: 39 requests/second.
- This test does not establish recognition, database or reporting capacity.
- Cost figures are planning estimates; measured cost savings remain unverified.