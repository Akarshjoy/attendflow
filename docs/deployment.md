# Rebuild AttendFlow from the ZIP — Windows / VS Code

Run commands from the **inner attendflow folder**. Keep one PowerShell terminal open;
variables in earlier steps are used later. Stop whenever a command fails.
No commands here require you to paste credentials into chat or into source files.

## 1. Open the folder and confirm tools

Extract the ZIP under Downloads. Open VS Code → File → Open Folder →
`Downloads\attendflow-system\attendflow`. Open Terminal → New Terminal.
Adjust this directory if your ZIP extracted elsewhere:

```powershell
cd "$env:USERPROFILE\Downloads\attendflow-system\attendflow"
$pythonDir = "$env:LOCALAPPDATA\Python\pythoncore-3.14-64"
$py = Join-Path $pythonDir "python.exe"
if (-not (Test-Path $py)) { throw "Set pythonDir to your Python 3.14 installation." }
$env:Path = "$pythonDir;$pythonDir\Scripts;$env:Path"
& $py --version
aws --version
sam --version
git --version
Test-Path .\scripts\build_template.py
$profile = "my-account"
$region = "us-east-1"
$stack = "attendflow"
$awsArgs = @("--profile", $profile, "--region", $region)
$projectArgs = @("--profile", $profile, "--region", $region, "--stack", $stack)
```

If Python is elsewhere, use its real directory. If SAM is missing, install the AWS SAM CLI
Windows installer from the official guide, then reopen VS Code and repeat the variable block.
No Docker is needed for this pure-Python build. Docker is optional for SAM local invocation.
Use a current SAM version supporting Python 3.14; do not only change generated template.json
if you intentionally change runtimes—update the generator and retest.

## 2. Confirm the account and check costs

```powershell
aws sts get-caller-identity @awsArgs --no-cli-pager
```

Confirm this is your intended account and a non-root deployer. If the profile is absent,
configure it with your administrator-approved credentials or SSO flow. Do not use a root key.
Previously exposed access keys must be revoked; never reuse a key pasted into a conversation.
Check Billing → Credits for your remaining balance, expiration and eligibility, and review
`docs/costs.md`. Paid-plan usage can exceed credits. Budget alerts do not stop spending.
This project does not require a training job or continuously running recognition endpoint.
Do not upgrade your account plan solely because a command fails; diagnose the service access error.

## 3. Install local dependencies and generate files

```powershell
& $py -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency install failed." }
& $py scripts/build_template.py
if ($LASTEXITCODE -ne 0) { throw "Template generation failed." }
& $py -m pytest tests -q
if ($LASTEXITCODE -ne 0) { throw "Fix failing tests before deployment." }
& $py scripts/deployment_policy.py @projectArgs
if ($LASTEXITCODE -ne 0) { throw "Policy generation failed." }
Get-ChildItem deployment-policy-*.json
```

The script writes multiple JSON policy files, split below the customer-managed policy size
limit. In IAM, an account administrator reviews each JSON under **Policies → Create policy → JSON**,
creates policies such as AttendFlowDeployer1/2/3, then attaches them to the deployer user or role.
Do not paste the entire set into a user inline policy; that has a smaller aggregate size limit.
The script does not attach anything. Existing DayOne policies do not automatically cover this stack.

The deployer can create scoped application roles and infrastructure; this is a powerful role,
not an end-user role. Organization permission boundaries/SCPs may still deny an action.
CreateEventSourceMapping requires wildcard resource scope with a function-ARN condition;
Get/Update/DeleteEventSourceMapping are separately allowed on mapping ARNs to avoid rollback failures.

## 4. Validate, build and deploy

```powershell
sam validate --lint --template-file template.json @awsArgs
if ($LASTEXITCODE -ne 0) { throw "Validation failed." }
sam build --template-file template.json
if ($LASTEXITCODE -ne 0) { throw "Build failed." }
sam deploy --guided --stack-name $stack @awsArgs `
  --template-file .aws-sam/build/template.yaml
