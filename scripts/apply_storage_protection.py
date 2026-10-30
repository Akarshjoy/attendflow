import json
from pathlib import Path

root = Path(__file__).resolve().parent.parent
path = root / "template.json"
template = json.loads(path.read_text(encoding="utf-8-sig"))
resources = template["Resources"]
tables = ("Employees", "Attendance", "Sessions", "Config", "Audit")

# Check every expected table before saving changes.
for name in tables:
    resource = resources.get(name, {})
    if resource.get("Type") != "AWS::DynamoDB::Table":
        raise RuntimeError(f"Expected DynamoDB table missing: {name}")
    if resource.get("DeletionPolicy") != "Retain":
        raise RuntimeError(f"Expected Retain deletion policy missing: {name}")
    if resource.get("UpdateReplacePolicy") != "Retain":
        raise RuntimeError(f"Expected Retain replacement policy missing: {name}")

for name in tables:
    resources[name]["Properties"]["DeletionProtectionEnabled"] = True

path.write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")
print("Deletion protection configured locally for all five DynamoDB tables.")