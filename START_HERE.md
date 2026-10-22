# Start here — AttendFlow

This is a separate project. It does not change DayOne, Smart Leave or TalentFlow.

1. Extract `attendflow-system.zip` and open the inner `attendflow` folder in VS Code.
2. Read `docs/deployment.md`. Use its commands in order, in one PowerShell terminal.
3. Install Python 3.14, AWS CLI v2 and AWS SAM CLI if missing. Match the Lambda runtime.
4. Run local tests, generate the deployment policies and have an administrator review them.
5. Build and deploy the **attendflow** stack in **us-east-1**. This creates billable AWS resources.
6. Run setup: seed rules, configure the frontend, upload it, then create your Admin and Kiosk accounts.
7. Use consenting adults for the demo. Enroll through the admin portal, then clock in/out through the kiosk.
8. Follow `docs/demo-guide.md` to collect real evidence. Local tests are simulations, not a live AWS demo.

No custom ML training, Comprehend endpoint or reserved Lambda concurrency is required.
This package has not been deployed into your account. Account policies, regional access,
quotas and real recognition latency must be checked during your deployment.

## Read these next

- `docs/deployment.md` — exact PowerShell commands, configuration and first login.
- `docs/design.md` and `docs/architecture.svg` — technical design and architecture.
- `docs/schema.md` — tables, keys and fields.
- `docs/demo-guide.md` — demo sequence and acceptance checks.
- `docs/costs.md` — 100 employees, two captures/day; actual Rekognition API count.
- `docs/troubleshooting.md` — common problems, including image removal and permissions.
- `docs/security-and-retention.md` — consent, data deletion, access and limitations.
- `docs/cleanup.md` — stop resources when finished, with explicit deletion steps.

**Important:** an image match is not liveness verification. The demo can be fooled by a photo.
Do not use it as an unattended security control, payroll authority or automatic disciplinary system.
Admin-reviewed manual attendance is built in.
