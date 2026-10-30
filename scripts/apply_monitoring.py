import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
path = ROOT / "template.json"
template = json.loads(path.read_text(encoding="utf-8-sig"))
resources = template["Resources"]
functions = ["ApiFunction", "Recognition", "Cleanup", "Report"]

for name in functions:
    if resources.get(name, {}).get("Type") != "AWS::Serverless::Function":
        raise RuntimeError(f"Expected SAM function missing: {name}")

if resources.get("Alerts", {}).get("Type") != "AWS::SNS::Topic":
    raise RuntimeError("Expected Alerts SNS topic missing")

def ref(name):
    return {"Ref": name}

def alarm_metric(name, metric, identifier):
    return {
        "Id": identifier,
        "ReturnData": False,
        "MetricStat": {
            "Metric": {
                "Namespace": "AWS/Lambda",
                "MetricName": metric,
                "Dimensions": [
                    {"Name": "FunctionName", "Value": ref(name)}
                ],
            },
            "Period": 300,
            "Stat": "Sum",
        },
    }

for name in functions:
    common = {
        "ComparisonOperator": "GreaterThanThreshold",
        "EvaluationPeriods": 1,
        "DatapointsToAlarm": 1,
        "TreatMissingData": "notBreaching",
        "AlarmActions": [ref("Alerts")],
        "OKActions": [ref("Alerts")],
    }

    resources[name + "ErrorRateAlarm"] = {
        "Type": "AWS::CloudWatch::Alarm",
        "Properties": {
            **common,
            "AlarmDescription": (
                f"{name}: Lambda execution errors exceed 5% "
                "of invocations in a five-minute period."
            ),
            "Threshold": 5,
            "Metrics": [
                alarm_metric(name, "Errors", "errors"),
                alarm_metric(name, "Invocations", "invocations"),
                {
                    "Id": "rate",
                    "Expression": (
                        "IF(invocations>0,100*errors/invocations,0)"
                    ),
                    "Label": "Lambda error rate (%)",
                    "ReturnData": True,
                },
            ],
        },
    }

    resources[name + "P95LatencyAlarm"] = {
        "Type": "AWS::CloudWatch::Alarm",
        "Properties": {
            **common,
            "AlarmDescription": (
                f"{name}: Lambda execution P95 exceeds 3000 ms "
                "in a five-minute period. Not end-to-end latency."
            ),
            "Namespace": "AWS/Lambda",
            "MetricName": "Duration",
            "Dimensions": [
                {"Name": "FunctionName", "Value": ref(name)}
            ],
            "ExtendedStatistic": "p95",
            "Period": 300,
            "Threshold": 3000,
            "EvaluateLowSampleCountPercentile": "evaluate",
        },
    }

def dashboard_metric(name, metric, settings):
    return [
        "AWS/Lambda",
        metric,
        "FunctionName",
        "${" + name + "}",
        settings,
    ]

invocations = []
error_rates = []
durations = []

for index, name in enumerate(functions):
    invocations.append(
        dashboard_metric(name, "Invocations", {"label": name})
    )
    durations.append(
        dashboard_metric(name, "Duration", {"label": name})
    )

    error_id = f"e{index}"
    invocation_id = f"i{index}"

    error_rates.extend([
        dashboard_metric(
            name, "Errors",
            {"id": error_id, "visible": False, "stat": "Sum"}
        ),
        dashboard_metric(
            name, "Invocations",
            {"id": invocation_id, "visible": False, "stat": "Sum"}
        ),
        [{
            "id": f"r{index}",
            "expression": (
                f"IF({invocation_id}>0,"
                f"100*{error_id}/{invocation_id},0)"
            ),
            "label": name,
        }],
    ])

def widget(title, x, metrics, statistic, axis_label, threshold=None):
    properties = {
        "title": title,
        "view": "timeSeries",
        "region": "${AWS::Region}",
        "period": 300,
        "stat": statistic,
        "metrics": metrics,
        "stacked": False,
        "yAxis": {
            "left": {
                "min": 0,
                "label": axis_label,
                "showUnits": False,
            }
        },
    }
    if threshold is not None:
        properties["annotations"] = {
            "horizontal": [{
                "label": "Alarm threshold",
                "value": threshold,
            }]
        }
    return {
        "type": "metric",
        "x": x,
        "y": 3,
        "width": 8,
        "height": 7,
        "properties": properties,
    }

body = {
    "start": "-PT6H",
    "periodOverride": "inherit",
    "widgets": [
        {
            "type": "text",
            "x": 0,
            "y": 0,
            "width": 24,
            "height": 3,
            "properties": {
                "markdown": (
                    "# AttendFlow operational dashboard\n"
                    "Five-minute periods; one series per Lambda. "
                    "Error rate = 100 x execution errors / invocations. "
                    "P95 measures Lambda execution duration, not the "
                    "complete camera-to-result journey. Expected face "
                    "rejections and handled API errors require separate "
                    "application logging. Missing data is not proof of health."
                )
            },
        },
        widget(
            "Invocations per 5 minutes",
            0, invocations, "Sum", "Invocations"
        ),
        widget(
            "Lambda execution error rate (%)",
            8, error_rates, "Sum", "Percent", 5
        ),
        widget(
            "Lambda execution P95 duration (ms)",
            16, durations, "p95", "Milliseconds", 3000
        ),
    ],
}

resources["OperationsDashboard"] = {
    "Type": "AWS::CloudWatch::Dashboard",
    "Properties": {
        "DashboardName": {
            "Fn::Sub": "${AWS::StackName}-${AWS::Region}-operations"
        },
        "DashboardBody": {"Fn::Sub": json.dumps(body)},
    },
}

template.setdefault("Outputs", {})["OperationsDashboardName"] = {
    "Value": ref("OperationsDashboard")
}

path.write_text(
    json.dumps(template, indent=2) + "\n",
    encoding="utf-8"
)
print(
    "Monitoring configured locally: "
    "8 new alarms and 1 dashboard. Existing alarms preserved."
)