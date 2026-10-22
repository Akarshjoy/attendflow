"""Local AWS simulations. These do not establish real biometric accuracy or latency."""
import importlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import domain
from domain import RuleError,aggregate,choose_match,eligible,transition,validate_face

@pytest.fixture
def aws(monkeypatch):
    for k,v in {'AWS_ACCESS_KEY_ID':'testing','AWS_SECRET_ACCESS_KEY':'testing','AWS_DEFAULT_REGION':'us-east-1','BUSINESS_TZ':'Asia/Kolkata',
                'RAW_BUCKET':'attendflow-test-raw','REPORT_BUCKET':'attendflow-test-reports','COLLECTION_ID':'test-collection','PORTAL_URL':'https://example.com','REPORT_FUNCTION':'report-test'}.items():monkeypatch.setenv(k,v)
    with mock_aws():
        db=boto3.resource('dynamodb')
        for name,pk,sk in [('employees','employee_id',None),('attendance','employee_id','date'),('sessions','session_id',None),('config','config_id',None),('audit','event_id',None)]:
            monkeypatch.setenv(name.upper()+'_TABLE',name)
            keys=[{'AttributeName':pk,'KeyType':'HASH'}]+([{'AttributeName':sk,'KeyType':'RANGE'}] if sk else [])
            db.create_table(TableName=name,KeySchema=keys,AttributeDefinitions=[{'AttributeName':x['AttributeName'],'AttributeType':'S'} for x in keys],BillingMode='PAY_PER_REQUEST')
        s3=boto3.client('s3')
        for bucket in ['attendflow-test-raw','attendflow-test-reports']:
            s3.create_bucket(Bucket=bucket);s3.put_bucket_versioning(Bucket=bucket,VersioningConfiguration={'Status':'Enabled'})
        import app
        yield app

def employee(**changes):
    return {'employee_id':'e1','name':'Demo Employee','department':'Engineering','start_date':'2026-01-01','workdays':[0,1,2,3,4,5,6],'late_after':'09:15','active':True,'version':1,'consent_at':'2026-01-01T00:00:00+00:00','face_id':'face-1',**changes}

def stamp(h=3,m=30,day=19):return datetime(2026,10,day,h,m,tzinfo=timezone.utc)
def call(app,path,method='GET',body=None,roles='Admin',query=None,sub='admin'):
    return app.api({'httpMethod':method,'path':path,'body':json.dumps(body or {}),'queryStringParameters':query,'requestContext':{'authorizer':{'claims':{'sub':sub,'cognito:groups':roles}}}},None)
def decoded(r):return json.loads(r['body'])
def store_employee(app,**kw):
    e=employee(**kw);app.table('employees').put_item(Item=e);return e

def job(app,sid='s1',**kw):
    j={'session_id':sid,'owner':'kiosk','mode':'attendance','action':'in','employee_id':'','key':f'raw/{sid}/image','state':'PROCESSING','lease_owner':'worker','expires_at':9999999999,'created_at':domain.iso(stamp()),'ttl':9999999999,**kw}
    app.table('sessions').put_item(Item=j);return j

def face():return {'Confidence':99.99,'Quality':{'Brightness':80,'Sharpness':90},'Pose':{'Yaw':0,'Pitch':0}}
def matches(eid='e1',fid='face-1',similarity=99.9):return [{'Face':{'FaceId':fid,'ExternalImageId':eid},'Similarity':similarity}]

def test_timezone_day_boundary():
    assert domain.local_day(datetime(2026,10,18,20,tzinfo=timezone.utc),'Asia/Kolkata')=='2026-10-19'

def test_present_at_cutoff():assert transition(None,employee(),'in',stamp(3,45),'Asia/Kolkata',[])['status']=='present'
def test_late_after_cutoff():assert transition(None,employee(),'in',stamp(3,46),'Asia/Kolkata',[])['status']=='late'
def test_out_keeps_late():
    r=transition(None,employee(),'in',stamp(4),'Asia/Kolkata',[])
    assert transition(r,employee(),'out',stamp(12),'Asia/Kolkata',[])['status']=='late'
@pytest.mark.parametrize('action', ['out','bad'])
def test_invalid_first_action(action):
    with pytest.raises(RuleError):transition(None,employee(),action,stamp(),'Asia/Kolkata',[])
