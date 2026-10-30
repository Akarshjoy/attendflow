"""Generate CloudFormation/SAM without YAML dependencies."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
R={}
def ref(n): return {'Ref':n}
def sub(s): return {'Fn::Sub':s}
def arn(n): return {'Fn::GetAtt':[n,'Arn']}
def add(n,t,p,**extra): R[n]={'Type':t,'Properties':p,**extra}
def allow(actions,resource,**extra): return {'Effect':'Allow','Action':actions,'Resource':resource,**extra}
def db(names,actions): return allow(['dynamodb:'+x for x in actions],[arn(n) for n in names])
read=['GetItem','Query','Scan']
write=read+['PutItem','UpdateItem','DeleteItem','ConditionCheckItem']
for name,pk,sk in [('Employees','employee_id',None),('Attendance','employee_id','date'),('Sessions','session_id',None),('Config','config_id',None),('Audit','event_id',None)]:
    keys=[{'AttributeName':pk,'KeyType':'HASH'}]+([{'AttributeName':sk,'KeyType':'RANGE'}] if sk else [])
    props={'BillingMode':'PAY_PER_REQUEST','AttributeDefinitions':[{'AttributeName':x['AttributeName'],'AttributeType':'S'} for x in keys],
           'KeySchema':keys,'SSESpecification':{'SSEEnabled':True},'PointInTimeRecoverySpecification':{'PointInTimeRecoveryEnabled':True}}
    if name=='Sessions': props['TimeToLiveSpecification']={'AttributeName':'ttl','Enabled':True}
    add(name,'AWS::DynamoDB::Table',props,DeletionPolicy='Retain',UpdateReplacePolicy='Retain')
add('Collection','AWS::Rekognition::Collection',{'CollectionId':sub('${AWS::StackName}-employees')},DeletionPolicy='Retain',UpdateReplacePolicy='Retain')
add('DeadLetters','AWS::SQS::Queue',{'MessageRetentionPeriod':1209600,'SqsManagedSseEnabled':True})
add('UploadQueue','AWS::SQS::Queue',{'VisibilityTimeout':360,'MessageRetentionPeriod':86400,'SqsManagedSseEnabled':True,
    'RedrivePolicy':{'deadLetterTargetArn':arn('DeadLetters'),'maxReceiveCount':4}})
raw_name=sub('${AWS::StackName}-captures-${AWS::AccountId}-${AWS::Region}')
raw_arn=sub('arn:${AWS::Partition}:s3:::${AWS::StackName}-captures-${AWS::AccountId}-${AWS::Region}')
add('QueuePolicy','AWS::SQS::QueuePolicy',{'Queues':[ref('UploadQueue')],'PolicyDocument':{'Version':'2012-10-17','Statement':[
    {'Effect':'Allow','Principal':{'Service':'s3.amazonaws.com'},'Action':'sqs:SendMessage','Resource':arn('UploadQueue'),
     'Condition':{'ArnEquals':{'aws:SourceArn':raw_arn},'StringEquals':{'aws:SourceAccount':ref('AWS::AccountId')}}}]}})
secure={'BucketEncryption':{'ServerSideEncryptionConfiguration':[{'ServerSideEncryptionByDefault':{'SSEAlgorithm':'AES256'}}]},
        'PublicAccessBlockConfiguration':{'BlockPublicAcls':True,'BlockPublicPolicy':True,'IgnorePublicAcls':True,'RestrictPublicBuckets':True},
        'VersioningConfiguration':{'Status':'Enabled'},'OwnershipControls':{'Rules':[{'ObjectOwnership':'BucketOwnerEnforced'}]}}
add('Web','AWS::S3::Bucket',secure,DeletionPolicy='Retain',UpdateReplacePolicy='Retain')
add('Reports','AWS::S3::Bucket',{**secure,'LifecycleConfiguration':{'Rules':[{'Id':'OldReportVersions','Status':'Enabled','NoncurrentVersionExpiration':{'NoncurrentDays':30}}]}},DeletionPolicy='Retain',UpdateReplacePolicy='Retain')
add('OAC','AWS::CloudFront::OriginAccessControl',{'OriginAccessControlConfig':{'Name':sub('${AWS::StackName}-web'),'OriginAccessControlOriginType':'s3','SigningBehavior':'always','SigningProtocol':'sigv4'}})
add('Headers','AWS::CloudFront::ResponseHeadersPolicy',{'ResponseHeadersPolicyConfig':{'Name':sub('${AWS::StackName}-headers'),
    'SecurityHeadersConfig':{'ContentTypeOptions':{'Override':True},'FrameOptions':{'FrameOption':'DENY','Override':True},
        'ReferrerPolicy':{'ReferrerPolicy':'no-referrer','Override':True},'StrictTransportSecurity':{'AccessControlMaxAgeSec':31536000,'IncludeSubdomains':True,'Override':True}},
    'CustomHeadersConfig':{'Items':[{'Header':'Permissions-Policy','Value':'camera=(self), microphone=()','Override':True}]}}})
add('CDN','AWS::CloudFront::Distribution',{'DistributionConfig':{'Enabled':True,'DefaultRootObject':'index.html','HttpVersion':'http2','PriceClass':'PriceClass_100',
    'Origins':[{'Id':'web','DomainName':{'Fn::GetAtt':['Web','RegionalDomainName']},'S3OriginConfig':{'OriginAccessIdentity':''},'OriginAccessControlId':ref('OAC')}],
    'DefaultCacheBehavior':{'TargetOriginId':'web','ViewerProtocolPolicy':'redirect-to-https','AllowedMethods':['GET','HEAD'],'CachedMethods':['GET','HEAD'],
       'Compress':True,'CachePolicyId':'658327ea-f89d-4fab-a63d-7e88639e58f6','ResponseHeadersPolicyId':ref('Headers')},
    'ViewerCertificate':{'CloudFrontDefaultCertificate':True}}})
portal=sub('https://${CDN.DomainName}')
add('Raw','AWS::S3::Bucket',{**secure,'BucketName':raw_name,
    'CorsConfiguration':{'CorsRules':[{'AllowedOrigins':[portal],'AllowedMethods':['POST'],'AllowedHeaders':['*'],'MaxAge':300}]},
    'NotificationConfiguration':{'QueueConfigurations':[{'Event':'s3:ObjectCreated:*','Queue':arn('UploadQueue'),'Filter':{'S3Key':{'Rules':[{'Name':'prefix','Value':'raw/'}]}}}]},
    'LifecycleConfiguration':{'Rules':[{'Id':'RawFallback','Prefix':'raw/','Status':'Enabled','ExpirationInDays':1,'NoncurrentVersionExpiration':{'NoncurrentDays':1},'AbortIncompleteMultipartUpload':{'DaysAfterInitiation':1}}]}},
    DependsOn='QueuePolicy',DeletionPolicy='Retain',UpdateReplacePolicy='Retain')
for name in ['Raw','Reports','Web']:
    statements=[{'Effect':'Deny','Principal':'*','Action':'s3:*','Resource':[arn(name),sub('${'+name+'.Arn}/*')], 'Condition':{'Bool':{'aws:SecureTransport':'false'}}}]
    if name=='Web': statements.append({'Effect':'Allow','Principal':{'Service':'cloudfront.amazonaws.com'},'Action':'s3:GetObject','Resource':sub('${Web.Arn}/*'),
        'Condition':{'StringEquals':{'AWS:SourceArn':sub('arn:${AWS::Partition}:cloudfront::${AWS::AccountId}:distribution/${CDN}')}}})
    add(name+'Policy','AWS::S3::BucketPolicy',{'Bucket':ref(name),'PolicyDocument':{'Version':'2012-10-17','Statement':statements}})
add('Pool','AWS::Cognito::UserPool',{'UserPoolName':sub('${AWS::StackName}-users'),'AdminCreateUserConfig':{'AllowAdminCreateUserOnly':True},
    'UsernameConfiguration':{'CaseSensitive':False},'AutoVerifiedAttributes':['email'],
    'Policies':{'PasswordPolicy':{'MinimumLength':12,'RequireLowercase':True,'RequireUppercase':True,'RequireNumbers':True,'RequireSymbols':True,'TemporaryPasswordValidityDays':7}}},DeletionPolicy='Retain',UpdateReplacePolicy='Retain')
add('Client','AWS::Cognito::UserPoolClient',{'UserPoolId':ref('Pool'),'GenerateSecret':False,'ExplicitAuthFlows':['ALLOW_USER_PASSWORD_AUTH','ALLOW_REFRESH_TOKEN_AUTH'],
    'PreventUserExistenceErrors':'ENABLED','EnableTokenRevocation':True,'IdTokenValidity':1,'AccessTokenValidity':1,'RefreshTokenValidity':1,
    'TokenValidityUnits':{'IdToken':'hours','AccessToken':'hours','RefreshToken':'days'}})
for group in ['Admin','Kiosk']: add(group+'Group','AWS::Cognito::UserPoolGroup',{'UserPoolId':ref('Pool'),'GroupName':group})
add('Api','AWS::Serverless::Api',{'StageName':'prod','EndpointConfiguration':{'Type':'REGIONAL'},
    'Cors':{'AllowOrigin':sub("'https://${CDN.DomainName}'"),'AllowMethods':"'GET,POST,OPTIONS'",'AllowHeaders':"'Authorization,Content-Type'"},
    'Auth':{'DefaultAuthorizer':'Login','AddDefaultAuthorizerToCorsPreflight':False,'Authorizers':{'Login':{'UserPoolArn':arn('Pool')}}},
    'MethodSettings':[{'ResourcePath':'/*','HttpMethod':'*','ThrottlingRateLimit':10,'ThrottlingBurstLimit':20}],
    'GatewayResponses':{'DEFAULT_4XX':{'ResponseParameters':{'Headers':{'Access-Control-Allow-Origin':sub("'https://${CDN.DomainName}'")}}},
                        'DEFAULT_5XX':{'ResponseParameters':{'Headers':{'Access-Control-Allow-Origin':sub("'https://${CDN.DomainName}'")}}}}})
env={n.upper()+'_TABLE':ref(n) for n in ['Employees','Attendance','Sessions','Config','Audit']}
env.update(CLIENT_ID=ref('Client'),RAW_BUCKET=ref('Raw'),REPORT_BUCKET=ref('Reports'),COLLECTION_ID=ref('Collection'),BUSINESS_TZ=ref('BusinessTimezone'),PORTAL_URL=portal)
collection_arn=sub('arn:${AWS::Partition}:rekognition:${AWS::Region}:${AWS::AccountId}:collection/${Collection}')
def function(name,handler,statements,events=None,extra_env=None,timeout=60):
    # Explicit roles prevent SAM from adding an all-queues managed polling policy.
    # Deterministic log groups exist before the function/event mapping can run.
    log_name=sub('/aws/lambda/${AWS::StackName}-'+name)
    add(name+'Logs','AWS::Logs::LogGroup',{'LogGroupName':log_name,'RetentionInDays':14})
    statements.append(allow(['logs:CreateLogStream','logs:PutLogEvents'],sub('arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:/aws/lambda/${AWS::StackName}-'+name+':*')))
    add(name+'Role','AWS::IAM::Role',{'AssumeRolePolicyDocument':{'Version':'2012-10-17','Statement':[{'Effect':'Allow','Principal':{'Service':'lambda.amazonaws.com'},'Action':'sts:AssumeRole'}]},
        'Policies':[{'PolicyName':'runtime','PolicyDocument':{'Version':'2012-10-17','Statement':statements}}]})
    add(name,'AWS::Serverless::Function',{'FunctionName':sub('${AWS::StackName}-'+name),'CodeUri':'backend/','Handler':'app.'+handler,'Runtime':'python3.14','Architectures':['x86_64'],'MemorySize':512,'Timeout':timeout,
        'Role':arn(name+'Role'),'Environment':{'Variables':{**env,**(extra_env or {})}},**({'Events':events} if events else {})},DependsOn=name+'Logs')
function('Report','report',[db(['Employees'],['Scan']),db(['Config'],['GetItem']),db(['Attendance'],['GetItem','PutItem']),allow(['s3:PutObject'],sub('${Reports.Arn}/reports/*'))],timeout=120)
function('ApiFunction','api',[db(['Employees'],['GetItem','Scan','PutItem','UpdateItem']),db(['Attendance'],['GetItem','Query','PutItem']),db(['Sessions','Config'],['GetItem','PutItem']),db(['Audit'],['PutItem']),allow(['s3:PutObject'],sub('${Raw.Arn}/raw/*')),
    allow(['s3:GetObject'],sub('${Reports.Arn}/reports/*')),allow(['s3:ListBucket'],arn('Reports'),Condition={'StringLike':{'s3:prefix':['reports/*']}}),
    allow(['rekognition:ListFaces','rekognition:DeleteFaces'],collection_arn),allow(['lambda:InvokeFunction'],arn('Report'))],
    {'Proxy':{'Type':'Api','Properties':{'RestApiId':ref('Api'),'Path':'/{proxy+}','Method':'ANY'}}},{'REPORT_FUNCTION':ref('Report')},timeout=29)
function('Recognition','ingest',[db(['Employees'],['GetItem','PutItem','ConditionCheckItem']),db(['Attendance'],['GetItem','PutItem']),db(['Sessions'],['GetItem','PutItem','UpdateItem']),db(['Config'],['GetItem','UpdateItem','DeleteItem']),db(['Audit'],['PutItem']),
    allow(['s3:GetObjectVersion','s3:DeleteObjectVersion'],sub('${Raw.Arn}/raw/*')),
    allow(['sqs:ReceiveMessage','sqs:DeleteMessage','sqs:GetQueueAttributes'],arn('UploadQueue')),
    allow(['rekognition:DetectFaces'],'*'),allow(['rekognition:SearchFacesByImage','rekognition:IndexFaces'],collection_arn)],
    {'Uploads':{'Type':'SQS','Properties':{'Queue':arn('UploadQueue'),'BatchSize':1,'FunctionResponseTypes':['ReportBatchItemFailures']}}})
function('Cleanup','cleanup',[db(['Employees'],['GetItem','Scan','UpdateItem']),db(['Sessions'],['Scan','UpdateItem']),db(['Config'],['GetItem','PutItem','DeleteItem']),allow(['s3:ListBucketVersions'],arn('Raw'),Condition={'StringLike':{'s3:prefix':['raw/*']}}),
    allow(['s3:DeleteObjectVersion'],sub('${Raw.Arn}/raw/*')),allow(['rekognition:ListFaces','rekognition:DeleteFaces'],collection_arn)],
    {'Tick':{'Type':'Schedule','Properties':{'Schedule':'rate(5 minutes)'}}},timeout=120)
add('ScheduleRole','AWS::IAM::Role',{'AssumeRolePolicyDocument':{'Version':'2012-10-17','Statement':[{'Effect':'Allow','Principal':{'Service':'scheduler.amazonaws.com'},'Action':'sts:AssumeRole',
    'Condition':{'StringEquals':{'aws:SourceAccount':ref('AWS::AccountId')}}}]},'Policies':[{'PolicyName':'invoke-reports','PolicyDocument':{'Version':'2012-10-17','Statement':[allow(['lambda:InvokeFunction'],arn('Report')),allow(['sqs:SendMessage'],arn('DeadLetters'))]}}]})
for name,cron,payload in [('Daily','cron(59 23 * * ? *)',{'mode':'daily'}),('Reconcile','cron(10 0 * * ? *)',{'mode':'daily','days_ago':1}),('Weekly','cron(0 1 ? * MON *)',{'mode':'weekly'})]:
    add(name+'Schedule','AWS::Scheduler::Schedule',{'Name':sub('${AWS::StackName}-'+name.lower()),'ScheduleExpression':cron,'ScheduleExpressionTimezone':ref('BusinessTimezone'),
        'FlexibleTimeWindow':{'Mode':'OFF'},'Target':{'Arn':arn('Report'),'RoleArn':arn('ScheduleRole'),'Input':json.dumps(payload),
        'RetryPolicy':{'MaximumRetryAttempts':2,'MaximumEventAgeInSeconds':3600},'DeadLetterConfig':{'Arn':arn('DeadLetters')}}})
# Scheduler acceptance is asynchronous; capture Lambda execution failures separately.
add('ReportInvokeConfig','AWS::Lambda::EventInvokeConfig',{'FunctionName':ref('Report'),'Qualifier':'$LATEST','MaximumRetryAttempts':2,
    'DestinationConfig':{'OnFailure':{'Destination':arn('DeadLetters')}}})
R['ReportRole']['Properties']['Policies'][0]['PolicyDocument']['Statement'].append(allow(['sqs:SendMessage'],arn('DeadLetters')))
add('Alerts','AWS::SNS::Topic',{'Subscription':[{'Protocol':'email','Endpoint':ref('AdminEmail')}]})
for name in ['Recognition','Cleanup','Report','ApiFunction']:
    add(name+'ErrorAlarm','AWS::CloudWatch::Alarm',{'Namespace':'AWS/Lambda','MetricName':'Errors','Dimensions':[{'Name':'FunctionName','Value':ref(name)}],
        'Statistic':'Sum','Period':300,'EvaluationPeriods':1,'Threshold':0,'ComparisonOperator':'GreaterThanThreshold','TreatMissingData':'notBreaching','AlarmActions':[ref('Alerts')]})
add('QueueAlarm','AWS::CloudWatch::Alarm',{'Namespace':'AWS/SQS','MetricName':'ApproximateNumberOfMessagesVisible','Dimensions':[{'Name':'QueueName','Value':{'Fn::GetAtt':['DeadLetters','QueueName']}}],
    'Statistic':'Maximum','Period':60,'EvaluationPeriods':1,'Threshold':0,'ComparisonOperator':'GreaterThanThreshold','TreatMissingData':'notBreaching','AlarmActions':[ref('Alerts')]})
outputs={'ApiUrl':sub('https://${Api}.execute-api.${AWS::Region}.${AWS::URLSuffix}/prod'),'PortalUrl':portal,'UserPoolId':ref('Pool'),'ClientId':ref('Client'),
    'WebBucket':ref('Web'),'RawBucket':ref('Raw'),'ReportBucket':ref('Reports'),'DistributionId':ref('CDN'),'CollectionId':ref('Collection'),
    'Region':ref('AWS::Region'),'ReportFunction':ref('Report'),'CleanupFunction':ref('Cleanup'),'DeadLetterQueueUrl':ref('DeadLetters')}
outputs.update({n+'Table':ref(n) for n in ['Employees','Attendance','Sessions','Config','Audit']})
t={'AWSTemplateFormatVersion':'2010-09-09','Transform':'AWS::Serverless-2016-10-31','Description':'AttendFlow consent-based attendance demonstration',
   'Parameters':{'AdminEmail':{'Type':'String','Description':'Inbox for operational SNS alerts'},'BusinessTimezone':{'Type':'String','Default':'Asia/Kolkata','AllowedValues':['Asia/Kolkata','UTC','America/New_York','Europe/London']}},
   'Resources':R,'Outputs':{k:{'Value':v} for k,v in outputs.items()}}
(ROOT/'template.json').write_text(json.dumps(t,indent=2)+'\n')
print('Generated template.json. Runtime: python3.14. No AWS resources were created.')

# HARDENING_TRACING_HOOK
from pathlib import Path
import runpy as _hardening_runpy
_hardening_runpy.run_path(str(Path(__file__).resolve().with_name("apply_tracing.py")))

# HARDENING_ROLE_SCOPES_HOOK
import runpy as _role_runpy
from pathlib import Path
_role_runpy.run_path(str(Path(__file__).resolve().with_name("apply_role_scopes.py")))


# HARDENING_MONITORING_HOOK
import runpy as _monitoring_runpy
from pathlib import Path
_monitoring_runpy.run_path(str(Path(__file__).resolve().with_name("apply_monitoring.py")))


# HARDENING_SCHEDULER_SCOPE_HOOK
import runpy as _scheduler_scope_runpy
from pathlib import Path
_scheduler_scope_runpy.run_path(str(Path(__file__).resolve().with_name("apply_scheduler_scope.py")))


# HARDENING_STORAGE_PROTECTION_HOOK
import runpy as _storage_protection_runpy
from pathlib import Path
_storage_protection_runpy.run_path(str(Path(__file__).resolve().with_name("apply_storage_protection.py")))
