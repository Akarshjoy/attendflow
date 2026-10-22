"""AttendFlow handlers. See docs/design.md for trust boundaries and limitations."""
import csv
import io
import json
import logging
import os
import time
import uuid
from datetime import date, timedelta
from decimal import Decimal
from urllib.parse import unquote_plus

import boto3
from boto3.dynamodb.conditions import Key
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError
from domain import (RuleError, aggregate, choose_match, eligible, iso, local_day,
                    parse_ts, transition, utcnow, validate_face)

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
MAX_IMAGE = 3 * 1024 * 1024
SER = TypeSerializer()
TERMINAL = {'DONE', 'REJECTED', 'FAILED', 'EXPIRED'}

def table(name):
    return boto3.resource('dynamodb').Table(os.environ[name.upper() + '_TABLE'])

def client(name):
    return boto3.client(name)

def encoded(obj):
    def normalize(v):
        if isinstance(v, float): return Decimal(str(v))
        if isinstance(v, dict): return {k: normalize(x) for k, x in v.items()}
        if isinstance(v, list): return [normalize(x) for x in v]
        return v
    return {k: SER.serialize(normalize(v)) for k, v in obj.items()}

def clean(obj):
    return json.loads(json.dumps(obj, default=lambda x: float(x) if isinstance(x, Decimal) else str(x)))

def get(name, key):
    return table(name).get_item(Key=key, ConsistentRead=True).get('Item')

def scan(name):
    rows, args = [], {}
    while True:
        r = table(name).scan(**args)
        rows.extend(r.get('Items', []))
        if not r.get('LastEvaluatedKey'):
            return rows
        args['ExclusiveStartKey'] = r['LastEvaluatedKey']

def query_attendance(eid, start, end):
    rows, args = [], {'KeyConditionExpression': Key('employee_id').eq(eid) & Key('date').between(start, end), 'ConsistentRead': True}
    while True:
        r = table('attendance').query(**args)
        rows.extend(r.get('Items', []))
        if not r.get('LastEvaluatedKey'):
            return rows
        args['ExclusiveStartKey'] = r['LastEvaluatedKey']

def config():
    return get('config', {'config_id': 'policy'}) or {'holidays': [], 'similarity': 99}

def groups(claims):
    raw = claims.get('cognito:groups', '')
    if isinstance(raw, list):
        return set(raw)
    return set(raw.strip('[]').replace('"', '').replace(' ', '').split(','))

def reply(status, data):
    return {'statusCode': status, 'headers': {'Content-Type': 'application/json',
        'Cache-Control': 'no-store', 'Access-Control-Allow-Origin': os.environ.get('PORTAL_URL', ''),
        'Access-Control-Allow-Headers': 'Authorization,Content-Type',
        'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'}, 'body': json.dumps(clean(data))}

def fail_condition(err):
    return isinstance(err, ClientError) and err.response['Error']['Code'] in ('ConditionalCheckFailedException', 'TransactionCanceledException')

def transaction(ops):
    # Use a fresh low-level client: mixing DynamoDB resource serialization hooks with
    # already serialized transactions leads to double-serialization.
    return client('dynamodb').transact_write_items(TransactItems=ops)

def put_op(name, item, condition=None, values=None, names=None):
    op = {'TableName': table(name).name, 'Item': encoded(item)}
    if condition:
        op['ConditionExpression'] = condition
    if values:
        op['ExpressionAttributeValues'] = encoded(values)
    if names:
        op['ExpressionAttributeNames'] = names
    return {'Put': op}

def emp_guard(employee):
    return {'ConditionCheck': {'TableName': table('employees').name,
        'Key': encoded({'employee_id': employee['employee_id']}),
        'ConditionExpression': '#v = :v AND active = :yes',
        'ExpressionAttributeNames': {'#v': 'version'},
        'ExpressionAttributeValues': encoded({':v': employee['version'], ':yes': True})}}

