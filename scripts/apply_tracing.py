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

    # ATTENDFLOW_ADOT_SDK_TRACING
    if name in {"ApiFunction", "Recognition", "Cleanup", "Report"}:
        if props.get("Runtime") != "python3.14":
            raise ValueError(f"Review runtime compatibility for {name}")

        layer = (
            "arn:aws:lambda:us-east-1:615299751070:"
            "layer:AWSOpenTelemetryDistroPython:32"
        )
        layers = props.setdefault("Layers", [])
        if layer not in layers:
            if len(layers) >= 5:
                raise ValueError(f"Lambda layer limit reached for {name}")
            layers.append(layer)

        variables = props.setdefault("Environment", {}).setdefault("Variables", {})
        settings = {
            "AWS_LAMBDA_EXEC_WRAPPER": "/opt/otel-instrument",
            "OTEL_AWS_APPLICATION_SIGNALS_ENABLED": "false",
            "OTEL_METRICS_EXPORTER": "none",
            "OTEL_LOGS_EXPORTER": "none",
        }
        for key, value in settings.items():
            if key in variables and variables[key] != value:
                raise ValueError(f"Conflicting {key} setting for {name}")
            variables[key] = value
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
