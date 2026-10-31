# Cost model and optimization assessment

## Scope

This is a planning model for AttendFlow in us-east-1, not an observed bill,
current price quotation, budget enforcement mechanism or spending cap.

Rates below are explicit assumptions from the project cost model. Reconfirm
them on AWS pricing pages before procurement or a production forecast.
Credits, discounts, taxes, support plans and GitHub charges are excluded.

## Workload assumptions

- N daily employees, active on 30 days per month.
- Two attendance captures per employee per day.
- Ten REST API requests per employee per day.
- Two billable image-analysis operations per attendance capture.
- One stored face vector per employee.
- Lambda memory: 512 MB.
- Assumed average API execution: 0.25 seconds.
- Assumed average Recognition execution: 2 seconds.
- Assumed average Cleanup execution: 1 second.
- Assumed average Report execution: 10 seconds.
- 8,640 Cleanup and 65 Report invocations per modeled month.

Execution times are assumptions, not measured billed-duration results.
Retries, retakes and changes in API polling can increase usage.

## Unit-rate assumptions

| Item | Assumed USD rate |
|---|---:|
| Rekognition operation, each modeled group | 0.001 per operation |
| Stored face vector | 0.00001 per vector-month |
| Lambda x86 compute | 0.0000166667 per GB-second |
| Lambda requests | 0.20 per million |
| API Gateway REST requests | 3.50 per million |

## Formulas

captures = N × 30 × 2
API requests = N × 30 × 10
Rekognition recurring = captures × (0.001 + 0.001) + N × 0.00001
Initial enrollment = N × (2 × 0.001 + 0.001)

Lambda GB-seconds =
0.5 × [(API requests × 0.25) + (captures × 2) + 8640 + (65 × 10)]

Lambda requests = API requests + captures + 8640 + 65

## Monthly scenario estimates

| Component, USD | 10 daily employees | 500 daily employees | 5,000 daily employees |
|---|---:|---:|---:|
| Captures | 600 | 30,000 | 300,000 |
| Rekognition recurring | 1.2001 | 60.0050 | 600.0500 |
| Lambda compute and requests | 0.0961 | 0.9277 | 8.5642 |
| REST API requests | 0.0105 | 0.5250 | 5.2500 |
| Modeled recurring subtotal | 1.31 | 61.46 | 613.86 |
| One-time initial enrollment | 0.03 | 1.50 | 15.00 |

The recurring subtotal excludes DynamoDB requests/storage/PITR, S3
storage/requests/versioning, CloudFront transfer, Cognito, SQS, SNS,
CloudWatch logs/alarms/dashboard, tracing and scheduling.

DynamoDB scans, growing attendance/audit history and report data require
explicit modeling as the application grows. Cognito pricing depends on the
actual tier, monthly active users and authentication configuration.

Earlier provisional monthly budgets of USD 15 / 100 / 800 included rough
allowances for omitted services. Those allowances were not itemized estimates
and must not be presented as guaranteed bills.

## Sensitivity

At 5,000 employees, 10% more complete attendance captures adds approximately
USD 60 in Rekognition operations under these rate assumptions, before other
service charges.

A 50 requests/second API throttle does not cap monthly expenditure.

## Optimization assessment

Implemented controls include short-lived raw-image handling, 14-day log
retention and PAY_PER_REQUEST tables. Their purpose includes privacy and
operational control; no measured dollar savings are claimed.

The throttle change improved the tested request success rate. It is a capacity
change, not evidence of reduced cost.

A measured cost-optimization experiment remains outstanding. A suitable next
experiment is safe AWS-client connection reuse, measured against equivalent
requests and billed duration. Preserve separation between DynamoDB resource
serialization and low-level transaction clients.

Do not remove image quality or consent checks to manufacture savings.

## Pricing references

- https://aws.amazon.com/rekognition/pricing/
- https://aws.amazon.com/lambda/pricing/
- https://aws.amazon.com/api-gateway/pricing/
- https://aws.amazon.com/dynamodb/pricing/
- https://aws.amazon.com/cloudwatch/pricing/
