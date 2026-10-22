"""Post-deployment initialization. Never prints AWS credentials or passwords."""
import argparse
import json
from pathlib import Path
import boto3
from botocore.exceptions import ClientError

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--profile',default='my-account');p.add_argument('--region',default='us-east-1');p.add_argument('--stack',default='attendflow')
actions=p.add_subparsers(dest='command',required=True)
for action in ['seed','configure','outputs']: actions.add_parser(action)
u=actions.add_parser('user');u.add_argument('--username',required=True);u.add_argument('--email',required=True);u.add_argument('--role',choices=['Admin','Kiosk'],required=True)
a=p.parse_args();session=boto3.Session(profile_name=a.profile,region_name=a.region)
stack=session.client('cloudformation').describe_stacks(StackName=a.stack)['Stacks'][0]
if stack['StackStatus'] not in ('CREATE_COMPLETE','UPDATE_COMPLETE'):
    raise SystemExit('Stack is not healthy: '+stack['StackStatus'])
o={x['OutputKey']:x['OutputValue'] for x in stack['Outputs']}
root=Path(__file__).resolve().parents[1]
if a.command=='outputs':print(json.dumps(o,indent=2))
if a.command=='seed':
    table=session.resource('dynamodb').Table(o['ConfigTable'])
    try:
        table.put_item(Item={'config_id':'policy','holidays':[],'similarity':99,'version':1},ConditionExpression='attribute_not_exists(config_id)')
        print('Seeded attendance policy. Holidays empty; similarity 99.')
    except ClientError as exc:
        if exc.response['Error']['Code']!='ConditionalCheckFailedException':raise
        print('Existing policy kept unchanged.')
if a.command=='configure':
    conf={'apiUrl':o['ApiUrl'],'clientId':o['ClientId'],'region':a.region}
    (root/'frontend'/'config.js').write_text('window.ATTENDFLOW = '+json.dumps(conf,indent=2)+';\n',encoding='utf-8')
    print('Wrote frontend/config.js. Upload the frontend to '+o['WebBucket'])
    print('Portal: '+o['PortalUrl'])
if a.command=='user':
    c=session.client('cognito-idp');email=a.email.strip().lower();username=a.username.strip()
    try:
        current=c.admin_get_user(UserPoolId=o['UserPoolId'],Username=username)
        attrs={x['Name']:x['Value'] for x in current['UserAttributes']}
        assigned=c.admin_list_groups_for_user(UserPoolId=o['UserPoolId'],Username=username)['Groups']
        if attrs.get('email')!=email or {g['GroupName'] for g in assigned}!={a.role}:
            raise SystemExit('User exists with different details or groups. Review it in Cognito; this command does not change roles.')
        print('Existing matching user kept unchanged. No new invitation sent.')
    except c.exceptions.UserNotFoundException:
        c.admin_create_user(UserPoolId=o['UserPoolId'],Username=username,
            UserAttributes=[{'Name':'email','Value':email}],DesiredDeliveryMediums=['EMAIL'])
        c.admin_add_user_to_group(UserPoolId=o['UserPoolId'],Username=username,GroupName=a.role)
        print('Created '+a.role+' user '+username+'. Check the invitation email and change the temporary password at first login.')
