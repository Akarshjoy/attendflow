# AttendFlow cost planning

Date: 2026-10-31
Region: us-east-1
Currency: USD

## Assumptions

30 days/month, two captures and ten API requests per employee/day.
One face vector per employee. All four Lambdas use 512 MB, x86_64.

Assumed average billed duration:
API 0.25 seconds; recognition 2 seconds; cleanup 1 second;
report 10 seconds. These are assumptions, not load-test measurements.

Monthly scheduled workload:
8,640 cleanup invocations and approximately 65 report invocations.

## Monthly estimate

| Component | 10 daily employees | 500 | 5,000 |
|---|---:|---:|---:|
| Rekognition | $1.20 | $60.01 | $600.05 |
| Lambda requests and compute | $0.10 | $0.93 | $8.56 |
| REST API requests | $0.01 | $0.53 | $5.25 |
| Subtotal, rounded after summing | $1.31 | $61.46 | $613.86 |
| Provisional other-service allowance | $10 | $30 | $150 |
| Rounded planning budget | $15 | $100 | $800 |

Initial enrollment adds approximately $0.03 / $1.50 / $15 in
Rekognition charges respectively.

## Calculation

Captures = employees * 30 * 2.
API requests = employees * 30 * 10.

Rekognition = captures * 0.002 + employees * 0.00001.
REST API requests = API requests * 3.50 / 1,000,000.

Lambda invocations = API requests + captures + 8,640 + 65.
Lambda GB-seconds =
  0.5 * (API requests * 0.25 + captures * 2 + 8,640 + 65 * 10).
Lambda cost =
  GB-seconds * 0.0000166667 + invocations * 0.20 / 1,000,000.

## Limits and cost controls

Other-service allowances are provisional, not itemized calculations.
They cover DynamoDB/PITR, S3, CloudFront/data transfer,
CloudWatch/X-Ray, Cognito, SQS, SNS and scheduling.

Actual costs depend on retained data, cleanup scans, log volume,
authentication usage, retries and traffic. Budgets are not spending caps.
No free-tier benefits, credits, discounts, tax or paid support included.
GitHub Actions charges, if applicable, are separate.

Existing controls include raw-image deletion/lifecycle, 14-day logs,
session TTL and on-demand DynamoDB.
Attendance and Audit have no configured TTL; their storage can grow.

The throttle increase improved performance. No measured cost saving
has been established.

## Sources

https://aws.amazon.com/rekognition/pricing/
https://aws.amazon.com/lambda/pricing/
https://aws.amazon.com/api-gateway/pricing/