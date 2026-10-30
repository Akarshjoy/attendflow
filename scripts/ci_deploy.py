"""Deploy the tested SAM artifact, preserving existing stack parameters."""
import json
import subprocess
from pathlib import Path

REGION = "us-east-1"
STACK = "attendflow"

raw = subprocess.check_output([
    "aws", "cloudformation", "describe-stacks",
    "--stack-name", STACK,
    "--region", REGION,
    "--output", "json",
    "--no-cli-pager",
], text=True)
stack = json.loads(raw)["Stacks"][0]

if stack["StackStatus"] not in {
    "CREATE_COMPLETE", "UPDATE_COMPLETE", "UPDATE_ROLLBACK_COMPLETE"
}:
    raise SystemExit(f"Stack is not ready: {stack['StackStatus']}")

parameters = []
for parameter in stack.get("Parameters", []):
    value = parameter["ParameterValue"]
    if value == "****":
        raise SystemExit("Masked stack parameter; cannot safely reuse its value.")
    parameters.append(
        f"ParameterKey={parameter['ParameterKey']},ParameterValue={value}"
    )

template = Path(".aws-sam/build/template.yaml")
if not template.is_file():
    raise SystemExit("Tested build template is missing.")

# Isolate CI deployment from any developer-specific samconfig settings.
config = Path(".aws-sam/ci-samconfig.toml").resolve()
config.write_text("version = 0.1\n", encoding="utf-8")

command = [
    "sam", "deploy",
    "--config-file", str(config),
    "--template-file", str(template),
    "--stack-name", STACK,
    "--region", REGION,
    "--s3-bucket",
    "aws-sam-cli-managed-default-samclisourcebucket-ik7r3nz9tsjv",
    "--s3-prefix", "attendflow-hardening",
    "--capabilities", "CAPABILITY_IAM",
    "--no-confirm-changeset",
    "--no-fail-on-empty-changeset",
]
if parameters:
    command.extend(["--parameter-overrides", *parameters])

subprocess.run(command, check=True)