def test_duplicate_in_out():
    r=transition(None,employee(),'in',stamp(),'Asia/Kolkata',[])
    with pytest.raises(RuleError):transition(r,employee(),'in',stamp(),'Asia/Kolkata',[])
    r=transition(r,employee(),'out',stamp(12),'Asia/Kolkata',[])
    with pytest.raises(RuleError):transition(r,employee(),'out',stamp(13),'Asia/Kolkata',[])
def test_out_before_in():
    r=transition(None,employee(),'in',stamp(),'Asia/Kolkata',[])
    with pytest.raises(RuleError):transition(r,employee(),'out',stamp(2),'Asia/Kolkata',[])
def test_holiday_and_end_date():
    assert not eligible(employee(),'2026-10-19',['2026-10-19'])
    assert not eligible(employee(end_date='2026-10-18'),'2026-10-19',[])
    assert not eligible(employee(start_date='2026-10-20'),'2026-10-19',[])
def test_weekend_not_absent():assert not eligible(employee(workdays=[0,1,2,3,4]),'2026-10-18',[])
def test_absent_can_be_replaced_by_valid_in():
    assert transition({'employee_id':'e1','date':'2026-10-19','status':'absent','version':1},employee(),'in',stamp(),'Asia/Kolkata',[])['version']==2
@pytest.mark.parametrize('details',[[],[face(),face()],[{**face(),'Confidence':98}],[{**face(),'Quality':{'Brightness':10,'Sharpness':80}}],[{**face(),'Pose':{'Yaw':70}}]])
def test_bad_faces_rejected(details):
    with pytest.raises(RuleError):validate_face(details)
def test_valid_face():validate_face([face()])
def test_low_similarity():
    with pytest.raises(RuleError):choose_match(matches(similarity=98.9))
def test_ambiguous_match():
    with pytest.raises(RuleError):choose_match(matches()+matches(eid='e2',similarity=99.3))
def test_same_employee_face_not_ambiguous():assert choose_match(matches()+matches(fid='other',similarity=99.4))['Face']['FaceId']=='face-1'
def test_percentages_include_late():
    r=aggregate([{'status':'present','clock_in':'x','clock_out':'y'},{'status':'late','clock_in':'x'},{'status':'absent'}])
    assert r['present_pct']==66.67 and r['late_pct']==33.33 and r['missing_clock_out']==1

def test_anonymous_denied(aws):assert call(aws,'/employees',sub='')['statusCode']==401
def test_kiosk_cannot_list_employees(aws):assert call(aws,'/employees',roles='Kiosk')['statusCode']==403
def test_kiosk_cannot_enroll(aws):assert call(aws,'/sessions','POST',{'mode':'enroll'},roles='Kiosk')['statusCode']==403
def test_manual_only_employee(aws):
    r=call(aws,'/employees','POST',{'name':'Private Person','department':'IT','start_date':'2026-10-01','consent':False})
    assert r['statusCode']==201 and decoded(r)['consent_at']==''
def test_no_consent_no_enrollment(aws):
    store_employee(aws,consent_at='',face_id='')
    assert call(aws,'/sessions','POST',{'mode':'enroll','employee_id':'e1'})['statusCode']==400

def test_upload_is_bounded(aws):
    r=decoded(call(aws,'/sessions','POST',{'mode':'attendance','action':'in'},roles='Kiosk'))
    import base64
    policy=json.loads(base64.b64decode(r['upload']['fields']['policy']))
    assert ['content-length-range',1,3*1024*1024] in policy['conditions']
    assert {'x-amz-server-side-encryption':'AES256'} in policy['conditions']
def test_session_owner_isolation(aws):
    job(aws)
    assert call(aws,'/sessions/s1',roles='Kiosk',sub='other')['statusCode']==404

def test_atomic_attendance_and_replay(aws):
    e=store_employee(aws);j=job(aws);aws.record(j,e,stamp())
    assert aws.get('sessions',{'session_id':'s1'})['state']=='DONE'
    assert aws.get('attendance',{'employee_id':'e1','date':'2026-10-19'})['version']==1
    # Duplicate queue delivery sees terminal state and never executes recognition.
    aws.process_object(os.environ['RAW_BUCKET'],'raw/s1/image','old-version')
    assert len(aws.scan('audit'))==1

