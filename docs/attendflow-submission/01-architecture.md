# AttendFlow architecture and application design

## Purpose

AttendFlow is a consent-based attendance demonstration. Administrators manage
employees, review attendance, record manual corrections and retrieve reports.
Kiosk users submit attendance captures through a restricted interface.

Manual attendance provides an alternative to face-based attendance.

## Components

| Component | Responsibility |
|---|---|
| Private Web S3 bucket and CloudFront | Deliver the browser application |
| CloudFront origin access control | Authorize access to the private web origin |
| Cognito user pool | Authenticate Admin and Kiosk users |
| API Gateway REST API | Validate Cognito tokens and route requests |
| ApiFunction | Enforce application authorization and handle API operations |
| Raw S3 bucket | Temporarily hold uploaded image versions |
| Upload SQS queue | Deliver capture work to Recognition |
| Recognition Lambda | Validate images, match/enroll faces and update state |
| Rekognition collection | Store enrolled face vectors and support matching |
| DynamoDB | Store employees, attendance, sessions, policy and audit records |
| Cleanup Lambda | Reconcile expired work, raw versions and orphaned vectors |
| Report Lambda | Generate attendance reports |
| EventBridge Scheduler | Trigger daily, reconciliation and weekly reports |
| Reports S3 bucket | Store private report objects |
| CloudWatch, SNS and X-Ray | Provide operational visibility and alerts |

## Intended processing flow

1. The user authenticates through Cognito.
2. API Gateway validates the token.
3. ApiFunction checks application-client and role requirements.
4. A capture session provides a constrained upload authorization.
5. The browser uploads an image to the private Raw bucket.
6. An S3 notification reaches the upload queue.
7. Recognition retrieves the exact image version and applies validation.
8. Rekognition operations support enrollment or attendance matching.
9. Conditional and transactional writes update application records.
10. Terminal processing removes the relevant raw image version.
11. The browser polls session state and displays the result.

This describes the implementation design. It is not proof that every step has
passed a live acceptance test.

## Data model

| Table | Purpose |
|---|---|
| Employees | Directory, active status, consent and face association |
| Attendance | Employee/date attendance records |
| Sessions | Capture ownership, processing state and expiry |
| Config | Attendance policy and coordination records |
| Audit | Application change history |

Tables use PAY_PER_REQUEST billing. Sessions has a TTL attribute named ttl;
TTL deletion is asynchronous. Audit is an ordinary DynamoDB table, not
immutable or WORM storage.

## Runtime configuration

All four functions use Python 3.14, x86_64 and 512 MB memory.

| Function | Timeout |
|---|---:|
| ApiFunction | 29 seconds |
| Recognition | 60 seconds |
| Cleanup | 120 seconds |
| Report | 120 seconds |

Cleanup runs every five minutes. Reporting schedules are daily at 23:59,
reconciliation at 00:10, and weekly on Monday at 01:00, interpreted using the
configured business timezone.

## Trust boundaries

The browser is untrusted. Server authorization, session ownership, employee
eligibility and consent checks govern operations. Hiding controls in the UI
does not provide authorization.

Images, biometric vectors, attendance records and operational telemetry have
different purposes and retention rules. See the security document.
