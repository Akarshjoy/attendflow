# Live demo and evidence checklist

Use a consenting adult demo group and fictional employee details. Record only the app, relevant
AWS resources and your own demonstration images; hide passwords, access keys, tokens and signed URLs.
Do not describe local mock tests as a real recognition demonstration.

## Before recording

- Stack CREATE_COMPLETE/UPDATE_COMPLETE, correct CloudFront URL and seed/configure complete.
- Admin and Kiosk can log in with changed passwords; SNS alert subscription confirmed.
- Webcam permission granted in the HTTPS portal. Laptop/mobile browser camera APIs need a secure origin.
- Employee scheduled for today, start_date <= today, no configured holiday today.
- The person voluntarily agrees to enrollment. Choose Admin → Employees and record consent.

## Suggested 3–5 minute recording

1. **Explain the system (20 seconds).** “An authorized kiosk captures a photo. AWS checks the face
   against the registered collection and records a server timestamp. The admin can review and correct it.”
2. **Registration (40 seconds).** Create a demo employee, show schedule/cutoff, choose the employee
   in Register a face and enroll from the live camera. Wait for Enrollment complete.
3. **Clock-in (30 seconds).** Sign in as Kiosk in a separate browser profile. Select Clock In and
   capture. Show the real name, time, status and measured duration. If processing is slow, leave the
   recording honest; do not claim the target was achieved if it was not.
4. **Clock-out (30 seconds).** After clock-in succeeds, select Clock Out and capture again.
5. **Admin review (40 seconds).** Filter by employee/date. Show clock-in, clock-out, status and source.
   Download the CSV. Explain that a late arrival still counts toward attendance percentage.
6. **Summary (40 seconds).** Generate a daily preview and open its JSON link. Explain that daytime
   previews do not mark absent employees. Show a prior closed day and weekly report if available.
7. **Limits (20 seconds).** “The photo is removed after processing, but an enrolled face vector remains
   until removal. This demonstration does not include liveness; manual correction is available.”

## Daily absence demonstration without waiting until midnight

Create a clearly marked **manual-only demo employee** whose start date includes yesterday and whose
schedule includes yesterday. Do not invent clock-ins. Admin → Reports → choose yesterday → Daily →
Generate → refresh the list. The report function should create an absent row for that eligible day.
Describe this accurately as a **manual report/backfill invocation**, not proof that the schedule fired.
To prove scheduling, inspect the real Scheduler target and Report Lambda logs after its scheduled run.

For a weekly demonstration choose an end date whose prior six days overlap demo employment. Days
before start_date and nonworking days must not count as absent. Monday’s scheduled report ends Sunday.

## Required checks and expected results

| Check | Expected result | Evidence to save |
|---|---|---|
| Enroll one clear face | FaceId linked to employee UUID | Enrollment result, directory entry |
| No face / multiple faces | Rejected, no attendance | Portal message and unchanged records |
| Unregistered face | No confident match | Portal message; use consenting participant |
| Clock-in then clock-out | One daily row with two increasing UTC timestamps | Portal + DynamoDB row |
| Duplicate clock-in | Rejected, original timestamp unchanged | Before/after row |
| Clock-out without in | Rejected | Portal message |
| Late arrival | Late status based on business timezone cutoff | Schedule, result |
| Nonworking day/holiday | No attendance write | Policy and result |
| Day close repeated | No duplicate absence row or overwrite of attendance | Report rerun and row |
| Consent withdrawn | Face no longer matches directory; manual option remains | Employee state, collection inspection |
| Raw image deleted | Exact captured VersionId absent, not only hidden by delete marker | S3 versions/API check |
| Kiosk opens admin endpoint | 403 | Network/API result without token disclosure |
| Manual correction | Reason, actor, before/after audit and new version | Audit table excerpt with private data redacted |
| Three-second target | Measured duration, not an assertion | Latency observations with cold/warm labels |

## Performance worksheet

Create a private record of capture type, network, image size, cold/warm state, duration, outcome and
any error. Report sample size and median/maximum; for a small sample avoid claiming a meaningful p95.
Processing may exceed three seconds due to S3 event delivery, SQS polling, cold starts and API latency.
Provisioned capacity or an alternative synchronous processing design needs a separate cost review.

## Submission folder

- Technical design: `design.md` + `architecture.svg`.
- Data model: `schema.md`.
- Video: real face registration → clock-in → clock-out → summary.
- Screenshots: actual UI, attendance row, Rekognition collection metadata, daily/weekly report,
  and version-deletion evidence. Never submit raw biometric photos as a public dataset.
- Cost sheet: `costs.md` and output of `scripts/estimate_cost.py`.
- Repository: source, tests and deployment instructions. Private evidence goes under
  `docs/live-evidence/` (ignored by Git). Export redacted copies deliberately if required.
