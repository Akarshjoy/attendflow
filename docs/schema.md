# DynamoDB schema and API

All tables use on-demand capacity, encryption at rest and point-in-time recovery.
CloudFormation retains them on deletion/replacement; retained data requires separate lifecycle review.

| Table | Partition key | Sort key | Main fields |
|---|---|---|---|
| Employees | employee_id (UUID) | — | name, department, active, start_date, end_date, workdays, late_after, face_id, consent_at, consent_recorded_by, version |
| Attendance | employee_id | date (YYYY-MM-DD, local) | clock_in, clock_out, status, source, timezone, version, name, last_session, reason |
| Sessions | session_id (UUID) | — | owner, mode, action, key, employee_id (enroll only), state, object_version, lease_owner, lease_until, expires_at, ttl, result/error |
| Config | config_id | — | policy: holidays, similarity, version; enrollment_lock: owner/lease; orphan markers: first observed time |
| Audit | event_id (UUID/session ID) | — | employee_id, at, actor, action, before, after, reason |

`workdays` uses Monday=0 through Sunday=6. `late_after` is a business-timezone HH:MM value.
Clock times are UTC ISO timestamps, not unqualified local strings. Status is one of present/late/absent.
Absent rows omit clock_in and clock_out. Face vectors reside in Rekognition, not DynamoDB photos.

```mermaid
erDiagram
  EMPLOYEES ||--o{ ATTENDANCE : has
  EMPLOYEES ||--o{ AUDIT : audited
  EMPLOYEES ||--o{ SESSIONS : enrolls_or_matches
  EMPLOYEES {
    string employee_id PK
    string face_id
    string start_date
    string consent_at
    number version
  }
  ATTENDANCE {
    string employee_id PK
    string date SK
    string clock_in
    string clock_out
    string status
    number version
  }
  SESSIONS {
    string session_id PK
    string owner
    string state
    string object_version
  }
  AUDIT {
    string event_id PK
    string employee_id
    string action
    string actor
  }
```

## API routes

All application routes require a valid Cognito ID token from this app client in Authorization.
OPTIONS preflight is unauthenticated and does not access application data.

| Route | Role | Behavior |
|---|---|---|
| GET /me | Admin, Kiosk | Roles and business timezone |
| POST /sessions | Admin, Kiosk | New bounded upload policy; enrollment is Admin-only |
| GET /sessions/{id} | Owner or Admin | Session result, never raw image |
| GET/POST /employees | Admin | Directory / create employee |
| POST /employees/{id}/consent | Admin | Record renewed consent |
| POST /employees/{id}/remove-face | Admin | Revoke face enrollment and delete vectors |
| POST /employees/{id}/deactivate | Admin | End date, disable captures, remove vectors |
| GET/POST /config | Admin | Read/edit holidays and similarity with version guard |
| GET /attendance | Admin | Filter start/end/employee_id/status; max 93 days |
| GET /export | Admin | Same filters; CSV escaped for spreadsheet formula injection |
| POST /manual | Admin | Audited correction; expected version and reason required |
| GET /reports | Admin | Recent report links valid for 120 seconds |
| POST /reports | Admin | Asynchronous daily/weekly regeneration |

One collection stores external-image IDs matching employee UUIDs. Audit history retains employee
names and attendance when enrollment is withdrawn; face removal is not an attendance-record erasure.
For the demo scale, directory scans and per-employee queries are deliberate. Report listing reads
up to 1,000 current S3 keys and displays the newest 100 from that result. Long-lived large deployments
need pagination and a report metadata index; it is not an unlimited archive browser.
