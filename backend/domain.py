"""Pure attendance policy. All timestamps are server generated UTC ISO strings."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

class RuleError(ValueError):
    pass

def utcnow():
    return datetime.now(timezone.utc)

def iso(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec='milliseconds')

def parse_ts(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise RuleError('Timestamp must include timezone.')
    return dt

def local_day(dt, tz):
    return dt.astimezone(ZoneInfo(tz)).date().isoformat()

def eligible(employee, day, holidays):
    d = date.fromisoformat(day)
    return (employee['start_date'] <= day and
            (not employee.get('end_date') or day <= employee['end_date']) and
            d.weekday() in employee['workdays'] and day not in holidays)

def transition(old, employee, action, stamp, tz, holidays, source='face'):
    day = local_day(stamp, tz)
    if not eligible(employee, day, holidays):
        raise RuleError('Not a scheduled working day for this employee.')
    row = dict(old or {'employee_id': employee['employee_id'], 'date': day, 'version': 0})
    if action == 'in':
        if row.get('clock_in'):
            raise RuleError('Already clocked in. Use Clock Out when leaving.')
        cutoff = datetime.combine(date.fromisoformat(day), time.fromisoformat(employee['late_after']), ZoneInfo(tz))
        row.update(clock_in=iso(stamp), status='late' if stamp > cutoff else 'present')
        row.pop('clock_out', None)
    elif action == 'out':
        if not row.get('clock_in'):
            raise RuleError('Clock in first. Overnight shifts are not supported.')
        if row.get('clock_out'):
            raise RuleError('Already clocked out for this day.')
        if stamp <= parse_ts(row['clock_in']):
            raise RuleError('Clock-out must follow clock-in.')
        row['clock_out'] = iso(stamp)
    else:
        raise RuleError('Unknown attendance action.')
    row.update(name=employee['name'], source=source, timezone=tz, version=int(row['version']) + 1)
    return row

def choose_match(matches, threshold=99, margin=1):
    if not matches or float(matches[0]['Similarity']) < threshold:
        raise RuleError('No confident match. Retry in better lighting or ask an administrator.')
    best = matches[0]
    if any(m['Face'].get('ExternalImageId') != best['Face'].get('ExternalImageId') and
           float(best['Similarity']) - float(m['Similarity']) <= margin for m in matches[1:]):
        raise RuleError('Ambiguous face match. Ask an administrator.')
    return best

def validate_face(details):
    if len(details) != 1:
        raise RuleError('Exactly one face must be visible.')
    f = details[0]
    if float(f.get('Confidence', 0)) < 99:
        raise RuleError('Face detection confidence is too low.')
    quality = f.get('Quality', {})
    if float(quality.get('Brightness', 0)) < 35 or float(quality.get('Sharpness', 0)) < 35:
        raise RuleError('Image is dark or blurry. Improve lighting and hold still.')
    pose = f.get('Pose', {})
    if abs(float(pose.get('Yaw', 0))) > 25 or abs(float(pose.get('Pitch', 0))) > 25:
        raise RuleError('Look directly at the camera.')

def aggregate(rows):
    result = {'scheduled_days': len(rows), 'present': 0, 'late': 0, 'absent': 0, 'missing_clock_out': 0}
    for r in rows:
        result[r['status']] += 1
        if r.get('clock_in') and not r.get('clock_out'):
            result['missing_clock_out'] += 1
    n = result['scheduled_days']
    result['present_pct'] = round(100 * (result['present'] + result['late']) / n, 2) if n else 0
    result['late_pct'] = round(100 * result['late'] / n, 2) if n else 0
    result['absent_pct'] = round(100 * result['absent'] / n, 2) if n else 0
    return result
