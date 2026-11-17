"""Assessment history, clinician follow-up, service directory and account lifecycle."""
import hashlib
import json
import secrets
import smtplib
import sqlite3
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from flask import abort, g, jsonify, request, session
from werkzeug.security import generate_password_hash

from instruments import DEFINITIONS, DIFFICULTY, OPTIONS, VERSION, needs_direct_checkin, score


def init_schema(connection):
    connection.executescript('''
    CREATE TABLE IF NOT EXISTS assessment_cycles(user_id TEXT PRIMARY KEY REFERENCES users(id),opened TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS assessment_history(id TEXT PRIMARY KEY,participant_id TEXT NOT NULL,submission_id TEXT UNIQUE NOT NULL,snapshot TEXT NOT NULL,created TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS history_participant ON assessment_history(participant_id,created);
    CREATE TABLE IF NOT EXISTS clinical_conclusions(participant_id TEXT PRIMARY KEY,submission_id TEXT NOT NULL,author_id TEXT NOT NULL,conclusion TEXT NOT NULL,agreement TEXT NOT NULL,rationale TEXT NOT NULL,private_note TEXT NOT NULL,shared_summary TEXT NOT NULL,published INTEGER NOT NULL,version INTEGER NOT NULL,created TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS wemwbs_scores(participant_id TEXT PRIMARY KEY,submission_id TEXT NOT NULL,total INTEGER NOT NULL,source_reference TEXT NOT NULL,author_id TEXT NOT NULL,created TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS appointments(id TEXT PRIMARY KEY,participant_id TEXT NOT NULL,submission_id TEXT NOT NULL,owner_id TEXT NOT NULL,starts_at TEXT NOT NULL,duration INTEGER NOT NULL,mode TEXT NOT NULL,location TEXT NOT NULL,state TEXT NOT NULL,version INTEGER NOT NULL,created TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS appointments_owner ON appointments(owner_id,starts_at);
    CREATE TABLE IF NOT EXISTS notifications(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,event_key TEXT NOT NULL,title TEXT NOT NULL,link TEXT NOT NULL,created TEXT NOT NULL,read_at TEXT,UNIQUE(user_id,event_key));
    CREATE TABLE IF NOT EXISTS support_services(id TEXT PRIMARY KEY,name TEXT NOT NULL,kind TEXT NOT NULL,contact TEXT NOT NULL,hours TEXT NOT NULL,eligibility TEXT NOT NULL,source_url TEXT NOT NULL,checked_on TEXT NOT NULL,checked_by TEXT NOT NULL,active INTEGER NOT NULL,version INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS account_security(user_id TEXT PRIMARY KEY REFERENCES users(id),version INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS account_tokens(token_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL,purpose TEXT NOT NULL,expires TEXT NOT NULL,used_at TEXT,created TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS recovery_attempts(id INTEGER PRIMARY KEY,address TEXT NOT NULL,created REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS mail_outbox(id TEXT PRIMARY KEY,user_id TEXT,recipient TEXT NOT NULL,subject TEXT NOT NULL,body TEXT NOT NULL,state TEXT NOT NULL,created TEXT NOT NULL,sent_at TEXT);
    ''')
    defaults = [
        ('questionnaire', 'behaviour-demo-1. Appendix A source wording and time bands require approval. PHQ-9, GAD-7 and WEMWBS are not administered.', 'behaviour-demo-1 with optional wellbeing-1 PHQ-9/GAD-7 responses. WEMWBS totals require a licensed source administration. Local clinical protocol and age-group suitability need professional approval.'),
        ('support_directory', 'No verified local services configured. No support requests are monitored.', 'Manage source-checked contacts under Support directory. Support-request response coverage is an operator responsibility; the demonstration is not monitored.'),
    ]
    for key, old, new in defaults:
        connection.execute('UPDATE config SET value=?,version=version+1 WHERE key=? AND value=?', (new,key,old))
    connection.commit()


