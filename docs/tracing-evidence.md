# AttendFlow tracing evidence

Observed: 31 October 2026
Region: us-east-1
Source: AWS X-Ray GetServiceGraph, preceding six-hour window.
Retrieved through AWS CloudShell.

## Observed AttendFlow nodes

| Node | Type | Graph request count |
|---|---|---:|
| attendflow/prod | AWS::ApiGateway::Stage | 919 |
| attendflow-ApiFunction | AWS::Lambda | 913 |
| attendflow-ApiFunction | AWS::Lambda::Function | 913 |
| attendflow-Cleanup | AWS::Lambda | 72 |
| attendflow-Cleanup | AWS::Lambda::Function | 72 |

Observed API edges:
client -> API Gateway stage -> Lambda service -> Lambda function.

Observed cleanup edges:
client -> Cleanup Lambda service -> Cleanup Lambda function.

The client nodes do not identify a specific person or prove the exact
upstream trigger. Lambda service/function counts are not additive.

## Interpretation and limits

This confirms trace collection and API Gateway-to-Lambda connectivity.
Graph counts describe the retrieved trace data, not a complete traffic
or billing census. The stage/function count difference is unexplained
by this summary and must not be labeled as six application failures.

Recognition and Report were absent from the returned window.
No DynamoDB, S3 or Rekognition downstream nodes were present.
Complete recognition/report flow coverage and SDK dependency tracing
remain unverified. Absence alone does not establish a service failure.

Other projects appeared in the account-wide query and were excluded
from this AttendFlow evidence record.

## Access

The dayone-deployer CLI identity was denied xray:GetServiceGraph.
The existing console identity successfully retrieved the graph through
CloudShell. No permission change was required for this evidence capture.