def audit_op(eid, actor, action, before, after, reason='', event_id=None):
    return put_op('audit', {'event_id': event_id or str(uuid.uuid4()), 'employee_id': eid,
        'at': iso(utcnow()), 'actor': actor, 'action': action, 'reason': reason,
        'before': before or {}, 'after': after or {}}, 'attribute_not_exists(event_id)')

def required_text(body, field, limit=120):
    value = str(body.get(field, '')).strip()
    if not value or len(value) > limit:
        raise RuleError(f'{field} is required (maximum {limit} characters).')
    return value

def api(event, context):
    try:
        claims = event.get('requestContext', {}).get('authorizer', {}).get('claims', {})
        if not claims.get('sub'):
            return reply(401, {'error': 'Sign in required.'})
        if os.environ.get('CLIENT_ID') and claims.get('aud') != os.environ['CLIENT_ID']:
            return reply(401, {'error': 'Wrong application token.'})
        roles = groups(claims)
        admin = 'Admin' in roles
        if not (admin or 'Kiosk' in roles):
            return reply(403, {'error': 'Admin or Kiosk access required.'})
        actor = claims['sub']
        method, path = event['httpMethod'], event['path'].rstrip('/')
        body = json.loads(event.get('body') or '{}')
        if not isinstance(body, dict):
            raise RuleError('Request body must be a JSON object.')
        q = event.get('queryStringParameters') or {}
        if method == 'GET' and path == '/me':
            return reply(200, {'roles': sorted(roles), 'timezone': os.environ['BUSINESS_TZ']})
        if method == 'POST' and path == '/sessions':
            mode = body.get('mode', 'attendance')
            if mode not in ('attendance', 'enroll') or (mode == 'enroll' and not admin):
                return reply(403, {'error': 'Enrollment requires Admin.'})
            eid = body.get('employee_id', '') if mode == 'enroll' else ''
            if mode == 'enroll':
                e = get('employees', {'employee_id': eid})
                if not e or not e['active'] or not e.get('consent_at'):
                    raise RuleError('An active employee with recorded consent is required.')
                if e.get('face_id'):
                    raise RuleError('Already enrolled. Remove enrollment before replacing it.')
            action = body.get('action', 'in')
            if action not in ('in', 'out'):
                raise RuleError('Choose Clock In or Clock Out.')
            mime = body.get('content_type', 'image/jpeg')
            if mime not in ('image/jpeg', 'image/png'):
                raise RuleError('Only JPEG or PNG images are accepted.')
            sid = str(uuid.uuid4())
            key = f'raw/{sid}/image'
            now = utcnow()
            job = {'session_id': sid, 'owner': actor, 'mode': mode, 'action': action,
                'employee_id': eid, 'key': key, 'state': 'WAITING', 'created_at': iso(now),
                'expires_at': int(now.timestamp()) + 120, 'ttl': int(now.timestamp()) + 86400}
            table('sessions').put_item(Item=job, ConditionExpression='attribute_not_exists(session_id)')
            # Signed POST is a presigned upload policy: exact key, size, MIME, encryption.
            upload = client('s3').generate_presigned_post(os.environ['RAW_BUCKET'], key,
                Fields={'Content-Type': mime, 'x-amz-server-side-encryption': 'AES256'},
                Conditions=[['content-length-range', 1, MAX_IMAGE], {'Content-Type': mime},
                    {'x-amz-server-side-encryption': 'AES256'}], ExpiresIn=60)
            return reply(201, {'session_id': sid, 'upload': upload})
        if method == 'GET' and path.startswith('/sessions/'):
            j = get('sessions', {'session_id': path.split('/')[-1]})
            if not j or (j['owner'] != actor and not admin):
                return reply(404, {'error': 'Session not found.'})
            state = j['state']
            if state == 'WAITING' and int(time.time()) > int(j['expires_at']) + 120:
                state = 'EXPIRED'
            return reply(200, {k: j[k] for k in ('session_id', 'result', 'error') if k in j} | {'state': state})
        if not admin:
            return reply(403, {'error': 'Admin access required.'})
        if method == 'GET' and path == '/employees':
            return reply(200, {'items': sorted(clean(scan('employees')), key=lambda e: e['name'].lower())})
        if method == 'POST' and path == '/employees':
            name = required_text(body, 'name')
            start = required_text(body, 'start_date', 10)
            date.fromisoformat(start)
            days = sorted(set(int(d) for d in body.get('workdays', [0,1,2,3,4])))
            if not days or any(d not in range(7) for d in days):
                raise RuleError('Select at least one valid working day.')
            late = body.get('late_after', '09:15')
            from datetime import time as dt_time
            dt_time.fromisoformat(late)
            eid = str(uuid.uuid4())
            e = {'employee_id': eid, 'name': name, 'department': required_text(body, 'department'),
                 'start_date': start, 'workdays': days, 'late_after': late, 'active': True,
                 'version': 1, 'consent_at': iso(utcnow()) if body.get('consent') is True else '', 'consent_recorded_by': actor}
            transaction([put_op('employees', e, 'attribute_not_exists(employee_id)'),
                         audit_op(eid, actor, 'create_employee', {}, e)])
            return reply(201, e)
        if method == 'POST' and path.startswith('/employees/') and path.endswith('/remove-face'):
            eid = path.split('/')[2]
            e = get('employees', {'employee_id': eid})
            if not e:
                raise RuleError('Unknown employee.')
            # First revoke enrollment in the directory atomically; recognition cannot
            # commit using a stale employee version. Then remove ALL matching vectors.
            before = dict(e)
            e.pop('face_id', None)
            e.pop('enrollment_session', None)
            e['version'] += 1
            e['consent_at'] = ''
            e['face_removal_pending'] = True
            transaction([put_op('employees', e, '#v = :v', {':v': before['version']}, {'#v':'version'}),
                         audit_op(eid, actor, 'revoke_face_consent', before, e)])
            remove_vectors(eid)
            table('employees').update_item(Key={'employee_id':eid}, UpdateExpression='REMOVE face_removal_pending')
            return reply(200, {'message': 'Enrollment revoked and stored face vectors removed. Manual attendance remains available.'})
        if method == 'POST' and path.startswith('/employees/') and path.endswith('/consent'):
            eid = path.split('/')[2]
            e = get('employees', {'employee_id': eid})
            if not e or e.get('face_removal_pending') or body.get('consent') is not True:
                raise RuleError('Employee and renewed consent required.')
            before = dict(e)
            e.update(consent_at=iso(utcnow()), consent_recorded_by=actor, version=e['version']+1)
            transaction([put_op('employees', e, '#v = :v', {':v':before['version']}, {'#v':'version'}),audit_op(eid,actor,'renew_consent',before,e)])
            return reply(200,e)
        if method == 'POST' and path.startswith('/employees/') and path.endswith('/deactivate'):
            eid = path.split('/')[2]
            e = get('employees', {'employee_id':eid})
            if not e:
                raise RuleError('Unknown employee.')
            before = dict(e)
            end = required_text(body,'end_date',10)
            date.fromisoformat(end)
            if end < e['start_date']:
                raise RuleError('End date precedes start date.')
            e.update(active=False, end_date=end, version=e['version']+1, consent_at='', face_removal_pending=True)
            e.pop('face_id',None)
            transaction([put_op('employees',e,'#v = :v',{':v':before['version']},{'#v':'version'}),audit_op(eid,actor,'deactivate',before,e)])
            remove_vectors(eid)
            table('employees').update_item(Key={'employee_id':eid},UpdateExpression='REMOVE face_removal_pending')
            return reply(200,{'message':'Deactivated and face vectors removed.'})
        if path == '/config':
            if method == 'GET':
                return reply(200, config())
            if method == 'POST':
                holidays = sorted(set(body.get('holidays', [])))
                if len(holidays) > 366:
                    raise RuleError('Too many holidays.')
                for d in holidays:
                    date.fromisoformat(d)
                threshold = int(body.get('similarity', 99))
                if not 99 <= threshold <= 100:
                    raise RuleError('Similarity threshold must be 99–100.')
                old = config()
                item = {'config_id':'policy','holidays':holidays,'similarity':threshold,'version':int(old.get('version',0))+1}
                if int(body.get('version',0)) != int(old.get('version',0)):
                    raise RuleError('Policy changed. Refresh before saving.')
                cond = '#v = :v' if 'version' in old else 'attribute_not_exists(config_id)'
                transaction([put_op('config',item,cond,{':v':old['version']} if 'version' in old else None,{'#v':'version'} if 'version' in old else None),audit_op('POLICY',actor,'policy_update',old,item)])
                return reply(200,item)
        if method == 'GET' and path in ('/attendance', '/export'):
            start, end = q.get('start',''), q.get('end','')
            if not start or not end or not 0 <= (date.fromisoformat(end)-date.fromisoformat(start)).days <= 92:
                raise RuleError('Choose a date range of 93 days or fewer.')
            employees = scan('employees')
            eid = q.get('employee_id','')
            rows=[]
            for e in employees:
                if not eid or eid == e['employee_id']:
                    rows.extend(query_attendance(e['employee_id'],start,end))
            if q.get('status'):
                rows=[r for r in rows if r['status']==q['status']]
            rows.sort(key=lambda r:(r['date'],r.get('name','')),reverse=True)
            if path == '/export':
                stream=io.StringIO()
                fields=['employee_id','name','date','clock_in','clock_out','status','source','timezone']
                w=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore'); w.writeheader()
                for row in rows:
                    # Prevent spreadsheet formula injection from employee names.
                    w.writerow({k: ("'"+str(v) if str(v).startswith(('=','+','-','@','\t','\r')) else v) for k,v in row.items()})
                return reply(200,{'csv':stream.getvalue()})
            return reply(200,{'items':rows,'summary':aggregate(rows)})
        if method == 'POST' and path == '/manual':
            eid = required_text(body,'employee_id')
            e = get('employees',{'employee_id':eid})
            day = required_text(body,'date',10); date.fromisoformat(day)
            reason = required_text(body,'reason',500)
            if not e or day > local_day(utcnow(),os.environ['BUSINESS_TZ']):
                raise RuleError('Unknown employee or future date.')
            if not eligible(e,day,config()['holidays']):
                raise RuleError('Not a scheduled employee day. Review the schedule first.')
            old=get('attendance',{'employee_id':eid,'date':day})
            row={'employee_id':eid,'date':day,'name':e['name'],'status':body.get('status'),
                 'source':'manual','timezone':os.environ['BUSINESS_TZ'],'version':int((old or {}).get('version',0))+1,'reason':reason}
            if row['status'] not in ('present','late','absent'):
                raise RuleError('Invalid status.')
            if row['status'] != 'absent':
                cin=parse_ts(required_text(body,'clock_in'))
                if local_day(cin,os.environ['BUSINESS_TZ']) != day:
                    raise RuleError('Clock-in must be on the selected local date.')
                row['clock_in']=iso(cin)
                if body.get('clock_out'):
                    cout=parse_ts(body['clock_out'])
                    if cout<=cin or local_day(cout,os.environ['BUSINESS_TZ']) != day:
                        raise RuleError('Clock-out must follow clock-in on the same date.')
                    row['clock_out']=iso(cout)
                if cin>utcnow() or (body.get('clock_out') and cout>utcnow()):
                    raise RuleError('Future attendance times are not allowed.')
            expected=int(body.get('version',0))
            if expected != int((old or {}).get('version',0)):
                raise RuleError('Attendance changed. Refresh before correction.')
            op=attendance_put(row,old)
            transaction([op,audit_op(eid,actor,'manual_correction',old,row,reason)])
            return reply(200,row)
        if method == 'POST' and path == '/reports':
            # Authorized asynchronous regeneration; result is read via /reports later.
            day=required_text(body,'date',10); date.fromisoformat(day)
            if day>local_day(utcnow(),os.environ['BUSINESS_TZ']):
                raise RuleError('Report date cannot be in the future.')
            mode=body.get('mode','daily')
            if mode not in ('daily','weekly'):
                raise RuleError('Invalid report mode.')
            client('lambda').invoke(FunctionName=os.environ['REPORT_FUNCTION'],InvocationType='Event',Payload=json.dumps({'mode':mode,'date':day}).encode())
            return reply(202,{'message':'Report requested. Refresh report list shortly.'})
        if method == 'GET' and path == '/reports':
            records=client('s3').list_objects_v2(Bucket=os.environ['REPORT_BUCKET'],Prefix='reports/',MaxKeys=1000).get('Contents',[])
            items=[]
            for obj in sorted(records,key=lambda x:x['LastModified'],reverse=True)[:100]:
                url=client('s3').generate_presigned_url('get_object',Params={'Bucket':os.environ['REPORT_BUCKET'],'Key':obj['Key']},ExpiresIn=120)
                items.append({'key':obj['Key'],'url':url,'updated':str(obj['LastModified'])})
            return reply(200,{'items':items})
        return reply(404, {'error':'Route not found.'})
    except (RuleError,ValueError,TypeError,KeyError) as exc:
        return reply(400, {'error':str(exc)})
    except ClientError as exc:
        if fail_condition(exc):
            return reply(409, {'error':'Record changed. Refresh and retry.'})
        log.error('api_aws_error code=%s',exc.response['Error']['Code'])
        return reply(500, {'error':'AWS operation failed. Administrator: inspect function logs.'})
    except Exception:
        log.exception('api_failure')
        return reply(500, {'error':'Unexpected server error.'})

