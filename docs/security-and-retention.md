# Security, consent and retention

## Employee choice

Explain what the system stores and why before enrollment. Record consent only when the employee
has agreed; do not mark the box merely to enable the camera. Employees can be created without
consent and use admin-recorded manual attendance. Withdrawal removes face matching eligibility
immediately and requests deletion of all associated Rekognition vectors. Attendance/audit history
remains; a separate organizational record-retention process governs it.

This is a technical demo, not a claim of legal compliance. Consult your organization’s applicable
privacy requirements before real employment use. Do not infer emotions, demographic attributes,
health or other personal characteristics from the photos; this application does not request them.

## What is stored

| Data | Where | Retention / removal |
|---|---|---|
| Raw enrollment/capture photo | S3 raw/ exact object version | Delete after terminal processing; cleanup every 5 minutes targets objects older than one hour |
| Raw fallback | S3 lifecycle current/noncurrent versions | One-day age-based fallback; asynchronous, not one-hour expiry |
| Face vector | Rekognition collection | Until enrollment removal/deactivation; orphan reconciliation after observation period |
| Session result | DynamoDB Sessions | ttl targets 24 hours; DynamoDB deletion is asynchronous |
| Directory and attendance | DynamoDB | Retained until deliberate administrative retention process |
| Audit events | DynamoDB Audit | Retained; ordinary table, not immutable storage |
| Daily/weekly reports | Versioned private S3 | Current copies retained; noncurrent copies expire after 30 days |
| Operational logs | CloudWatch | 14 days |
| Failed message metadata | SQS DLQ | 14 days, no raw image bytes |

Object version IDs matter: deleting without VersionId in a versioned bucket creates a delete marker
and can leave image bytes behind. The worker/cleanup delete actual versions. Check both current and
noncurrent versions when verifying removal. Raw-image deletion does not remove enrolled biometric
vectors. S3 versioning supports recovery/audit of reports, but is not WORM retention.

If cleanup fails, raw images can live longer than the one-hour target until recovery/lifecycle expiry.
Alarms and inspection are essential; no exact upper-bound deletion guarantee is claimed.
Consent-removal failure leaves matching disabled and a pending marker for cleanup retries.
Orphan face vectors from interrupted registration are observed, then deleted after an hour if still
unreferenced. Directory checks protect a successfully committed face from orphan cleanup.

## Access and browser behavior

- Admin/Kiosk accounts are created through the administrative CLI, not public registration.
- API Gateway verifies Cognito tokens; Lambda checks app client and groups.
- API uses ID tokens, held only in browser memory. Refreshing the page requires signing in again.
- Logout stops camera tracks and clears displayed records. Results clear automatically after 15 seconds.
- Kiosk tokens can create captures for any enrolled employee; use a trusted station/operator.
- A client-side interface hiding a button is not authorization: server role checks enforce access.
- Raw uploads use exact-key, content-type, maximum-size, encryption and expiry conditions.
- Private buckets require HTTPS; CloudFront uses OAC. No raw-photo download API exists.
- CSV names beginning with formula characters are neutralized.

## Known security boundaries

A printed photo or another screen can spoof the still-image flow. Face similarity is neither
liveness nor guaranteed identity. A legitimate match can fail in poor light; a wrong match is also
possible. Use a human correction path and never automatically penalize employees from this result.
Before unattended production use, add tested liveness, stronger authentication, station controls,
admin MFA, abuse controls, documented retention and organizational privacy review.
Rate limits help reduce load but do not provide a spending cap. The browser login flow does not
implement arbitrary MFA challenges; enabling MFA requires extending it or using managed login.
