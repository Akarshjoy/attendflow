# Trusted Advisor review

Date: 31 October 2026
Source: refreshed AWS Trusted Advisor Security console screenshots.
Scope: account-level checks visible in the supplied evidence.

| Check | Observed result |
|---|---|
| Amazon EBS Public Snapshots | Green; 0 public snapshots |
| Amazon RDS Public Snapshots | Green; 0 public snapshots |
| Amazon S3 Bucket Permissions | Green; 17 items shown in the section |
| MFA on Root Account | Green; explicitly states MFA is enabled |
| Security Groups - Specific Ports Unrestricted | Green; 0 items shown |

No remediation was indicated by these five displayed results.
Refreshing checks did not itself change resource permissions.

## Scope limitations

This review does not establish that every Trusted Advisor check passed.
Individual S3 resource rows were not visible in the screenshots.
The security-group check describes specific ports and IPv4 inbound rules;
its green result is not proof that every network access path is restricted.

Root-account MFA does not establish MFA for application administrators.
EBS/RDS findings are account-level context, not evidence that AttendFlow
uses either service.

AttendFlow's bucket encryption, versioning and public-access-block settings
were verified separately through AWS CLI output.

## Related evidence

- security-and-retention.md
- validation.md
- operations-runbook.md