```

| Prompt | Answer |
|---|---|
| Stack | `attendflow` (no slash or backslash) |
| Region | `us-east-1` |
| AdminEmail | Your operational alert inbox |
| BusinessTimezone | `Asia/Kolkata` for India |
| Confirm changes before deploy | Y |
| Allow SAM IAM role creation | Y after reviewing policies |
| Disable rollback | N |
| Save configuration | Y, `samconfig.toml`, `default` |
| Deploy changeset | Review then Y |

No SenderEmail or SESIdentityArn parameter is needed for this project. Confirm the SNS
subscription sent to AdminEmail. Wait for complete stack success, not just a resource’s success.
CloudFront deployment may take several minutes. If creation or rollback fails, use the
troubleshooting guide before repeating deployment or deleting anything.

## 5. Retrieve outputs, seed rules and publish the frontend

```powershell
$raw = aws cloudformation describe-stacks @awsArgs --stack-name $stack --output json --no-cli-pager
if ($LASTEXITCODE -ne 0) { throw "Could not retrieve stack outputs." }
$stackData = $raw | ConvertFrom-Json
$outputs = @{}
foreach ($item in $stackData.Stacks[0].Outputs) {
    $outputs[$item.OutputKey] = $item.OutputValue
}
$outputs
& $py scripts/setup.py @projectArgs seed
if ($LASTEXITCODE -ne 0) { throw "Seed failed." }
& $py scripts/setup.py @projectArgs configure
if ($LASTEXITCODE -ne 0) { throw "Frontend configuration failed." }
$webBucket = $outputs["WebBucket"]
aws s3 sync .\frontend "s3://$webBucket" @awsArgs --cache-control "max-age=60"
if ($LASTEXITCODE -ne 0) { throw "Frontend upload failed." }
Start-Process $outputs["PortalUrl"]
```

S3 stays private. Access the CloudFront HTTPS URL. Do not enable public bucket access or use
an HTTP S3 website endpoint. `frontend/config.js` contains public app identifiers, not secrets;
it is generated per environment and ignored by Git.

## 6. Create Admin and Kiosk accounts

```powershell
$adminEmail = (Read-Host "Admin invitation email").Trim()
& $py scripts/setup.py @projectArgs user --username admin --email "$adminEmail" --role Admin
if ($LASTEXITCODE -ne 0) { throw "Admin creation failed." }
$kioskEmail = (Read-Host "Kiosk operator invitation email").Trim()
& $py scripts/setup.py @projectArgs user --username kiosk --email "$kioskEmail" --role Kiosk
if ($LASTEXITCODE -ne 0) { throw "Kiosk creation failed." }
```

Use usernames **admin** and **kiosk**, and the temporary passwords emailed by Cognito.
The portal prompts for a new password. Temporary passwords expire after seven days.
Do not record these passwords in your demo. If an existing account matches, the script keeps it
and does not resend an invitation. If user creation succeeded but adding a group failed, fix
that exact group assignment in Cognito instead of creating another user.

Admin: creates directory employees, enrolls faces, reviews reports and makes audited corrections.
Kiosk: uses camera and sees only sessions it created. It cannot browse the employee directory.
Employees do not need individual Cognito logins in this version.

## 7. First demonstration

1. Admin → Employees → Add employee. Select today or an earlier true demo start date,
   working days including today, and an appropriate late cutoff in the business timezone.
2. If the person agrees, record consent. Otherwise leave consent unchecked and use Manual attendance.
3. Capture attendance → Register a face → choose employee → start camera → Enroll from camera.
4. Wait for Enrollment complete. An upload by itself does not prove enrollment succeeded.
5. In a separate browser profile sign in as kiosk. Capture Clock In; verify the actual record as admin.
6. Capture Clock Out, then review both times. Do not create duplicate captures while processing.
7. Generate a daily report to preview recorded attendance; absence marking waits until day close.
8. Follow `demo-guide.md` for late status, absences, reports and evidence.

## 8. Updates

Backend/infrastructure: run tests, regenerate template, validate, build, and `sam deploy` with
this stack/profile. Frontend: upload it separately; invalidate only this distribution if needed:

```powershell
aws cloudfront create-invalidation @awsArgs `
  --distribution-id $outputs["DistributionId"] --paths "/*"
```

Keep the original business timezone for an established dataset. Changing it requires a migration
plan for existing dates. Never overwrite another project’s stack, pool or frontend configuration.

## Official references

- https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html
- https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-deploy.html
- https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html
- https://docs.aws.amazon.com/service-authorization/latest/reference/list_lambda.html