def test_independent_duplicate_capture_does_not_rewrite(aws):
    e=store_employee(aws);aws.record(job(aws),e,stamp())
    with pytest.raises(RuleError):aws.record(job(aws,'s2'),e,stamp(3,31))
    assert aws.get('attendance',{'employee_id':'e1','date':'2026-10-19'})['version']==1

def test_withdrawal_prevents_stale_match(aws):
    e=store_employee(aws);j=job(aws)
    store_employee(aws,consent_at='',version=2,face_id='')
    with pytest.raises(RuleError):aws.record(j,e,stamp())
    assert not aws.scan('attendance')

def test_transaction_rollback_on_session_conflict(aws):
    e=store_employee(aws);j=job(aws);j['lease_owner']='not-the-owner'
    with pytest.raises(ClientError):aws.record(j,e,stamp())
    assert not aws.scan('attendance') and not aws.scan('audit')

def test_decimal_versions_stay_numbers(aws):
    store_employee(aws);e=aws.get('employees',{'employee_id':'e1'})
    assert 'N' in aws.encoded(e)['version']

def test_manual_correction_audited_and_conflict_checked(aws,monkeypatch):
    store_employee(aws);monkeypatch.setattr(aws,'utcnow',lambda:stamp(14))
    data={'employee_id':'e1','date':'2026-10-19','status':'present','clock_in':domain.iso(stamp()),'reason':'Camera unavailable','version':0}
    r=call(aws,'/manual','POST',data)
    assert r['statusCode']==200
    assert len(aws.scan('audit'))==1
    assert call(aws,'/manual','POST',data)['statusCode']==400

def test_absence_job_idempotent(aws,monkeypatch):
    store_employee(aws);monkeypatch.setattr(aws,'utcnow',lambda:stamp(20))
    aws.report({'mode':'daily','date':'2026-10-19'},None);aws.report({'mode':'daily','date':'2026-10-19'},None)
    rows=aws.scan('attendance');assert len(rows)==1 and rows[0]['status']=='absent'
def test_daily_does_not_overwrite_clock_in(aws,monkeypatch):
    e=store_employee(aws);aws.record(job(aws),e,stamp());monkeypatch.setattr(aws,'utcnow',lambda:stamp(20))
    aws.report({'mode':'daily','date':'2026-10-19'},None)
    assert aws.scan('attendance')[0]['status']=='present'
def test_daytime_report_no_false_absence(aws,monkeypatch):
    store_employee(aws);monkeypatch.setattr(aws,'utcnow',lambda:stamp(5))
    r=aws.report({'mode':'daily','date':'2026-10-19'},None)
    assert r['summary']['scheduled_days']==0 and not aws.scan('attendance')
def test_report_excludes_holiday(aws,monkeypatch):
    store_employee(aws);aws.table('config').put_item(Item={'config_id':'policy','holidays':['2026-10-19'],'similarity':99})
    monkeypatch.setattr(aws,'utcnow',lambda:stamp(20))
    aws.report({'mode':'daily','date':'2026-10-19'},None);assert not aws.scan('attendance')
def test_policy_optimistic_version(aws):
    assert call(aws,'/config','POST',{'holidays':[],'similarity':99,'version':0})['statusCode']==200
    assert call(aws,'/config','POST',{'holidays':[],'similarity':99,'version':0})['statusCode']==400

def mock_rek(aws,monkeypatch):
    rek=Mock();rek.detect_faces.return_value={'FaceDetails':[face()]};rek.search_faces_by_image.return_value={'FaceMatches':matches()};rek.list_faces.return_value={'Faces':[]}
    original=aws.client;monkeypatch.setattr(aws,'client',lambda name:rek if name=='rekognition' else original(name))
    return rek

def image_job(aws,sid='s1',**kw):
    j=job(aws,sid,state='WAITING',**kw);j.pop('lease_owner',None);aws.table('sessions').put_item(Item=j)
    result=boto3.client('s3').put_object(Bucket=os.environ['RAW_BUCKET'],Key=j['key'],Body=b'\xff\xd8\xff' + b'demo-image',ContentType='image/jpeg')
    return j,result['VersionId']

