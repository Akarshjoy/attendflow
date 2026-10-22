# Troubleshooting and recovery

Reuse the variables from deployment.md. Diagnose the first failure, not a later symptom.

## Deployment

| Symptom | Action |
|---|---|
| Python not found / Microsoft Store alias | Use the full Python 3.14 executable and prepend its directory to this terminal’s PATH |
| sam not recognized | Install SAM, reopen VS Code, confirm sam --version |
| Runtime mismatch | Match local Python to the generator/runtime; rebuild, not just edit an old build output |
| DescribeStacks CompanionStack denied | Attach the reviewed AttendFlow policies; the attendflow* stack prefix includes companion stacks |
| Event source mapping access denied | Check Create mapping wildcard/function condition and Get/Update/Delete mapping ARN permissions separately |
| Policy too long | Attach generated pieces as customer-managed policies, not user inline policies |
| Rekognition subscription/service access error | Check account eligibility, region and service access; do not assume an upgrade is free or required |
| Lambda concurrency quota error | This template has no reserved-concurrency requirement; inspect other resources/account quota and the exact failed resource |
| CREATE_FAILED / ROLLBACK_COMPLETE / DELETE_FAILED | Read events and fix permission/resource cause before retrying. Retained resources can block recreation |
| S3 bucket already exists | This stack’s captures name includes account and region. Inspect an older retained bucket before reuse/import/deletion |

```powershell
aws cloudformation describe-stack-events @awsArgs --stack-name $stack `
  --query "StackEvents[?contains(ResourceStatus, 'FAILED')].{Resource:LogicalResourceId,Reason:ResourceStatusReason}" `
  --output json --no-cli-pager
```

## Browser and attendance

| Symptom | Action |
|---|---|
| Blank/config missing | Run setup.py configure; upload all frontend files; refresh CloudFront cache |
| Camera unavailable | Use HTTPS; grant browser permission; close another app using the camera; camera errors do not create attendance |
| Cognito invitation missing | Check mailbox/spam, Cognito creation result, email-delivery quotas and user status. SNS confirmation is a different email |
| Unauthorized after a while | Tokens last one hour. Sign out/in; page refresh intentionally clears the in-memory session |
| Upload 403 | Check presigned policy expiry, size/type/encryption fields, region and exact CloudFront origin in S3 CORS |
| Processing lasts more than a few seconds | Use Check last capture. Inspect Sessions state, SQS queue, Lambda logs and DLQ. Do not repeatedly upload |
| No confident match | Improve lighting/framing; verify enrollment, consent and exact FaceId mapping. Do not lower threshold blindly |
| Employee absent from enrollment dropdown | Needs active status, consent, no existing face, no pending removal |
| Already enrolled / face belongs to another employee | Review directory. Remove enrollment deliberately before replacing; cleanup may need to reconcile an orphan |
| Clock-out rejected | Wait for successful clock-in first; same local date, increasing time, no prior out |
| Wrong late status | Compare S3 upload time in business timezone to that employee’s late cutoff |
| No absences in daytime preview | Intended: day has not closed. Use a prior eligible date or wait for the schedule |
| Manual correction conflict | Refresh and click the row’s Edit button; do not force a stale version |
| Report outdated after correction | Regenerate that date and affected weekly report; old S3 versions preserve earlier outputs |
| Raw photos remain | Inspect exact versions and Cleanup logs/alarms. Lifecycle is not an hourly deletion guarantee |

## Inspect processing without exposing photos or tokens

```powershell
aws sqs get-queue-attributes @awsArgs `
  --queue-url $outputs["DeadLetterQueueUrl"] `
  --attribute-names ApproximateNumberOfMessages --no-cli-pager
aws cloudformation list-stack-resources @awsArgs --stack-name $stack `
  --query "StackResourceSummaries[?ResourceType=='AWS::Lambda::Function'].{Name:LogicalResourceId,Function:PhysicalResourceId}" `
  --output table --no-cli-pager
```

Open the matching Lambda in CloudWatch Logs using an administrator/read-only monitoring identity if
this deployer lacks log-reading rights. Logs record operational error types, not raw faces or tokens.
DynamoDB Sessions provides session state and user-safe failure reasons. A raw photo may already
be deleted; a DLQ retry cannot recreate it. Inspect actual attendance before recapturing or correcting.

## Verify raw version removal

```powershell
aws s3api list-object-versions @awsArgs --bucket $outputs["RawBucket"] `
  --prefix "raw/" --max-items 20 --output json --no-cli-pager
```

This lists metadata only. Inspect pagination for a full audit. Both Versions and DeleteMarkers matter;
no current object alone is not proof that a versioned image was physically removed.

## Report handler test

Admin’s Generate report button is the simplest path. If invoking from CLI, first prepare explicit
JSON. This is a manual invocation, not proof that Scheduler fired:

```powershell
$reportDate = Read-Host "Closed report date YYYY-MM-DD"
$payload = @{ mode = "daily"; date = $reportDate } | ConvertTo-Json -Compress
[System.IO.File]::WriteAllText((Join-Path (Get-Location) "report-input.json"), $payload, [System.Text.UTF8Encoding]::new($false))
aws lambda invoke @awsArgs --function-name $outputs["ReportFunction"] `
  --payload fileb://report-input.json report-result.json --no-cli-pager
Get-Content report-result.json
```

Inspect invocation metadata for FunctionError as well as the returned body. Delete local private
report files or add them to .gitignore before publishing. Do not purge a queue to hide a failure.
