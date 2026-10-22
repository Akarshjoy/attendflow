"""Generate reviewable deployer policies. No policy is attached automatically."""
import argparse,json,re
from pathlib import Path
import boto3
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--profile',default='my-account');p.add_argument('--region',default='us-east-1');p.add_argument('--stack',default='attendflow');a=p.parse_args()
if not re.fullmatch('[a-z][a-z0-9-]{2,35}',a.stack):raise SystemExit('Use a lowercase stack name (3–36 characters).')
s=boto3.Session(profile_name=a.profile,region_name=a.region);identity=s.client('sts').get_caller_identity();account=identity['Account'];partition=identity['Arn'].split(':')[1];region=a.region
S=[]
def allow(actions,resources,condition=None):
    st={'Effect':'Allow','Action':actions,'Resource':resources}
    if condition:st['Condition']=condition
    S.append(st)
base=f'arn:{partition}:'
allow(['cloudformation:CreateStack','cloudformation:UpdateStack','cloudformation:DeleteStack','cloudformation:DescribeStacks','cloudformation:DescribeStackEvents','cloudformation:DescribeStackResources','cloudformation:ListStackResources','cloudformation:GetTemplate','cloudformation:GetTemplateSummary','cloudformation:CreateChangeSet','cloudformation:DescribeChangeSet','cloudformation:ExecuteChangeSet','cloudformation:DeleteChangeSet','cloudformation:ListChangeSets'],[f'{base}cloudformation:{region}:{account}:stack/{a.stack}*/*',f'{base}cloudformation:{region}:{account}:stack/aws-sam-cli-managed-default/*',f'{base}cloudformation:{region}:{account}:changeSet/*/*',f'{base}cloudformation:{region}:aws:transform/Serverless-2016-10-31'])
allow(['cloudformation:ValidateTemplate','cloudformation:GetTemplateSummary'],'*')
allow(['s3:CreateBucket','s3:DeleteBucket','s3:GetBucketLocation','s3:ListBucket','s3:ListBucketVersions','s3:GetBucketPolicy','s3:PutBucketPolicy','s3:DeleteBucketPolicy','s3:PutBucketPublicAccessBlock','s3:GetBucketPublicAccessBlock','s3:PutBucketOwnershipControls','s3:GetBucketOwnershipControls','s3:PutEncryptionConfiguration','s3:GetEncryptionConfiguration','s3:PutBucketVersioning','s3:GetBucketVersioning','s3:PutBucketCORS','s3:GetBucketCORS','s3:PutLifecycleConfiguration','s3:GetLifecycleConfiguration','s3:PutBucketNotification','s3:GetBucketNotification','s3:PutBucketTagging','s3:GetBucketTagging','s3:GetObject','s3:PutObject','s3:DeleteObject','s3:DeleteObjectVersion','s3:GetObjectVersion'],[f'{base}s3:::{a.stack}-*',f'{base}s3:::{a.stack}-*/*',f'{base}s3:::aws-sam-cli-managed-default-*',f'{base}s3:::aws-sam-cli-managed-default-*/*'])
allow(['iam:CreateRole','iam:DeleteRole','iam:GetRole','iam:UpdateAssumeRolePolicy','iam:PutRolePolicy','iam:GetRolePolicy','iam:DeleteRolePolicy','iam:ListRolePolicies','iam:AttachRolePolicy','iam:DetachRolePolicy','iam:ListAttachedRolePolicies','iam:TagRole','iam:UntagRole'],f'{base}iam::{account}:role/{a.stack}-*')
allow(['iam:PassRole'],f'{base}iam::{account}:role/{a.stack}-*',{'StringEquals':{'iam:PassedToService':['lambda.amazonaws.com','scheduler.amazonaws.com']}})
allow(['lambda:CreateFunction','lambda:DeleteFunction','lambda:GetFunction','lambda:GetFunctionConfiguration','lambda:UpdateFunctionCode','lambda:UpdateFunctionConfiguration','lambda:AddPermission','lambda:RemovePermission','lambda:GetPolicy','lambda:TagResource','lambda:UntagResource','lambda:ListTags','lambda:PutFunctionConcurrency','lambda:DeleteFunctionConcurrency','lambda:GetFunctionConcurrency','lambda:PutFunctionEventInvokeConfig','lambda:DeleteFunctionEventInvokeConfig','lambda:GetFunctionEventInvokeConfig','lambda:InvokeFunction'],f'{base}lambda:{region}:{account}:function:{a.stack}-*')
allow(['lambda:GetEventSourceMapping','lambda:UpdateEventSourceMapping','lambda:DeleteEventSourceMapping','lambda:TagResource','lambda:UntagResource','lambda:ListTags'],f'{base}lambda:{region}:{account}:event-source-mapping:*')
allow(['lambda:CreateEventSourceMapping'],'*',{'ArnLike':{'lambda:FunctionArn':f'{base}lambda:{region}:{account}:function:{a.stack}-*'}})
allow(['lambda:ListEventSourceMappings'],'*')
allow(['dynamodb:CreateTable','dynamodb:DeleteTable','dynamodb:DescribeTable','dynamodb:UpdateTable','dynamodb:DescribeContinuousBackups','dynamodb:UpdateContinuousBackups','dynamodb:DescribeTimeToLive','dynamodb:UpdateTimeToLive','dynamodb:TagResource','dynamodb:UntagResource','dynamodb:ListTagsOfResource','dynamodb:GetItem','dynamodb:PutItem','dynamodb:Scan'],f'{base}dynamodb:{region}:{account}:table/{a.stack}-*')
allow(['rekognition:CreateCollection','rekognition:DescribeCollection','rekognition:DeleteCollection','rekognition:ListFaces','rekognition:DeleteFaces','rekognition:TagResource','rekognition:UntagResource','rekognition:ListTagsForResource'],f'{base}rekognition:{region}:{account}:collection/{a.stack}-employees')
allow(['sqs:CreateQueue','sqs:DeleteQueue','sqs:GetQueueAttributes','sqs:SetQueueAttributes','sqs:GetQueueUrl','sqs:TagQueue','sqs:UntagQueue','sqs:ListQueueTags'],f'{base}sqs:{region}:{account}:{a.stack}-*')
allow(['cognito-idp:CreateUserPool'],'*')
allow(['cognito-idp:DescribeUserPool','cognito-idp:UpdateUserPool','cognito-idp:DeleteUserPool','cognito-idp:CreateUserPoolClient','cognito-idp:UpdateUserPoolClient','cognito-idp:DescribeUserPoolClient','cognito-idp:DeleteUserPoolClient','cognito-idp:CreateGroup','cognito-idp:GetGroup','cognito-idp:UpdateGroup','cognito-idp:DeleteGroup','cognito-idp:AdminCreateUser','cognito-idp:AdminGetUser','cognito-idp:AdminAddUserToGroup','cognito-idp:AdminListGroupsForUser','cognito-idp:TagResource','cognito-idp:UntagResource','cognito-idp:ListTagsForResource'],f'{base}cognito-idp:{region}:{account}:userpool/*')
allow(['apigateway:GET','apigateway:POST','apigateway:PUT','apigateway:PATCH','apigateway:DELETE'],f'{base}apigateway:{region}::*')
allow(['cloudfront:CreateDistribution','cloudfront:GetDistribution','cloudfront:GetDistributionConfig','cloudfront:UpdateDistribution','cloudfront:DeleteDistribution','cloudfront:CreateOriginAccessControl','cloudfront:GetOriginAccessControl','cloudfront:UpdateOriginAccessControl','cloudfront:DeleteOriginAccessControl','cloudfront:CreateResponseHeadersPolicy','cloudfront:GetResponseHeadersPolicy','cloudfront:UpdateResponseHeadersPolicy','cloudfront:DeleteResponseHeadersPolicy','cloudfront:ListTagsForResource','cloudfront:TagResource','cloudfront:UntagResource','cloudfront:CreateInvalidation'],'*')
allow(['logs:CreateLogGroup','logs:DescribeLogGroups','logs:DeleteLogGroup','logs:PutRetentionPolicy','logs:DeleteRetentionPolicy','logs:TagResource','logs:UntagResource','logs:ListTagsForResource','logs:TagLogGroup','logs:UntagLogGroup'],f'{base}logs:{region}:{account}:log-group:/aws/lambda/{a.stack}-*')
allow(['logs:DescribeLogGroups'],'*')
allow(['events:PutRule','events:DescribeRule','events:DeleteRule','events:PutTargets','events:RemoveTargets','events:ListTargetsByRule','events:TagResource','events:UntagResource'],f'{base}events:{region}:{account}:rule/{a.stack}-*')
allow(['scheduler:CreateSchedule','scheduler:GetSchedule','scheduler:UpdateSchedule','scheduler:DeleteSchedule'],f'{base}scheduler:{region}:{account}:schedule/default/{a.stack}-*')
allow(['sns:CreateTopic','sns:DeleteTopic','sns:GetTopicAttributes','sns:SetTopicAttributes','sns:Subscribe','sns:Unsubscribe','sns:ListSubscriptionsByTopic','sns:TagResource','sns:UntagResource','sns:ListTagsForResource'],f'{base}sns:{region}:{account}:{a.stack}-*')
allow(['cloudwatch:PutMetricAlarm','cloudwatch:DeleteAlarms','cloudwatch:DescribeAlarms','cloudwatch:TagResource','cloudwatch:UntagResource','cloudwatch:ListTagsForResource'],f'{base}cloudwatch:{region}:{account}:alarm:{a.stack}-*')
# Split by JSON character count to stay below the 6,144-character managed-policy limit.
chunks=[];chunk=[]
for st in S:
    if len(json.dumps({'Version':'2012-10-17','Statement':chunk+[st]},separators=(',',':')))>5500:
        chunks.append(chunk);chunk=[]
    chunk.append(st)
if chunk:chunks.append(chunk)
for i,chunk in enumerate(chunks,1):
    path=Path(__file__).resolve().parents[1]/f'deployment-policy-{i}.json'
    path.write_text(json.dumps({'Version':'2012-10-17','Statement':chunk},indent=2)+'\n')
    print(path.name)
print('Have an account administrator review and attach these as CUSTOMER-MANAGED policies. No policy was attached.')
print('Creation actions may need wildcard scope. These are deployment permissions, not Lambda runtime roles.')