def test_recognition_pipeline_and_physical_delete(aws,monkeypatch):
    # Stub only the ML response; S3, DynamoDB and transactions use Moto.
    store_employee(aws,start_date='2020-01-01');mock_rek(aws,monkeypatch);j,v=image_job(aws)
    aws.process_object(os.environ['RAW_BUCKET'],j['key'],v)
    assert aws.get('sessions',{'session_id':'s1'})['state']=='DONE'
    assert not boto3.client('s3').list_object_versions(Bucket=os.environ['RAW_BUCKET']).get('Versions')
    assert len(aws.scan('attendance'))==1

def test_no_face_rejected_without_attendance(aws,monkeypatch):
    rek=mock_rek(aws,monkeypatch);rek.detect_faces.return_value={'FaceDetails':[]};j,v=image_job(aws)
    aws.process_object(os.environ['RAW_BUCKET'],j['key'],v)
    assert aws.get('sessions',{'session_id':'s1'})['state']=='REJECTED' and not aws.scan('attendance')

def test_enrollment_indexes_and_maps_face(aws,monkeypatch):
    store_employee(aws,face_id='');rek=mock_rek(aws,monkeypatch);rek.search_faces_by_image.return_value={'FaceMatches':[]}
    rek.index_faces.return_value={'FaceRecords':[{'Face':{'FaceId':'new-face'}}]}
    j,v=image_job(aws,mode='enroll',employee_id='e1')
    aws.process_object(os.environ['RAW_BUCKET'],j['key'],v)
    assert aws.get('employees',{'employee_id':'e1'})['face_id']=='new-face'
    assert aws.get('sessions',{'session_id':'s1'})['state']=='DONE'

def test_sqs_partial_failure(aws,monkeypatch):
    monkeypatch.setattr(aws,'process_object',Mock(side_effect=RuntimeError('network')))
    event={'Records':[{'messageId':'m1','body':json.dumps({'Records':[{'eventSource':'aws:s3','s3':{'bucket':{'name':'x'},'object':{'key':'raw/s1/image','versionId':'1'}}}]})},{'messageId':'m2','body':json.dumps({'Event':'s3:TestEvent'})}]}
    assert aws.ingest(event,None)=={'batchItemFailures':[{'itemIdentifier':'m1'}]}

def test_remove_consent_removes_vectors_and_preserves_history(aws,monkeypatch):
    store_employee(aws);rek=mock_rek(aws,monkeypatch);rek.list_faces.return_value={'Faces':[{'FaceId':'face-1','ExternalImageId':'e1'}]}
    r=call(aws,'/employees/e1/remove-face','POST')
    assert r['statusCode']==200
    e=aws.get('employees',{'employee_id':'e1'});assert not e.get('face_id') and not e['consent_at']
    rek.delete_faces.assert_called_once()

def test_cleanup_deletes_all_expired_versions(aws,monkeypatch):
    mock_rek(aws,monkeypatch);s3=boto3.client('s3')
    for _ in range(2):s3.put_object(Bucket=os.environ['RAW_BUCKET'],Key='raw/old/image',Body=b'x')
    monkeypatch.setattr(aws,'utcnow',lambda:datetime.now(timezone.utc)+timedelta(hours=2))
    assert aws.cleanup({},None)['deleted_versions']==2
    assert not s3.list_object_versions(Bucket=os.environ['RAW_BUCKET']).get('Versions')

def test_csv_neutralizes_formulas(aws):
    store_employee(aws,name='=HYPERLINK("bad")')
    aws.table('attendance').put_item(Item={'employee_id':'e1','date':'2026-10-19','name':'=BAD()','status':'absent','version':1})
    r=decoded(call(aws,'/export',query={'start':'2026-10-19','end':'2026-10-19'}))
    assert "'=BAD()" in r['csv']

