# Cleanup and GitHub publishing

## Save source and evidence first

Keep your corrected source in GitHub and real demo evidence privately. Never commit passwords,
AWS keys, raw photos, tokens, signed URLs or private employee reports. The provided .gitignore
excludes SAM artifacts, local configuration, policy JSON and the private live-evidence directory.
Review staged changes; .gitignore does not remove files already tracked.

```powershell
git init -b main
git add .
git --no-pager diff --cached --stat
git --no-pager diff --cached --check
git commit -m "Add AttendFlow serverless attendance system"
```

Run git init only for a folder not already in Git. In VS Code use Source Control → Publish to GitHub,
or connect your existing remote. Publishing source does not stop AWS resources or hosting charges.

## When the demo is finished

Before deleting the stack, use the portal to remove enrolled faces for every demo employee.
Wait for pending removals to complete, check the raw capture bucket’s versions and save any required
reports. Confirm the account, region and stack; never run cleanup for another project.

**The following deletes the application infrastructure. Run only when you intend to stop it.**

```powershell
aws sts get-caller-identity @awsArgs --no-cli-pager
sam delete --stack-name $stack @awsArgs
```

Deletion may take time, especially for CloudFront. Fix a DELETE_FAILED cause rather than force
retaining more resources without understanding what remains.

## Retained resources need a separate decision

The template intentionally retains DynamoDB tables, Cognito user pool, S3 buckets and the
Rekognition collection to prevent accidental data loss. Stack deletion does not remove them.
Retained images/vectors/data can continue to incur charges and require privacy review.
Export the physical resource inventory before deletion:

```powershell
aws cloudformation list-stack-resources @awsArgs --stack-name $stack `
  --output json --no-cli-pager > retained-resource-inventory.json
```

For each retained resource, decide whether to archive or deliberately remove it:

- Rekognition: after confirming the exact project collection and no needed enrollment,
  delete that collection in the console/API. Do not delete another project’s collections.
- Raw S3: delete **all versions** and delete markers, not just current objects, then the empty bucket.
- Report/Web S3: preserve necessary reports/source, then delete versions and bucket when approved.
- DynamoDB: review attendance/audit retention needs before deleting each named table.
- Cognito: remove this project’s user pool only when these logins are no longer needed.
- Logs/SNS/alarms/queues/schedules: verify CloudFormation deleted them; investigate retained failures.

No broad account-wide deletion script is supplied. In Billing/Cost Explorer verify that usage stops;
metrics and billing data can lag. A deleted GitHub repository or a closed VS Code window does not
remove AWS infrastructure. An old retained captures bucket with the deterministic name can block
redeployment of the same stack name until it is deliberately reused/imported or removed.
