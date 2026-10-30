import json
from pathlib import Path

root = Path(__file__).resolve().parent.parent
path = root / "template.json"
template = json.loads(path.read_text(encoding="utf-8-sig"))
resources = template["Resources"]

expected_role = {"Fn::GetAtt": ["ScheduleRole", "Arn"]}

for name in ("DailySchedule", "ReconcileSchedule", "WeeklySchedule"):
    resource = resources[name]
    if resource["Type"] != "AWS::Scheduler::Schedule":
        raise RuntimeError(f"Unexpected resource type: {name}")
    properties = resource["Properties"]
    if properties.get("GroupName", "default") != "default":
        raise RuntimeError(f"Schedule group changed: {name}")
    if properties["Target"]["RoleArn"] != expected_role:
        raise RuntimeError(f"Schedule role changed: {name}")

role = resources["ScheduleRole"]
if role["Type"] != "AWS::IAM::Role":
    raise RuntimeError("Expected ScheduleRole IAM role")

trust = role["Properties"]["AssumeRolePolicyDocument"]
statements = trust["Statement"]
if not isinstance(statements, list) or len(statements) != 1:
    raise RuntimeError("Unexpected trust statements; inspect before changing")

statement = statements[0]
if (
    statement.get("Effect") != "Allow"
    or statement.get("Principal") != {"Service": "scheduler.amazonaws.com"}
    or statement.get("Action") != "sts:AssumeRole"
):
    raise RuntimeError("Unexpected Scheduler trust policy")

condition = statement.setdefault("Condition", {})
account = condition.get("StringEquals", {}).get("aws:SourceAccount")
if account != {"Ref": "AWS::AccountId"}:
    raise RuntimeError("Expected account restriction is missing")

source_arn = {
    "Fn::Sub":
        "arn:${AWS::Partition}:scheduler:${AWS::Region}:"
        "${AWS::AccountId}:schedule-group/default"
}

for operator, entries in condition.items():
    if "aws:SourceArn" in entries:
        if operator != "ArnEquals" or entries["aws:SourceArn"] != source_arn:
            raise RuntimeError("Different SourceArn restriction already exists")

condition.setdefault("ArnEquals", {})["aws:SourceArn"] = source_arn

path.write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")
print("ScheduleRole trust restricted to this account, region and default group.")