def test_template_security():
    t=json.loads((Path(__file__).resolve().parents[1]/'template.json').read_text());r=t['Resources']
    assert r['Api']['Properties']['Auth']['DefaultAuthorizer']=='Login'
    assert r['Raw']['Properties']['VersioningConfiguration']['Status']=='Enabled'
    assert r['UploadQueue']['Properties']['VisibilityTimeout']>=6*r['Recognition']['Properties']['Timeout']
    assert r['DailySchedule']['Properties']['ScheduleExpression']=='cron(59 23 * * ? *)'
    for n in ['Employees','Attendance','Sessions','Config','Audit']:assert r[n]['Properties']['SSESpecification']['SSEEnabled']

def test_wrong_app_client_rejected(aws,monkeypatch):
    monkeypatch.setenv('CLIENT_ID','required-client')
    assert call(aws,'/me')['statusCode']==401

def test_raw_policy_replay_cannot_replace_accepted_version(aws,monkeypatch):
    rek=mock_rek(aws,monkeypatch);j,v=image_job(aws)
    aws.table('sessions').update_item(Key={'session_id':j['session_id']},UpdateExpression='SET object_version = :v',ExpressionAttributeValues={':v':v})
    v2=boto3.client('s3').put_object(Bucket=os.environ['RAW_BUCKET'],Key=j['key'],Body=b'\xff\xd8\xffother')['VersionId']
    aws.process_object(os.environ['RAW_BUCKET'],j['key'],v2)
    rek.detect_faces.assert_not_called()
    versions=boto3.client('s3').list_object_versions(Bucket=os.environ['RAW_BUCKET'])['Versions']
    assert [x['VersionId'] for x in versions]==[v]

def test_active_worker_retry_preserves_image(aws):
    j,v=image_job(aws)
    import time
    aws.table('sessions').update_item(Key={'session_id':j['session_id']},UpdateExpression='SET #s = :s, lease_until = :u, object_version = :v',ExpressionAttributeNames={'#s':'state'},ExpressionAttributeValues={':s':'PROCESSING',':u':int(time.time())+100,':v':v})
    with pytest.raises(RuntimeError):aws.process_object(os.environ['RAW_BUCKET'],j['key'],v)
    assert boto3.client('s3').list_object_versions(Bucket=os.environ['RAW_BUCKET']).get('Versions')

def test_bad_image_bytes_rejected_without_ml_charge(aws,monkeypatch):
    rek=mock_rek(aws,monkeypatch);j=job(aws,state='WAITING')
    v=boto3.client('s3').put_object(Bucket=os.environ['RAW_BUCKET'],Key=j['key'],Body=b'not-an-image')['VersionId']
    aws.process_object(os.environ['RAW_BUCKET'],j['key'],v)
    rek.detect_faces.assert_not_called()
    assert aws.get('sessions',{'session_id':'s1'})['state']=='REJECTED'

def test_orphan_vector_cleanup_preserves_active_enrollment(aws,monkeypatch):
    store_employee(aws);rek=mock_rek(aws,monkeypatch)
    rek.list_faces.return_value={'Faces':[{'FaceId':'face-1','ExternalImageId':'e1'},{'FaceId':'orphan','ExternalImageId':'e1'}]}
    aws.cleanup({},None)
    rek.delete_faces.assert_not_called()
    old=domain.utcnow()+timedelta(hours=2);monkeypatch.setattr(aws,'utcnow',lambda:old)
    aws.cleanup({},None)
    rek.delete_faces.assert_called_once_with(CollectionId='test-collection',FaceIds=['orphan'])

def test_manual_future_times_rejected(aws,monkeypatch):
    store_employee(aws);monkeypatch.setattr(aws,'utcnow',lambda:stamp(5))
    r=call(aws,'/manual','POST',{'employee_id':'e1','date':'2026-10-19','status':'present','clock_in':domain.iso(stamp(6)),'reason':'testing','version':0})
    assert r['statusCode']==400 and not aws.scan('attendance')

def test_runtime_role_has_no_all_queue_permissions():
    t=json.loads((Path(__file__).resolve().parents[1]/'template.json').read_text())
    role=t['Resources']['RecognitionRole']['Properties']
    assert not role.get('ManagedPolicyArns')
    queue=[s for s in role['Policies'][0]['PolicyDocument']['Statement'] if 'sqs:ReceiveMessage' in s['Action']]
    assert queue[0]['Resource']=={'Fn::GetAtt':['UploadQueue','Arn']}
