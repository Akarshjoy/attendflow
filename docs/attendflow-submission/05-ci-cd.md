# CI/CD and deployment controls

Repository: https://github.com/Akarshjoy/attendflow
Workflow: .github/workflows/attendflow.yml
Deployment branch: production-hardening

## Build and validation

The workflow:

1. Checks out the commit without persisting Git credentials.
2. Configures Python 3.14, Node.js 24 and SAM CLI 1.166.2.
3. Installs Python test dependencies and runs npm ci.
4. Generates the template, validates it with linting and runs sam build.
5. Runs backend pytest and frontend smoke tests.
6. Archives the successful SAM build.
7. Uploads a commit-specific artifact with seven-day retention.

An earlier local backend run passed all 54 tests. Frontend smoke evidence
covered Admin login, employee rendering, enrollment selection, attendance
filters/table, logout clearing and Kiosk-role UI behavior.

Mocks and DOM checks do not establish live camera or recognition accuracy.

## Deployment conditions

Deployment requires the checks job to succeed and the production-hardening
branch. It is triggered by either:

- A push whose head commit message starts with [deploy-attendflow]; or
- A workflow_dispatch request with deploy=true.

Manual dispatch availability in the GitHub UI also depends on GitHub's
default-branch workflow requirements.

Deployment concurrency uses a shared production group with cancellation disabled.
The deploy job restores the commit-specific tested artifact, obtains AWS
credentials through OIDC and runs scripts/ci_deploy.py with existing stack
parameters.

Documentation commits without the deployment prefix run checks but do not meet
the push deployment condition.

## OIDC

The role trust restricts audience to sts.amazonaws.com and subject to:

repo:Akarshjoy@223323475/attendflow@1429151715:ref:refs/heads/production-hardening

A leading tab in the identity provider audience originally prevented token
validation. Correcting it enabled successful role assumption and deployment.

Changing branches or introducing a GitHub environment can alter the subject.
Review the trust policy alongside such workflow changes.

## Verified failed-test gate

Commit ad4772c introduced an intentional failing test with a deployment-prefixed
commit message. The observed run reported 1 failed and 54 passed tests.
Deployment was skipped.

The demonstration test was removed in commit 6d999a5. Tests passed again.

Evidence:
https://github.com/Akarshjoy/attendflow/actions/runs/41183342255

The failed run is retained as evidence; the failing test is not part of the
current intended test suite.

## OpenTelemetry deployment

Commit 616aa8e added the pinned layer and environment configuration.

The first deployment rolled back because GitHubAttendFlowDeploy lacked
lambda:GetLayerVersion for the layer. A narrowly scoped inline policy fixed
the issue. The second attempt succeeded.

Evidence:
https://github.com/Akarshjoy/attendflow/actions/runs/41208519610

The post-deployment service graph verified API and Cleanup downstream
instrumentation. Recognition and Report coverage remain unverified.

## Limits

The CI dependency is a verified deployment gate. Repository branch protection,
required reviewers, immutable action-SHA pinning and approval environments are
separate controls and have not been established by this evidence.

The observed workflow deploys the SAM build. A separate static-frontend
publication procedure is not demonstrated by the supplied workflow.
