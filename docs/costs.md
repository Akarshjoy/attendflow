# AWS cost sheet — 100 employees, two attendance captures/day

Planning date: 16 October 2026. Region: us-east-1. Currency: USD, before taxes, credits or discounts.
Use your actual account’s AWS Pricing Calculator before deployment. This is not a spending cap.

## Count captures and API operations separately

100 employees × 2 captures/day × 30 days = **6,000 attendance captures/month**.
Each successful capture calls DetectFaces and SearchFacesByImage: **12,000 analysis operations**.
A statement of “2 calls/day per employee” is only correct if “call” means an attendance event;
the implementation needs **4 Rekognition API operations/day per employee**.

Using the published first-tier example rates of $0.001 per Group 1 or Group 2 operation,
and $0.00001 per stored face vector/month:

| Rekognition component | Quantity | Unit price | Estimated cost |
|---|---:|---:|---:|
| Attendance DetectFaces (Group 2) | 6,000 | $0.001 | $6.00 |
| Attendance SearchFacesByImage (Group 1) | 6,000 | $0.001 | $6.00 |
| One face vector for each employee | 100/month | $0.00001 | $0.001 |
| **Recurring Rekognition subtotal** | | | **$12.001 (~$12.00)** |
| Initial enrollment DetectFaces | 100 once | $0.001 | $0.10 |
| Initial enrollment duplicate-face search | 100 once | $0.001 | $0.10 |
| Initial enrollment IndexFaces | 100 once | $0.001 | $0.10 |
| **First month including all 100 enrollments** | | | **$12.301 (~$12.30)** |

For **22 working days**, recurring recognition is 4,400 × 2 × $0.001 + $0.001 = **$8.801**.
If the assignment literally allows only 6,000 total billed recognition operations, its analysis
subtotal would be $6, but that is not this two-operation-per-capture implementation.
Retakes, retries, extra enrollments and rejected captures add operations; a no-face rejection
normally uses only DetectFaces. No custom training or continuously provisioned endpoint is used.

## Supporting services — add these to the calculator

The figures above are the requested Rekognition cost sheet, not the complete AWS account bill.

| Service | Inputs to estimate |
|---|---|
| API Gateway | One session creation + polling requests per capture; assume 5 polls = 36,000 requests/month, plus admin requests |
| Lambda | API/recognition calls, reporting and 8,640 five-minute cleanup invocations per 30 days; actual duration × 512 MB |
| DynamoDB | Employee/session reads, transaction writes (higher unit cost), reports, scans, storage and PITR |
| S3 | 6,000 capture PUTs/deletes/GETs, version listings, report/frontend storage and requests |
| SQS | Upload sends, receive/delete calls, retries and polling |
| EventBridge / Scheduler | Cleanup events and daily/reconcile/weekly scheduled deliveries |
| Cognito | Monthly active Admin/Kiosk users, not automatically all 100 employees |
| CloudFront | Frontend HTTPS requests and outbound transfer |
| CloudWatch / SNS | Logs, **5 alarms**, optional alert email deliveries |

Do not assume these are all free. Fixed monitoring charges can matter for a small demo. Your
other AWS projects also consume credits. Check Bills, Cost Explorer and Credits regularly, and
remove unneeded resources after collecting evidence. A budget alert warns; it does not stop usage.

## Recalculate

```powershell
python scripts/estimate_cost.py --employees 100 --days 30 --captures-per-day 2
```

The script makes no AWS calls and does not create resources. Change rates explicitly when AWS
pricing changes; they are inputs, not guaranteed future prices.

## Source

https://aws.amazon.com/rekognition/pricing/ — Group 1/2 operation definitions, first-million-image
example rates and face-vector storage example. Multiple APIs on one image are separately charged.
Verify the regional pricing table/calculator and credit eligibility for your account before spending.
