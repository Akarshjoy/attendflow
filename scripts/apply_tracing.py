"""Apply phase-one infrastructure tracing settings after template generation."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / "template.json"
template = json.loads(path.read_text(encoding="utf-8-sig"))
resources = template["Resources"]
count = 0
for name, resource in resources.items():
    props = resource.get("Properties", {})
    if resource["Type"] == "AWS::Serverless::Api":
        props["TracingEnabled"] = True
    if resource["Type"] != "AWS::Serverless::Function":
        continue
    props["Tracing"] = "Active"
    count += 1
    role = props.get("Role")
    if role is None:
        # SAM adds tracing permissions to its generated execution role.
        continue
    ref = role.get("Fn::GetAtt") if isinstance(role, dict) else None
    if not isinstance(ref, list) or len(ref) != 2 or ref[1] != "Arn":
        raise ValueError(f"Review the explicit role for {name} before proceeding")
    role_resource = resources[ref[0]]
    if role_resource["Type"] != "AWS::IAM::Role":
        raise ValueError(f"Unexpected role resource for {name}")
    policies = role_resource["Properties"].setdefault("Policies", [])
    policy = {
        "PolicyName": "HardeningTraceWrite",
        "PolicyDocument": {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": ["xray:PutTraceSegments", "xray:PutTelemetryRecords"],
                "Resource": "*"
            }]
        }
    }
    policies[:] = [p for p in policies if p.get("PolicyName") != policy["PolicyName"]]
    policies.append(policy)
path.write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")
print(f"Tracing configured locally for {count} Lambda functions and API stages.")