def attendance_put(row, old):
    if old:
        return put_op('attendance',row,'#v = :v',{':v':old['version']},{'#v':'version'})
    return put_op('attendance',row,'attribute_not_exists(employee_id)')

def finish_op(job, state, result=None, error=None):
    item=dict(job); item.update(state=state,completed_at=iso(utcnow()))
    if result is not None: item['result']=result
    if error is not None: item['error']=error
    return put_op('sessions',item,'lease_owner = :owner AND #s = :processing',
                  {':owner':job['lease_owner'],':processing':'PROCESSING'},{'#s':'state'})

def record(job,employee,stamp):
    tz=os.environ['BUSINESS_TZ']
    for attempt in range(4):
        current=get('employees',{'employee_id':employee['employee_id']})
        if not current or not current['active'] or current.get('face_id')!=employee.get('face_id') or not current.get('consent_at'):
            raise RuleError('Enrollment changed or employee inactive.')
        old=get('attendance',{'employee_id':employee['employee_id'],'date':local_day(stamp,tz)})
        row=transition(old,current,job['action'],stamp,tz,config()['holidays'])
        row['last_session']=job['session_id']
        result={'employee_id':current['employee_id'],'name':current['name'],'time':iso(stamp),'status':row['status'],'action':job['action']}
        try:
            transaction([attendance_put(row,old),emp_guard(current),finish_op(job,'DONE',result),
                audit_op(current['employee_id'],job['owner'],'clock_'+job['action'],old,row,event_id=job['session_id'])])
            return
        except ClientError as exc:
            latest=get('sessions',{'session_id':job['session_id']})
            if latest and latest['state']=='DONE': return
            if not fail_condition(exc) or attempt==3: raise

