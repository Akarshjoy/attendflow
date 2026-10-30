"""Replace SAM-generated broad execution policies with explicit scoped roles.
Run after build_template.py. No AWS calls. Does not complete the full IAM audit.
"""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / 'template.json'
template = json.loads(path.read_text(encoding='utf-8-sig'))
resources = template['Resources']
changed = 0
for name, resource in list(resources.items()):
    if resource['Type'] != 'AWS::Serverless::Function':
        continue
    props = resource['Properties']
    if props.get('Role'):
        # Preserve existing explicit roles (including AttendFlow).
        continue
    role_id = name + 'Role'
    if role_id in resources:
        raise ValueError('Unexpected role collision: ' + role_id)
    statements = []
    for policy in props.get('Policies', []):
        if not isinstance(policy, dict) or 'Statement' not in policy:
            raise ValueError('Review non-inline policy on ' + name)
        value = policy['Statement']
        statements.extend(value if isinstance(value, list) else [value])
    # Match existing default log groups without introducing a Role->Function cycle.
    log_scope = {'Fn::Sub': 'arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:/aws/lambda/${AWS::StackName}-' + name + '-*'}
    stream_scope = {'Fn::Sub': 'arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:/aws/lambda/${AWS::StackName}-' + name + '-*:log-stream:*'}
    log_config = props.get('LoggingConfig', {}).get('LogGroup')
    if log_config:
        if not isinstance(log_config, dict) or 'Ref' not in log_config:
            raise ValueError('Review log configuration on ' + name)
        log_resource = resources[log_config['Ref']]
        log_name = log_resource['Properties']['LogGroupName']
        log_scope = {'Fn::Sub': ['arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:${Group}', {'Group': log_name}]}
        stream_scope = {'Fn::Sub': ['arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:${Group}:log-stream:*', {'Group': log_name}]}
    statements.extend([
        {'Effect': 'Allow', 'Action': ['logs:CreateLogGroup'], 'Resource': log_scope},
        {'Effect': 'Allow', 'Action': ['logs:CreateLogStream', 'logs:PutLogEvents'], 'Resource': stream_scope},
        {'Effect': 'Allow', 'Action': ['xray:PutTraceSegments', 'xray:PutTelemetryRecords'], 'Resource': '*'}
    ])
    for event in props.get('Events', {}).values():
        ep = event.get('Properties', {})
        if event['Type'] == 'SQS':
            statements.append({'Effect': 'Allow', 'Action': ['sqs:ReceiveMessage', 'sqs:DeleteMessage', 'sqs:GetQueueAttributes'], 'Resource': ep['Queue']})
        if event['Type'] == 'DynamoDB':
            statements.append({'Effect': 'Allow', 'Action': ['dynamodb:GetRecords', 'dynamodb:GetShardIterator', 'dynamodb:DescribeStream'], 'Resource': ep['Stream']})
            # ListStreams does not support resource-level permissions.
            statements.append({'Effect': 'Allow', 'Action': ['dynamodb:ListStreams'], 'Resource': '*'})
            failure = ep.get('DestinationConfig', {}).get('OnFailure', {})
            if failure.get('Type') == 'SQS':
                statements.append({'Effect': 'Allow', 'Action': ['sqs:SendMessage'], 'Resource': failure['Destination']})
    # Eliminate duplicate statements while retaining every existing business permission.
    unique = {json.dumps(s, sort_keys=True): s for s in statements}
    resources[role_id] = {
        'Type': 'AWS::IAM::Role',
        'Properties': {
            'AssumeRolePolicyDocument': {'Version': '2012-10-17', 'Statement': [
                {'Effect': 'Allow', 'Principal': {'Service': 'lambda.amazonaws.com'}, 'Action': 'sts:AssumeRole'}
            ]},
            'Policies': [{'PolicyName': 'ScopedRuntime', 'PolicyDocument': {'Version': '2012-10-17', 'Statement': list(unique.values())}}]
        }
    }
    props.pop('Policies', None)
    props['Role'] = {'Fn::GetAtt': [role_id, 'Arn']}
    changed += 1
path.write_text(json.dumps(template, indent=2) + '\n', encoding='utf-8')
print(f'Scoped {changed} generated Lambda roles; existing explicit roles preserved.')