def register(app, db, require, user, payload, text, record, record_json, audit, now):
    def security_version(uid):
        row = db().execute('SELECT version FROM account_security WHERE user_id=?', (uid,)).fetchone()
        return row['version'] if row else 0

    def repeat_open(uid):
        return db().execute('SELECT 1 FROM assessment_cycles WHERE user_id=?', (uid,)).fetchone() is not None

    def conclusion(pid, public=False):
        row = db().execute('SELECT c.*,u.name AS author FROM clinical_conclusions c JOIN users u ON u.id=c.author_id WHERE participant_id=?', (pid,)).fetchone()
        if not row or public and not row['published']:
            return None
        data = dict(row)
        if public:
            return {key: data[key] for key in ('shared_summary', 'author', 'created')}
        return data

    def instruments(row):
        values = score(json.loads(row['answers']))
        wellbeing = db().execute('SELECT * FROM wemwbs_scores WHERE participant_id=? AND submission_id=?', (row['participant_id'], row['submission_id'])).fetchone()
        if wellbeing:
            values[-1].update(score=wellbeing['total'], status='Recorded from licensed administration', version='WEMWBS-14', source_reference=wellbeing['source_reference'])
        return values

    def archive(row):
        prediction = db().execute('SELECT result FROM model_predictions WHERE participant_id=?', (row['participant_id'],)).fetchone()
        snapshot = {'record': dict(row), 'prediction': json.loads(prediction['result']) if prediction else None,
                    'instruments': instruments(row), 'conclusion': conclusion(row['participant_id']),
                    'events': [dict(item) for item in db().execute('SELECT * FROM reviews WHERE participant_id=? ORDER BY id', (row['participant_id'],))]}
        db().execute('INSERT INTO assessment_history VALUES(?,?,?,?,?)', (secrets.token_hex(12), row['participant_id'], row['submission_id'], json.dumps(snapshot), row['submitted_at']))
        for table in ('reviews', 'model_predictions', 'clinical_conclusions', 'wemwbs_scores'):
            db().execute(f'DELETE FROM {table} WHERE participant_id=?', (row['participant_id'],))

    def history(pid, public):
        items = []
        for row in db().execute('SELECT id,snapshot FROM assessment_history WHERE participant_id=? ORDER BY created', (pid,)):
            snapshot = json.loads(row['snapshot'])
            old = snapshot['record']
            item = {key: old[key] for key in ('participant_id', 'submitted_at', 'estimate', 'review_state')}
            item.update(visit_id=row['id'], current=False, answers=json.loads(old['answers']), instruments=snapshot['instruments'], conclusion=snapshot['conclusion'])
            if public:
                for instrument in item['instruments']:
                    instrument.pop('source_reference', None)
                c = item['conclusion']
                item['conclusion'] = {key: c[key] for key in ('shared_summary', 'author', 'created')} if c and c['published'] else None
            else:
                item.update(events=snapshot['events'], prediction=snapshot['prediction'])
            items.append(item)
        latest = db().execute('SELECT * FROM assessments WHERE participant_id=?', (pid,)).fetchone()
        if latest:
            current = record_json(latest, True)
            current.update(visit_id='current', current=True)
            items.append(current)
        return items

    def historical_submission(uid, submission_id):
        row = db().execute('SELECT h.snapshot FROM assessment_history h JOIN participants p ON p.participant_id=h.participant_id WHERE p.user_id=? AND h.submission_id=?', (uid, submission_id)).fetchone()
        if not row:
            return None
        snapshot = json.loads(row['snapshot'])
        old = snapshot['record']
        prediction = snapshot['prediction'] or {'model_version':None,'reason':'No saved model prediction.'}
        result = {key:old[key] for key in ('participant_id','submitted_at','updated','estimate','review_state','version','complete','assigned_to','questionnaire_version')}
        result.update(answers=json.loads(old['answers']),prediction=prediction,model_version=prediction.get('model_version'),model_reason=prediction.get('reason'),instruments=snapshot['instruments'],events=[],contact=None,demo=bool(old['demo']),explanation=prediction.get('explanation'))
        for instrument in result['instruments']:
            instrument.pop('source_reference', None)
        c = snapshot['conclusion']
        result['conclusion'] = {key:c[key] for key in ('shared_summary','author','created')} if c and c['published'] else None
        result['needs_direct_checkin'] = needs_direct_checkin(result['answers'])
        return result

    def notify(uid, key, title, link):
        if uid:
            return db().execute('INSERT OR IGNORE INTO notifications(id,user_id,event_key,title,link,created) VALUES(?,?,?,?,?,?)',
                                (secrets.token_hex(12), uid, key, title, link, now())).rowcount
        return 0

    def send_mail(uid, recipient, subject, body):
        mail_id = secrets.token_hex(12)
        mode = app.config['MAIL_MODE']
        state = 'Preview' if mode == 'preview' else 'Manual delivery' if mode == 'manual' else 'Pending'
        db().execute('INSERT INTO mail_outbox VALUES(?,?,?,?,?,?,?,?)', (mail_id, uid, recipient, subject, body, state, now(), None))
        if mode == 'smtp':
            try:
                msg = EmailMessage()
                msg['Subject'], msg['From'], msg['To'] = subject, app.config['SMTP_FROM'], recipient
                msg.set_content(body)
                with smtplib.SMTP(app.config['SMTP_HOST'], app.config['SMTP_PORT'], timeout=10) as smtp:
                    smtp.starttls()
                    if app.config.get('SMTP_USERNAME'):
                        smtp.login(app.config['SMTP_USERNAME'], app.config['SMTP_PASSWORD'])
                    smtp.send_message(msg)
                state = 'Sent'
                db().execute('UPDATE mail_outbox SET state=?,body=?,sent_at=? WHERE id=?', (state, '', now(), mail_id))
            except (OSError, smtplib.SMTPException):
                state = 'Failed'
                db().execute('UPDATE mail_outbox SET state=? WHERE id=?', (state, mail_id))
        return {'id': mail_id, 'state': state, 'mode': mode}

    def token_mail(uid, email, purpose):
        token = secrets.token_urlsafe(32)
        stamp = now()
        expires = (datetime.now(timezone.utc) + timedelta(hours=48) if purpose == 'invite' else datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(timespec='seconds')
        db().execute('UPDATE account_tokens SET used_at=? WHERE user_id=? AND purpose=? AND used_at IS NULL', (stamp, uid, purpose))
        db().execute('INSERT INTO account_tokens VALUES(?,?,?,?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), uid, purpose, expires, None, stamp))
        url = app.config['APP_BASE_URL'].rstrip('/') + '/#account/set-password/' + token
        subject = 'Set up your Between account' if purpose == 'invite' else 'Reset your Between password'
        return send_mail(uid, email, subject, f'{subject}\n\nOpen this link to choose your password:\n{url}\n\nThis link expires at {expires} and can be used once. If you did not request it, you can ignore this message.\n')

    @app.get('/api/instruments')
    def instrument_definitions():
        return jsonify(version=VERSION, definitions=DEFINITIONS, options=OPTIONS, difficulty=DIFFICULTY,
                       timeframe='Over the last 2 weeks, how often have you been bothered by the following problems?',
                       difficulty_prompt='How difficult have these problems made it for you to do your work, take care of things at home, or get along with other people?')

    @app.post('/api/assessment/repeat')
    @require('participant')
    def start_repeat():
        if payload().get('confirmed') is not True:
            abort(400, description='Confirm that you want to start a new assessment.')
        participant = db().execute('SELECT * FROM participants WHERE user_id=?', (g.user['id'],)).fetchone()
        if participant['withdrawn']:
            abort(409, description='Participation has been withdrawn.')
        if not db().execute('SELECT 1 FROM assessments WHERE user_id=?', (g.user['id'],)).fetchone():
            abort(409, description='Complete your first assessment before starting a follow-up.')
        if not repeat_open(g.user['id']):
            db().execute('INSERT INTO assessment_cycles VALUES(?,?)', (g.user['id'], now()))
            db().execute('DELETE FROM drafts WHERE user_id=?', (g.user['id'],))
            audit('Started repeat assessment', participant['participant_id'])
            db().commit()
        return jsonify(started=True)

    @app.post('/api/assessment/repeat/cancel')
    @require('participant')
    def cancel_repeat():
        db().execute('DELETE FROM assessment_cycles WHERE user_id=?', (g.user['id'],))
        db().execute('DELETE FROM drafts WHERE user_id=?', (g.user['id'],))
        db().commit()
        return jsonify(cancelled=True)

    @app.get('/api/assessment/history')
    @require('participant')
    def own_history():
        pid = db().execute('SELECT participant_id FROM participants WHERE user_id=?', (g.user['id'],)).fetchone()[0]
        return jsonify(visits=history(pid, True))

    @app.get('/api/cases/<pid>/history')
    @require('counsellor')
    def case_history(pid):
        record(pid)
        audit('Viewed assessment history', pid)
        db().commit()
        return jsonify(visits=history(pid, False))

    @app.post('/api/cases/<pid>/conclusion')
    @require('counsellor')
    def save_conclusion(pid):
        db().execute('BEGIN IMMEDIATE')
        case = record(pid)
        data = payload()
        title, agreement = text(data, 'conclusion', 100), text(data, 'agreement', 30)
        rationale, private, shared = text(data, 'rationale', 1000), text(data, 'private_note', 2000), text(data, 'shared_summary', 1000)
        published = data.get('published', False)
        if title not in ('Further conversation recommended', 'Follow-up planned', 'Assessment complete') or agreement not in ('Agree', 'Disagree', 'Uncertain') or type(published) is not bool:
            abort(400, description='Choose a conclusion, a model agreement and a sharing choice.')
        if agreement == 'Disagree' and not rationale or published and not shared:
            abort(400, description='Explain a disagreement and add a participant message before sharing it.')
        if title == 'Assessment complete' and not rationale:
            abort(400, description='Record a reason before completing the clinical assessment.')
        scheduled = db().execute("SELECT min(starts_at) AS starts FROM appointments WHERE participant_id=? AND state='Scheduled'", (pid,)).fetchone()['starts']
        if title == 'Assessment complete' and scheduled:
            abort(409, description='Complete or cancel outstanding appointments before closing this assessment.')
        current = db().execute('SELECT version FROM clinical_conclusions WHERE participant_id=?', (pid,)).fetchone()
        expected = current['version'] if current else 0
        if type(data.get('version')) is not int or data['version'] != expected:
            abort(409, description='The clinician conclusion changed. Reload before saving.')
        if type(data.get('record_version')) is not int or data['record_version'] != case['version']:
            abort(409, description='The assessment changed. Reload before signing off.')
        stamp = now()
        db().execute('INSERT INTO clinical_conclusions VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(participant_id) DO UPDATE SET submission_id=excluded.submission_id,author_id=excluded.author_id,conclusion=excluded.conclusion,agreement=excluded.agreement,rationale=excluded.rationale,private_note=excluded.private_note,shared_summary=excluded.shared_summary,published=excluded.published,version=excluded.version,created=excluded.created',
                     (pid, case['submission_id'], g.user['id'], title, agreement, rationale, private, shared, int(published), expected + 1, stamp))
        review_state = 'Closed' if title == 'Assessment complete' else 'Follow-up arranged' if scheduled else 'In progress'
        db().execute('UPDATE assessments SET review_state=?,updated=?,version=version+1 WHERE participant_id=?', (review_state,stamp,pid))
        db().execute('INSERT INTO reviews(participant_id,actor,status,note,owner,due_date,outcome,created) VALUES(?,?,?,?,?,?,?,?)',
                     (pid,g.user['name'],review_state,'Clinician conclusion recorded.',g.user['name'],scheduled[:10] if scheduled else '',shared if published else title,stamp))
        if published:
            target = db().execute('SELECT user_id FROM assessments WHERE participant_id=?', (pid,)).fetchone()[0]
            notify(target, f'conclusion:{case["submission_id"]}:{expected+1}', 'Your clinician has shared feedback with you.', '#assessment')
        audit('Saved clinician conclusion', pid, agreement)
        db().commit()
        return jsonify(saved=True, conclusion=conclusion(pid), record_version=case['version']+1, review_state=review_state)

    @app.post('/api/cases/<pid>/wemwbs')
    @require('counsellor')
    def record_wemwbs(pid):
        db().execute('BEGIN IMMEDIATE')
        case = record(pid)
        data = payload()
        total, reference = data.get('total'), text(data, 'source_reference', 200)
        if type(total) is not int or not 14 <= total <= 70 or not reference or data.get('licensed_administration') is not True:
            abort(400, description='Record a 14–70 total, the licensed administration reference, and confirmation of a permitted administration.')
        if data.get('record_version') != case['version']:
            abort(409, description='The assessment changed. Reload before recording the score.')
        db().execute('INSERT INTO wemwbs_scores VALUES(?,?,?,?,?,?) ON CONFLICT(participant_id) DO UPDATE SET submission_id=excluded.submission_id,total=excluded.total,source_reference=excluded.source_reference,author_id=excluded.author_id,created=excluded.created',
                     (pid, case['submission_id'], total, reference, g.user['id'], now()))
        db().execute('UPDATE assessments SET updated=?,version=version+1 WHERE participant_id=?', (now(),pid))
        audit('Recorded licensed WEMWBS total', pid)
        db().commit()
        return jsonify(saved=True, instruments=instruments(case), record_version=case['version']+1)

    def appointments_for(uid, participant=False):
        clause, value = ('a.user_id=?', uid) if participant else ('a.assigned_to=?', uid)
        rows = db().execute(f'SELECT p.*,u.name AS clinician FROM appointments p JOIN assessments a ON a.participant_id=p.participant_id JOIN users u ON u.id=p.owner_id WHERE {clause} ORDER BY p.starts_at', (value,)).fetchall()
        return [dict(row) for row in rows]

    @app.get('/api/appointments')
    @require('participant', 'counsellor')
    def get_appointments():
        return jsonify(appointments=appointments_for(g.user['id'], g.user['role'] == 'participant'))

    @app.post('/api/cases/<pid>/appointments')
    @require('counsellor')
    def save_appointment(pid):
        db().execute('BEGIN IMMEDIATE')
        case, data = record(pid), payload()
        starts, mode, location = text(data, 'starts_at', 40), text(data, 'mode', 30), text(data, 'location', 200)
        duration, state = data.get('duration'), text(data, 'state', 30) or 'Scheduled'
        try:
            date = datetime.fromisoformat(starts.replace('Z', '+00:00'))
            if not date.tzinfo:
                raise ValueError()
        except (TypeError, ValueError):
            abort(400, description='Choose an appointment date and time with a timezone.')
        if type(duration) is not int or not 15 <= duration <= 120 or mode not in ('In person', 'Phone', 'Video') or state not in ('Scheduled', 'Completed', 'Cancelled'):
            abort(400, description='Check appointment duration, format and status.')
        appt_id = text(data, 'id', 60)
        existing = db().execute('SELECT * FROM appointments WHERE id=? AND participant_id=?', (appt_id, pid)).fetchone() if appt_id else None
        if appt_id and not existing:
            abort(404, description='Appointment not found.')
        if existing and data.get('version') != existing['version']:
            abort(409, description='This appointment changed. Reload before editing it.')
        if state == 'Scheduled' and date <= datetime.now(timezone.utc):
            abort(400, description='Choose a future time for a scheduled appointment.')
        if state == 'Scheduled' and case['review_state'] == 'Closed':
            abort(409, description='Reopen the case with a reason before scheduling another follow-up.')
        if not existing and state != 'Scheduled':
            abort(400, description='New appointments must be scheduled.')
        appt_id = appt_id or secrets.token_hex(12)
        version = existing['version'] + 1 if existing else 1
        db().execute('INSERT INTO appointments VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET owner_id=excluded.owner_id,starts_at=excluded.starts_at,duration=excluded.duration,mode=excluded.mode,location=excluded.location,state=excluded.state,version=excluded.version',
                     (appt_id, pid, existing['submission_id'] if existing else case['submission_id'], g.user['id'], date.astimezone(timezone.utc).isoformat(timespec='seconds'), duration, mode, location, state, version, now()))
        next_visit = db().execute("SELECT min(starts_at) AS starts FROM appointments WHERE participant_id=? AND state='Scheduled'", (pid,)).fetchone()['starts']
        review_state = 'Follow-up arranged' if next_visit else 'In progress' if case['review_state'] != 'Closed' else 'Closed'
        db().execute('UPDATE assessments SET review_state=?,updated=?,version=version+1 WHERE participant_id=?', (review_state,now(),pid))
        db().execute('INSERT INTO reviews(participant_id,actor,status,note,owner,due_date,outcome,created) VALUES(?,?,?,?,?,?,?,?)',
                     (pid,g.user['name'],review_state,'Appointment '+state.lower()+'.',g.user['name'],next_visit[:10] if next_visit else '', 'Attend the agreed follow-up appointment.' if next_visit else 'Review the next steps with the clinician.',now()))
        notify(case['user_id'], f'appointment:{appt_id}:{version}', 'Your follow-up appointment has been updated. Open your appointments for details.', '#appointments')
        audit('Updated appointment', pid, appt_id)
        db().commit()
        return jsonify(saved=True, id=appt_id, version=version)

    @app.get('/api/follow-ups')
    @require('counsellor')
    def follow_ups():
        today = datetime.now(timezone.utc).date().isoformat()
        tasks = [dict(row) for row in db().execute('SELECT a.participant_id,a.review_state,r.owner,r.due_date,r.outcome FROM assessments a JOIN reviews r ON r.id=(SELECT max(id) FROM reviews WHERE participant_id=a.participant_id) WHERE a.assigned_to=? AND a.review_state=? ORDER BY r.due_date', (g.user['id'], 'Follow-up arranged'))]
        for task in tasks:
            task['overdue'] = bool(task['due_date'] and task['due_date'] < today)
        checkins = [{'participant_id':row['participant_id']} for row in db().execute("SELECT participant_id,answers FROM assessments WHERE assigned_to=? AND review_state!='Closed'", (g.user['id'],)) if needs_direct_checkin(json.loads(row['answers']))]
        return jsonify(tasks=tasks, appointments=appointments_for(g.user['id']), checkins=checkins)

    @app.get('/api/notifications')
    @require()
    def notifications():
        rows = [dict(row) for row in db().execute('SELECT id,title,link,created,read_at FROM notifications WHERE user_id=? ORDER BY created DESC LIMIT 100', (g.user['id'],))]
        return jsonify(notifications=rows)

    @app.post('/api/notifications/<nid>/read')
    @require()
    def read_notification(nid):
        changed = db().execute('UPDATE notifications SET read_at=? WHERE id=? AND user_id=?', (now(), nid, g.user['id']))
        if not changed.rowcount:
            abort(404, description='Notification not found.')
        db().commit()
        return jsonify(saved=True)

    @app.get('/api/support/services')
    def services():
        return jsonify(services=[dict(row) for row in db().execute('SELECT id,name,kind,contact,hours,eligibility,source_url,checked_on FROM support_services WHERE active=1 ORDER BY name')])

    @app.get('/api/admin/services')
    @require('administrator')
    def admin_services():
        return jsonify(services=[dict(row) for row in db().execute('SELECT * FROM support_services ORDER BY name')])

    @app.post('/api/admin/services')
    @require('administrator')
    def save_service():
        db().execute('BEGIN IMMEDIATE')
        data = payload()
        sid = text(data, 'id', 60) or secrets.token_hex(12)
        values = {key: text(data, key, 300) for key in ('name', 'kind', 'contact', 'hours', 'eligibility', 'source_url', 'checked_on')}
        if any(not value for value in values.values()) or values['kind'] not in ('Phone', 'Email', 'Website', 'In person') or not values['source_url'].startswith('https://'):
            abort(400, description='Add service details, opening hours, eligibility and an official HTTPS source.')
        try:
            checked = datetime.strptime(values['checked_on'], '%Y-%m-%d').date()
            if checked > datetime.now(timezone.utc).date():
                raise ValueError()
        except ValueError:
            abort(400, description='Choose the date you checked the service; it cannot be in the future.')
        if data.get('confirmed_checked') is not True or type(data.get('active', True)) is not bool:
            abort(400, description='Confirm that you checked the contact information and availability.')
        current = db().execute('SELECT version FROM support_services WHERE id=?', (sid,)).fetchone()
        expected = current['version'] if current else 0
        if data.get('version', 0) != expected:
            abort(409, description='This service changed. Reload before saving.')
        db().execute('INSERT INTO support_services VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,kind=excluded.kind,contact=excluded.contact,hours=excluded.hours,eligibility=excluded.eligibility,source_url=excluded.source_url,checked_on=excluded.checked_on,checked_by=excluded.checked_by,active=excluded.active,version=excluded.version',
                     (sid, *values.values(), g.user['id'], int(data.get('active', True)), expected + 1))
        audit('Updated staff-checked support service', sid)
        db().commit()
        return jsonify(saved=True, id=sid, version=expected + 1)

    @app.post('/api/admin/invitations')
    @require('administrator')
    def invitation():
        data = payload()
        email, name, role = text(data, 'email', 254).lower(), text(data, 'name', 100), text(data, 'role', 30)
        if '@' not in email or not name or role not in ('participant', 'counsellor', 'researcher', 'administrator') or data.get('confirmed') is not True:
            abort(400, description='Provide a name, email, role and confirmation.')
        uid = 'account-' + secrets.token_hex(8)
        try:
            db().execute('INSERT INTO users VALUES(?,?,?,?,?,?,?)', (uid, email, generate_password_hash(secrets.token_urlsafe(40)), name, role, 1, now()))
            if role == 'participant':
                db().execute('INSERT INTO participants VALUES(?,?,?,?)', (uid, 'P-' + secrets.token_hex(5).upper(), 0, now()))
        except sqlite3.IntegrityError:
            abort(409, description='An account already uses that email.')
        delivery = token_mail(uid, email, 'invite')
        audit('Created account invitation', uid, role)
        db().commit()
        return jsonify(saved=True, delivery=delivery), 201

    @app.post('/api/account/recovery')
    def recovery():
        import time
        email = text(payload(), 'email', 254).lower()
        address = request.remote_addr or 'local'
        recent = db().execute('SELECT count(*) FROM recovery_attempts WHERE address=? AND created>?', (address, time.time() - 900)).fetchone()[0]
        if recent >= 5:
            abort(429, description='Too many recovery requests. Please try again later.')
        db().execute('INSERT INTO recovery_attempts(address,created) VALUES(?,?)', (address, time.time()))
        account = db().execute('SELECT id,email FROM users WHERE email=? AND active=1', (email,)).fetchone()
        if account:
            token_mail(account['id'], account['email'], 'reset')
        db().commit()
        return jsonify(message='If an active account matches that email, password reset instructions will be prepared. Contact the workspace operator if email delivery is not configured.')

    @app.post('/api/account/password')
    def set_password():
        data = payload()
        token, password = text(data, 'token', 100), text(data, 'password', 128)
        if len(password) < 12:
            abort(400, description='Use a password of at least 12 characters.')
        digest = hashlib.sha256(token.encode()).hexdigest()
        row = db().execute('SELECT t.* FROM account_tokens t JOIN users u ON u.id=t.user_id WHERE token_hash=? AND used_at IS NULL AND expires>? AND u.active=1', (digest, now())).fetchone()
        if not row:
            abort(400, description='This link is invalid, expired or already used. Request a new link.')
        stamp = now()
        changed = db().execute('UPDATE account_tokens SET used_at=? WHERE token_hash=? AND used_at IS NULL AND expires>?', (stamp, digest, stamp))
        if not changed.rowcount:
            abort(409, description='This link has already been used.')
        db().execute('UPDATE users SET password=? WHERE id=?', (generate_password_hash(password), row['user_id']))
        db().execute('INSERT INTO account_security VALUES(?,1) ON CONFLICT(user_id) DO UPDATE SET version=version+1', (row['user_id'],))
        audit('Account password changed', row['user_id'])
        db().commit()
        session.clear()
        return jsonify(saved=True, message='Your password has been set. Sign in with your new password.')

    @app.get('/api/admin/mail')
    @require('administrator')
    def mail_preview():
        fields = 'id,recipient,subject,body,state,created,sent_at' if app.config['MAIL_MODE'] in ('preview', 'manual') else 'id,recipient,subject,state,created,sent_at'
        return jsonify(mode=app.config['MAIL_MODE'], messages=[dict(row) for row in db().execute(f'SELECT {fields} FROM mail_outbox ORDER BY created DESC LIMIT 50')])

    @app.get('/api/research/validation')
    @require('researcher')
    def external_validation():
        from pathlib import Path
        path = app.config.get('EXTERNAL_EVALUATION')
        report = None
        message = 'No external participant study has been connected. An evaluation workflow is ready; clinical validation is still pending.'
        if path:
            try:
                candidate = json.loads(Path(path).read_text(encoding='utf-8'))
                if candidate.get('kind') != 'external-evaluation-1' or candidate.get('clinical_release') is not False or candidate.get('model_sha256') != app.extensions['between_model'].artifact_hash:
                    raise ValueError()
                report = {key:candidate[key] for key in ('dataset_description','model_version','evaluated_at','metrics','limitations')}
                message = candidate['limitations']
            except (OSError, ValueError, KeyError, AttributeError):
                message = 'The configured external evaluation could not be verified for this model. Ask the operator to check its provenance.'
        return jsonify(report=report,message=message)

    def send_reminders():
        count = 0
        beginning = now()
        end = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(timespec='seconds')
        rows = db().execute('SELECT p.*,a.user_id,u.email FROM appointments p JOIN assessments a ON a.participant_id=p.participant_id JOIN users u ON u.id=a.user_id WHERE p.state=? AND p.starts_at>? AND p.starts_at<=? AND u.active=1', ('Scheduled', beginning, end)).fetchall()
        for row in rows:
            key = f'reminder:{row["id"]}:{row["version"]}'
            if db().execute('SELECT 1 FROM notifications WHERE user_id=? AND event_key=?', (row['user_id'], key)).fetchone():
                continue
            if not notify(row['user_id'], key, 'You have an upcoming follow-up appointment. Sign in for details.', '#appointments'):
                continue
            send_mail(row['user_id'], row['email'], 'Your Between appointment reminder', 'You have an upcoming appointment. Sign in to your workspace to see its time and details: ' + app.config['APP_BASE_URL'].rstrip('/') + '/#appointments')
            count += 1
        db().commit()
        return count

    return {'repeat_open': repeat_open, 'archive': archive, 'instruments': instruments,
            'conclusion': conclusion, 'security_version': security_version, 'send_reminders': send_reminders,
            'historical_submission':historical_submission, 'notify':notify}
