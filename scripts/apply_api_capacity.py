import json
from pathlib import Path

root = Path(__file__).resolve().parent.parent
path = root / "template.json"
template = json.loads(path.read_text(encoding="utf-8-sig"))
api = template["Resources"]["Api"]

if api["Type"] != "AWS::Serverless::Api":
    raise RuntimeError("Expected Api to be AWS::Serverless::Api")

settings = api["Properties"].get("MethodSettings", [])
if not isinstance(settings, list):
    raise RuntimeError("Unexpected MethodSettings format")

defaults = [
    setting for setting in settings
    if setting.get("HttpMethod") == "*"
    and setting.get("ResourcePath") in ("/*", "*")
]
if len(defaults) != 1:
    raise RuntimeError("Expected exactly one default method setting")

setting = defaults[0]
current = (
    setting.get("ThrottlingRateLimit"),
    setting.get("ThrottlingBurstLimit"),
)
if current not in ((10, 20), (50, 100)):
    raise RuntimeError(f"Unexpected existing throttle settings: {current}")

setting["ThrottlingRateLimit"] = 50
setting["ThrottlingBurstLimit"] = 100

path.write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")
print("API capacity configured locally: 50 requests/sec, burst 100.")
