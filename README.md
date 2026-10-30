# AttendFlow — Serverless Attendance with Face Recognition

A standalone AWS attendance demonstration: register consenting employees, capture a
single face through a browser, record clock-in/clock-out, and review daily and weekly summaries.

![Architecture](docs/architecture.svg)

## What is included

- Responsive Admin and Kiosk views, Cognito authentication and first-login password change.
- Private direct-to-S3 image uploads using a bounded, short-lived presigned POST policy.
- S3 → SQS → Lambda recognition, single-face/quality checks and Rekognition collection search.
- Explicit Clock In/Clock Out actions; server timestamps, employee schedules and late status.
- Atomic attendance/session/audit writes with optimistic concurrency and retry protection.
- Daily absence close at 23:59, next-day reconciliation at 00:10, weekly reports Monday 01:00.
- Employee/date/status filters, CSV export, report downloads and audited manual corrections.
- Consent recording/revocation, physical raw-image version deletion and periodic cleanup.
- SAM infrastructure, least-scope runtime policies, operational alarms and a dead-letter queue.
- Local tests, deployment guide, technical design, cost model and demo checklist.

## Quick start

Read [START_HERE.md](START_HERE.md), then [the deployment guide](docs/deployment.md).
Use a new stack named `attendflow`. Do not deploy this template over another project.

```powershell
python -m pip install -r requirements-dev.txt
python scripts/build_template.py
python -m pytest tests -q
sam validate --lint --template-file template.json --profile my-account --region us-east-1
sam build --template-file template.json
sam deploy --guided --stack-name attendflow --template-file .aws-sam/build/template.yaml --profile my-account --region us-east-1
```

A successful CloudFormation deployment is only the infrastructure step. Seed policy,
configure/upload frontend, and create users as described in the guide.

## Services and responsibilities

| Service | Responsibility |
|---|---|
| Amazon Rekognition | Detect a face, index employee face vectors, search for a match |
| AWS Lambda | API validation, recognition, cleanup and reports |
| Amazon S3 | Private temporary images, versioned reports and frontend assets |
| Amazon DynamoDB | Employees, daily attendance, sessions, policy and audit history |
| Amazon API Gateway | Cognito-protected application routes |
| Amazon Cognito | Admin and Kiosk user accounts |
| Amazon CloudFront | HTTPS delivery of the private S3 website; browser camera requires a secure origin |
| Amazon SQS | Buffer uploads; retry failures and retain exhausted events in a DLQ |
| Amazon EventBridge / Scheduler | Five-minute cleanup and timezone-aware daily/weekly schedules |
| Amazon CloudWatch | Logs, error alarms and DLQ monitoring |
| Amazon SNS | Operational alert emails to the administrator |
| AWS IAM | Runtime roles and deployment permissions |
| AWS CloudFormation | Provision and update the SAM stack |

SAM, AWS CLI, Python and VS Code are development/deployment tools. This project does
not use Step Functions or a custom trained model. Cognito sends its user invitations;
there is no separate SES application notification feature.

## Functions

| Logical function | Handler | Trigger |
|---|---|---|
| ApiFunction | `app.api` | API Gateway |
| Recognition | `app.ingest` | SQS upload messages |
| Report | `app.report` | Scheduler or authenticated admin regeneration |
| Cleanup | `app.cleanup` | EventBridge every five minutes |

## Important design decisions

- One employee/day row, one clock-in and one clock-out; no overnight shifts or lunch punches.
- Business timezone defaults to Asia/Kolkata. Change it at deployment before collecting records.
- Kiosk is a trusted operator account; it can capture attendance, not list all employees or edit records.
- Employees can use manual attendance without consenting to face enrollment.
- Late employees count as attended in `present_pct`; the separate late percentage is also reported.
- S3 lifecycle cannot implement a one-hour TTL. Explicit version deletion plus scheduled cleanup
  implements a best-effort short retention target; daily lifecycle expiry is only a fallback.
- Three seconds is a measured target, not a guarantee. The portal handles delayed results and
  can recheck the latest capture. Queueing, network and cold starts affect latency.
- Report generation scans the small employee directory and queries daily records. This is a
  100-employee demonstration, not a large-workforce analytics design.

## Deliverables

| Requested deliverable | Location / completion step |
|---|---|
| Technical design and architecture diagram | `docs/design.md`, `docs/architecture.svg` |
| Face registration → clock-in → clock-out video | Follow `docs/demo-guide.md`; record your actual deployment |
| GitHub repository with instructions | This source package and `docs/deployment.md`; publish after reviewing staged files |
| AWS cost sheet | `docs/costs.md`; reproducible arithmetic in `scripts/estimate_cost.py` |

## Validation and limits

See `docs/validation.md`. Automated tests use Moto for AWS storage and stub ML responses;
they cannot establish biometric accuracy, anti-spoofing, IAM authorization in your account,
or real-world latency. No live AWS deployment or video is claimed by the source package.

Use a consenting demonstration group. A still photograph can spoof matching; liveness,
production privacy governance, payroll integration, shifts, PTO integration and multi-region
operation are outside this version. Review any match error with a human before changing
an employee’s attendance or making an employment decision.


[![AttendFlow CI-CD](https://github.com/Akarshjoy/attendflow/actions/workflows/attendflow.yml/badge.svg?branch=production-hardening)](https://github.com/Akarshjoy/attendflow/actions/workflows/attendflow.yml)


<!-- ATTENDFLOW_DEPLOY_TRIGGER -->
### Requesting deployment

Pushes run the build and tests. On `production-hardening`, a commit message beginning with `[deploy-attendflow]` also requests deployment of the tested SAM artifact. Deployment depends on the checks job succeeding. Manual dispatch with `deploy=true` is also supported when available.