def remove_vectors(eid):
    args={'CollectionId':os.environ['COLLECTION_ID'],'MaxResults':1000}
    ids=[]
    while True:
        r=client('rekognition').list_faces(**args)
        ids += [f['FaceId'] for f in r['Faces'] if f.get('ExternalImageId')==eid]
        if not r.get('NextToken'): break
        args['NextToken']=r['NextToken']
    for pos in range(0,len(ids),1000):
        client('rekognition').delete_faces(CollectionId=os.environ['COLLECTION_ID'],FaceIds=ids[pos:pos+1000])

def process_object(bucket,key,version):
    if bucket!=os.environ['RAW_BUCKET'] or not key.startswith('raw/'):
        return
    sid=key.split('/')[1]
    job=get('sessions',{'session_id':sid})
    enrollment_lock = False
    try:
        if not job or job['key']!=key or job['state'] in TERMINAL:
            return
        # One S3 version per session. Ignore replay uploads of the same signed policy.
        if job.get('object_version') and job['object_version']!=version:
            return
        owner=str(uuid.uuid4()); now=int(time.time())
        try:
            r=table('sessions').update_item(Key={'session_id':sid},
                UpdateExpression='SET #s = :processing, lease_until = :until, lease_owner = :owner, object_version = :ov',
                ConditionExpression='(#s = :waiting OR (#s = :processing AND lease_until < :now)) AND (attribute_not_exists(object_version) OR object_version = :ov)',
                ExpressionAttributeNames={'#s':'state'},ExpressionAttributeValues={':processing':'PROCESSING',':waiting':'WAITING',':until':now+100,':owner':owner,':now':now,':ov':version},ReturnValues='ALL_NEW')
            job=r['Attributes']
        except ClientError as exc:
            if fail_condition(exc):
                # Do not delete the image owned by an active invocation.
                raise RuntimeError('Session is already being processed; retry later.') from exc
            raise
        try:
            obj=client('s3').get_object(Bucket=bucket,Key=key,VersionId=version)
        except ClientError as exc:
            if exc.response['Error']['Code'] in ('NoSuchKey','NoSuchVersion'):
                transaction([finish_op(job,'EXPIRED',error='Image expired; capture again.')]); return
            raise
        if obj['ContentLength']>MAX_IMAGE:
            raise RuleError('Image is too large.')
        image=obj['Body'].read(MAX_IMAGE+1)
        if not (image.startswith(b'\xff\xd8\xff') or image.startswith(b'\x89PNG\r\n\x1a\n')):
            raise RuleError('Image must contain JPEG or PNG bytes.')
        uploaded=obj['LastModified']
        if uploaded.timestamp()>int(job['expires_at']):
            raise RuleError('Upload session expired. Capture again.')
        # Capture timestamp is the trusted upload time, not browser time or queue time.
        stamp=uploaded
        rek=client('rekognition')
        details=rek.detect_faces(Image={'Bytes':image},Attributes=['DEFAULT'])['FaceDetails']
        validate_face(details)
        if job['mode']=='enroll':
            table('config').update_item(Key={'config_id':'enrollment_lock'},
                UpdateExpression='SET lock_owner = :o, lock_until = :u',
                ConditionExpression='attribute_not_exists(lock_until) OR lock_until < :now',
                ExpressionAttributeValues={':o':owner,':u':int(time.time())+100,':now':int(time.time())})
            enrollment_lock = True
            e=get('employees',{'employee_id':job['employee_id']})
            if not e or not e['active'] or not e.get('consent_at') or e.get('face_removal_pending'):
                raise RuleError('Employee consent is missing or removal is pending.')
            if e.get('face_id') and e.get('enrollment_session')!=sid:
                raise RuleError('Employee already enrolled.')
            # Prevent one enrolled face from being linked to a second identity.
            matches=rek.search_faces_by_image(CollectionId=os.environ['COLLECTION_ID'],Image={'Bytes':image},FaceMatchThreshold=99,MaxFaces=5)['FaceMatches']
            if any(m['Face'].get('ExternalImageId')!=e['employee_id'] for m in matches):
                raise RuleError('Face is already linked to another employee. Review enrollment.')
            indexed=rek.index_faces(CollectionId=os.environ['COLLECTION_ID'],Image={'Bytes':image},ExternalImageId=e['employee_id'],MaxFaces=1,QualityFilter='AUTO')['FaceRecords']
            if not indexed: raise RuleError('Face could not be indexed. Retake a clearer image.')
            before=dict(e)
            e.update(face_id=indexed[0]['Face']['FaceId'],enrollment_session=sid,version=e['version']+1)
            transaction([put_op('employees',e,'#v = :v AND active = :yes',{':v':before['version'],':yes':True},{'#v':'version'}),
                         finish_op(job,'DONE',{'employee_id':e['employee_id'],'name':e['name'],'message':'Enrollment complete.'}),
                         audit_op(e['employee_id'],job['owner'],'enroll',before,e,event_id=sid)])
        else:
            matches=rek.search_faces_by_image(CollectionId=os.environ['COLLECTION_ID'],Image={'Bytes':image},FaceMatchThreshold=98,MaxFaces=5)['FaceMatches']
            best=choose_match(matches,int(config()['similarity']))
            e=get('employees',{'employee_id':best['Face'].get('ExternalImageId','')})
            if not e or e.get('face_id')!=best['Face']['FaceId']:
                raise RuleError('Face has no active enrollment. Ask an administrator.')
            record(job,e,stamp)
    except ClientError as exc:
        if exc.response['Error']['Code'] in ('InvalidImageFormatException', 'ImageTooLargeException') and job and job.get('lease_owner'):
            transaction([finish_op(job,'REJECTED',error='Invalid or oversized image. Retake a JPEG/PNG photo.')])
        else:
            raise
    except RuleError as exc:
        if job and job.get('lease_owner'):
            transaction([finish_op(job,'REJECTED',error=str(exc))])
        else: raise
    finally:
        if enrollment_lock:
            try:
                table('config').delete_item(Key={'config_id':'enrollment_lock'},
                    ConditionExpression='lock_owner = :o',ExpressionAttributeValues={':o':owner})
            except ClientError as exc:
                if not fail_condition(exc): raise
        # Retain only for infrastructure retries; all terminal/replayed/unknown
        # images are physically removed by version, never just a delete marker.
        latest=get('sessions',{'session_id':sid})
        if not latest or latest['state'] in TERMINAL or (latest.get('object_version') and latest['object_version']!=version):
            client('s3').delete_object(Bucket=bucket,Key=key,VersionId=version)

