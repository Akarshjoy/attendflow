# Validation record and live acceptance gates

## Local verification completed on 16 October 2026

- Python test suite: Moto-backed storage/transaction tests and stubbed ML responses.
- `cfn-lint`: generated SAM template passed.
- Official SAM translator: template transformed into 52 CloudFormation resources; transformed
  template also passed cfn-lint. Packaging validation used a synthetic S3 code URI locally;
  no deployment or AWS calls were made for this check.
- Explicit Lambda roles verified; no broad SAM-managed SQS execution policy was injected.
- JavaScript syntax check passed.
- JSDOM frontend smoke check passed: Admin login, directory rendering, enrollment selection,
  attendance table/statistics, logout clearing and Kiosk view restrictions.
- Cost arithmetic script produced 6,000 captures, 12,000 analysis operations and $12.001 recurring
  Rekognition subtotal under its documented assumptions.

The test count/result is recorded in the package’s `TEST_RESULTS.txt` after the final run.
Local testing used Python 3.12; deployed runtime is Python 3.14. These pure-Python tests must be
rerun in your own Python 3.14 environment before deployment, as shown in deployment.md.

## Reproduce

```powershell
python scripts/build_template.py
python -m pytest tests -q
sam validate --lint --template-file template.json --profile my-account --region us-east-1
sam build --template-file template.json
```

Optional frontend DOM checks require Node.js 24+ (not needed by the deployed static site):

```powershell
npm install
npm run test:frontend
```

The DOM test mocks Cognito/API calls. It is not a browser camera, network, pixel-layout or live
AWS integration test. A local Chromium test could not be run in the build environment because
the browser binary was unavailable. Browser camera/HTTPS/CORS behavior remains a live gate.

## Coverage

| Area | Covered locally |
|---|---|
| Time policy | UTC/local date boundary, cutoff equality, late status, holidays, weekdays, employment bounds |
| Attendance | In/out order, duplicate rejection, absent replacement, transaction rollback, exactly-one session/audit commit |
| Concurrency | Optimistic row/session conditions and stale employee consent; not a load test |
| Recognition gate | Face count, quality, pose, similarity, ambiguity, current FaceId mapping using stub responses |
| Enrollment | Consent enforcement, vector mapping and removal using stub Rekognition |
| Privacy cleanup | Actual S3 versions deleted under Moto, replay version isolation, active lease image preservation, orphan vector reconciliation |
| Security | Role restrictions, app-client check, session ownership, CSV formula neutralization |
| Reports | Idempotent absence creation, no overwriting presence, daytime preview behavior, holiday exclusion |
| UI | Mocked login/data rendering and role controls in JSDOM |

## Must still be verified in your AWS deployment

- AWS account/region service access and all IAM actions during stack create/update/delete.
- Actual Cognito invitation delivery and password-change flow.
- Webcam permission, upload CORS, S3 notifications and SQS event-source mapping.
- Real Rekognition enrollment/matching with consenting participants; no accuracy claim from mocks.
- Cold and warm end-to-end response times; explicitly report whether the three-second goal is met.
- Current and noncurrent raw photo deletion, cleanup failures/alerts, face removal in the collection.
- Daily/weekly schedules, DLQ failure recovery and actual report downloads.
- Admin correction audit records and retained-resource cleanup.

The app is a deployable demonstration implementation, not a certified biometric or payroll product.
A generated architecture or passing unit suite is not evidence that a real employee was recognized.
