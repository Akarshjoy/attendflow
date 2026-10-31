# Security and IAM review

## Authentication and authorization

The proxy ANY method uses a Cognito user-pool authorizer. OPTIONS is
unauthenticated for browser preflight.

Missing-token and invalid-token probes both returned HTTP 401. Backend source
also checks the application client, groups and session ownership.

Admin and Kiosk responsibilities are separated server-side. Tokens are held in
browser memory. The current browser authentication flow does not implement
arbitrary MFA challenges.

## IAM before and after

| Area | Baseline | Change / verified position |
|---|---|---|
| Lambda execution roles | Explicit roles already existed | Preserved; generic scoping helper changed zero AttendFlow roles |
| Scheduler trust | Scheduler principal with account condition | Added restriction to this region/account's default schedule group |
| Trace publishing | Existing helper manages trace-write policy | PutTraceSegments and PutTelemetryRecords available to explicit roles |
| Deployment role | Could deploy functions but could not read new layer | Added GetLayerVersion for pinned OpenTelemetry layer version 32 |
| GitHub federation | OIDC provider had a leading tab in audience | Corrected audience; successful federated deployments subsequently observed |

Do not describe the generic role-scoping helper as a completed before/after
least-privilege transformation for AttendFlow. A full effective-permissions
audit has not been demonstrated.

## Runtime permission boundaries

The reviewed role statements separate API, Recognition, Cleanup and Report
responsibilities. They scope table, bucket/prefix, queue, collection and
function access according to those responsibilities.

Examples:

- API accesses application tables, creates constrained raw uploads, reads
  reports and invokes Report.
- Recognition reads exact raw image versions, consumes its queue and performs
  face operations and attendance/session transactions.
- Cleanup scans/reconciles application state, removes raw versions and
  reconciles face vectors.
- Report reads directory/configuration data and writes attendance/report data.
- Scheduler invokes Report and can deliver failures to its configured queue.

Remaining wildcard resources include X-Ray publishing and Rekognition
DetectFaces, which require service-specific treatment. Wildcards must be
explained action by action, rather than removed mechanically.

## Pinned layer deployment permission

Role: GitHubAttendFlowDeploy
Inline policy: AttendFlowOpenTelemetryLayerRead

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "ReadPinnedOpenTelemetryLayer",
    "Effect": "Allow",
    "Action": "lambda:GetLayerVersion",
    "Resource": "arn:aws:lambda:us-east-1:615299751070:layer:AWSOpenTelemetryDistroPython:32"
  }]
}
```

This policy was applied through CloudShell. It is a deployment-role permission,
not an application runtime permission. A future layer-version change requires
reviewing this policy as well as the template. Preserve this policy when
recreating the deployment role.

## Storage protection

- All five DynamoDB tables were observed ACTIVE with deletion protection true.
- PITR, encryption and retention settings were checked during hardening.
- S3 public-access blocking, encryption and versioning were checked.
- The web origin is private and uses CloudFront origin access control.
- TLS-only bucket access and constrained upload conditions are part of the design.

Deletion protection does not prevent authorized item deletion and is not a
substitute for a tested restore procedure.

## Consent and retention

| Data | Handling |
|---|---|
| Raw image | Exact version deleted after terminal processing |
| Cleanup target | Objects older than one hour; cleanup scheduled every five minutes |
| Raw lifecycle fallback | One-day age-based current/noncurrent expiration; asynchronous |
| Face vector | Removed through enrollment-removal/deactivation workflow |
| Session | Approximately 24-hour TTL target; asynchronous deletion |
| Attendance and audit | Retained until an administrative retention process acts |
| Reports | Current versions retained; noncurrent versions expire after 30 days |
| Lambda logs | 14 days |
| DLQ metadata | 14 days; no raw image bytes intended |

Cleanup failure can extend raw-image retention. S3 deletion without VersionId
may leave old image bytes behind; verification must inspect actual versions.
Removing images does not remove enrolled face vectors.

## Trusted Advisor evidence

The supplied refreshed views showed:

- Root-account MFA enabled.
- S3 bucket-permissions check green, with 17 listed items.
- EBS and RDS public-snapshot checks green, with zero public snapshots shown.
- Specific unrestricted-security-group-ports check green, with zero items shown.

These are account-level selected checks. Individual S3 rows were not included
in the supplied screenshot. Root MFA does not establish Cognito Admin MFA,
and a green security-group check is not a complete network review.

## Known limitations

Still images can be spoofed by photographs or screens. Similarity is not
liveness or guaranteed identity. False matches and false rejections are possible.

Human correction, consent, manual alternatives, stronger administrator
authentication, station controls and organizational retention/privacy review
remain necessary before real employment use. No legal-compliance certification
or biometric-accuracy claim is made.