def ingest(event,context):
    failures=[]
    for message in event.get('Records',[]):
        try:
            body=json.loads(message['body'])
            for rec in body.get('Records',[]):
                if rec.get('eventSource')=='aws:s3':
                    obj=rec['s3']['object']
                    process_object(rec['s3']['bucket']['name'],unquote_plus(obj['key']),obj['versionId'])
        except Exception as exc:
            log.error('ingest_retry message_id=%s error_type=%s',message['messageId'],type(exc).__name__)
            failures.append({'itemIdentifier':message['messageId']})
    return {'batchItemFailures':failures}

def cleanup(event,context):
    s3=client('s3'); cutoff=utcnow()-timedelta(hours=1); deleted=0
    for page in s3.get_paginator('list_object_versions').paginate(Bucket=os.environ['RAW_BUCKET'],Prefix='raw/'):
        for obj in page.get('Versions',[])+page.get('DeleteMarkers',[]):
            if obj['LastModified']<=cutoff:
                s3.delete_object(Bucket=os.environ['RAW_BUCKET'],Key=obj['Key'],VersionId=obj['VersionId']); deleted+=1
    # Retry revoked consent cleanup, including orphan vectors from interrupted enrollments.
    people={e['employee_id']:e for e in scan('employees')}
    for eid,e in people.items():
        if e.get('face_removal_pending'):
            remove_vectors(eid)
            table('employees').update_item(Key={'employee_id':eid},UpdateExpression='REMOVE face_removal_pending')
    args={'CollectionId':os.environ['COLLECTION_ID'],'MaxResults':1000}
    while True:
        page=client('rekognition').list_faces(**args)
        for face in page['Faces']:
            e=get('employees',{'employee_id':face.get('ExternalImageId','unknown')})
            # CreationTimestamp is not returned by ListFaces. Use an observation marker
            # and wait an hour; the next sweep rechecks the directory before deletion.
            marker='orphan#'+face['FaceId']
            if not e or e.get('face_id')!=face['FaceId']:
                observed=get('config',{'config_id':marker})
                if observed and int(observed['seen_at'])<int(cutoff.timestamp()):
                    client('rekognition').delete_faces(CollectionId=os.environ['COLLECTION_ID'],FaceIds=[face['FaceId']])
                    table('config').delete_item(Key={'config_id':marker})
                elif not observed:
                    table('config').put_item(Item={'config_id':marker,'seen_at':int(time.time())})
            else:
                table('config').delete_item(Key={'config_id':marker})
        if not page.get('NextToken'): break
        args['NextToken']=page['NextToken']
    # Stale in-progress sessions become visible errors; no fake attendance is written.
    for job in scan('sessions'):
        if job['state'] not in TERMINAL and int(job['expires_at'])<int(cutoff.timestamp()):
            try:
                table('sessions').update_item(Key={'session_id':job['session_id']},UpdateExpression='SET #s = :expired, #e = :reason',
                    ConditionExpression='#s = :old AND (attribute_not_exists(lease_until) OR lease_until < :now)',
                    ExpressionAttributeNames={'#s':'state','#e':'error'},ExpressionAttributeValues={':expired':'EXPIRED',':reason':'Processing expired. Ask an administrator before recapturing.',':old':job['state'],':now':int(time.time())})
            except ClientError as exc:
                if not fail_condition(exc): raise
    log.info('cleanup_complete deleted=%s',deleted)
    return {'deleted_versions':deleted}

def report(event,context):
    tz=os.environ['BUSINESS_TZ']; today=date.fromisoformat(local_day(utcnow(),tz))
    mode=event.get('mode','daily')
    day=date.fromisoformat(event['date']) if event.get('date') else today-timedelta(days=int(event.get('days_ago',0)))
    if mode=='weekly' and not event.get('date'):
        day=today-timedelta(days=1)  # Monday schedule reports previous Monday–Sunday.
    days=[(day-timedelta(days=i)).isoformat() for i in reversed(range(7 if mode=='weekly' else 1))]
    if day>today: raise RuleError('Future report date.')
    people=scan('employees'); holidays=config()['holidays']; rows=[]
    for d in days:
        for e in people:
            if not eligible(e,d,holidays): continue
            key={'employee_id':e['employee_id'],'date':d}
            row=get('attendance',key)
            # Do not create today's absences during a daytime preview/report request.
            close=utcnow().astimezone(__import__('zoneinfo').ZoneInfo(tz)).strftime('%H:%M')>='23:59'
            if not row and (d<today.isoformat() or close):
                row={**key,'name':e['name'],'status':'absent','source':'daily_close','timezone':tz,'version':1}
                try:
                    table('attendance').put_item(Item=row,ConditionExpression='attribute_not_exists(employee_id)')
                except ClientError as exc:
                    if not fail_condition(exc): raise
                    row=get('attendance',key)
            if row: rows.append(row)
    by_employee=[]
    for e in people:
        subset=[r for r in rows if r['employee_id']==e['employee_id']]
        if subset: by_employee.append({'employee_id':e['employee_id'],'name':e['name'],**aggregate(subset)})
    result={'mode':mode,'from':days[0],'to':days[-1],'timezone':tz,'generated_at':iso(utcnow()),
            'provisional':day==today,'summary':aggregate(rows),'employees':by_employee,'attendance':rows}
    key=f'reports/{mode}/{day.isoformat()}.json'
    client('s3').put_object(Bucket=os.environ['REPORT_BUCKET'],Key=key,Body=json.dumps(clean(result)).encode(),ContentType='application/json',ServerSideEncryption='AES256')
    return {'key':key,'summary':result['summary']}
