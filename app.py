"""Between: a local research-screening demonstration. Never accepts live enrolment."""
import csv
import io
import json
import os
import secrets
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

from flask import Flask, abort, g, jsonify, make_response, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

from ml.service import DEFAULT_ARTIFACT_DIR, ModelService
import instruments
import workspace

ROOT = Path(__file__).resolve().parent
STATES = ('Needs review', 'In progress', 'Follow-up arranged', 'Closed')
FREQUENCIES = ('never', 'rarely', 'sometimes', 'often', 'always')
PLATFORMS = ('instagram', 'tiktok', 'whatsapp', 'youtube', 'snapchat', 'facebook', 'x', 'other')
QUESTIONNAIRE_VERSION = 'behaviour-demo-1'


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def create_app(test_config=None):
    app = Flask(__name__, static_folder='static')
    demo_mode = os.environ.get('BETWEEN_DEMO', '1') != '0'
    app.config.update(DATABASE=os.environ.get('BETWEEN_DATABASE', str(ROOT / 'instance' / 'between.sqlite3')),
                      SECRET_KEY=os.environ.get('BETWEEN_SECRET_KEY'),
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                      SESSION_COOKIE_SECURE=os.environ.get('BETWEEN_HTTPS') == '1',
                      PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
                      ML_ARTIFACT_DIR=str(DEFAULT_ARTIFACT_DIR),
                      DEMO_MODE=demo_mode,
                      PRODUCTION=os.environ.get('BETWEEN_ENV') == 'production',
                      APP_BASE_URL=os.environ.get('BETWEEN_BASE_URL', 'http://127.0.0.1:5000'),
                      MAIL_MODE=os.environ.get('BETWEEN_MAIL_MODE', 'preview' if demo_mode else 'manual'),
                      SMTP_HOST=os.environ.get('BETWEEN_SMTP_HOST', ''),
                      SMTP_PORT=int(os.environ.get('BETWEEN_SMTP_PORT', '587')),
                      SMTP_FROM=os.environ.get('BETWEEN_SMTP_FROM', ''),
                      SMTP_USERNAME=os.environ.get('BETWEEN_SMTP_USERNAME', ''),
                      SMTP_PASSWORD=os.environ.get('BETWEEN_SMTP_PASSWORD', ''),
                      EXTERNAL_EVALUATION=os.environ.get('BETWEEN_EXTERNAL_EVALUATION'),
                      MAX_CONTENT_LENGTH=128 * 1024)
    if test_config:
        app.config.update(test_config)
    if app.config['TESTING'] and (not test_config or 'MAIL_MODE' not in test_config):
        app.config['MAIL_MODE'] = 'preview'
    if app.config['MAIL_MODE'] not in ('preview', 'manual', 'smtp'):
        raise ValueError('BETWEEN_MAIL_MODE must be preview, manual or smtp.')
    if app.config['MAIL_MODE'] == 'smtp' and not (app.config['SMTP_HOST'] and app.config['SMTP_FROM']):
        raise ValueError('SMTP delivery needs BETWEEN_SMTP_HOST and BETWEEN_SMTP_FROM.')
    if app.config['PRODUCTION'] and (app.config['DEMO_MODE'] or not app.config['SECRET_KEY'] or len(app.config['SECRET_KEY']) < 32 or not app.config['SESSION_COOKIE_SECURE'] or not app.config['APP_BASE_URL'].startswith('https://') or app.config['MAIL_MODE'] == 'preview'):
        raise ValueError('Production requires demo access disabled, a stable 32+ character secret, secure cookies, an HTTPS base URL, and manual or SMTP account delivery. See docs/deployment.md.')
    model = ModelService(app.config['ML_ARTIFACT_DIR'])
    app.extensions['between_model'] = model
    Path(app.config['DATABASE']).parent.mkdir(parents=True, exist_ok=True)
    if not app.config['SECRET_KEY']:
        keyfile = ROOT / 'instance' / 'session.key'
        keyfile.parent.mkdir(exist_ok=True)
        if not keyfile.exists():
            keyfile.write_text(secrets.token_hex(32), encoding='utf-8')
        app.config['SECRET_KEY'] = keyfile.read_text(encoding='utf-8').strip()

    def db():
        if 'db' not in g:
            g.db = sqlite3.connect(app.config['DATABASE'], timeout=15)
            g.db.row_factory = sqlite3.Row
            g.db.execute('PRAGMA foreign_keys=ON')
        return g.db

    @app.teardown_appcontext
    def close_db(_error):
        if 'db' in g:
            g.db.close()

    def audit(action, target='', detail=''):
        db().execute('INSERT INTO audit(actor,action,target,detail,created) VALUES(?,?,?,?,?)',
                     (session.get('user_id', 'system'), action, target, detail, now()))

    def user():
        return db().execute('SELECT * FROM users WHERE id=? AND active=1',
                            (session.get('user_id', ''),)).fetchone()

    def require(*roles):
        def decorator(fn):
            @wraps(fn)
            def wrapped(*args, **kwargs):
                current = user()
                if not current:
                    abort(401, description='Your session has ended. Sign in to recover server-saved work.')
                if roles and current['role'] not in roles:
                    abort(403, description='Your account does not have permission to open this area.')
                g.user = current
                return fn(*args, **kwargs)
            return wrapped
        return decorator

    @app.before_request
    def protect():
        if not request.path.startswith('/api/'):
            return
        session.setdefault('csrf', secrets.token_urlsafe(32))
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            if not secrets.compare_digest(request.headers.get('X-CSRF-Token', ''), session['csrf']):
                abort(403, description='This page has expired. Reload it before trying again.')
        if session.get('user_id') and time.time() > session.get('expires', 0):
            session.clear()
            abort(401, description='Your session expired. Sign in again; your server-saved draft is recoverable.')
        if session.get('user_id') and session.get('auth_version', 0) != ws['security_version'](session['user_id']):
            session.clear()
            abort(401, description='Your password changed. Sign in again with your new password.')

    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        if app.config['SESSION_COOKIE_SECURE']:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response

    @app.errorhandler(400)
    @app.errorhandler(401)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(409)
    @app.errorhandler(413)
    @app.errorhandler(429)
    def api_error(error):
        return jsonify(error=error.description), error.code

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify(error='The server could not complete the request. Your last acknowledged save is unchanged.'), 500

    def payload():
        value = request.get_json(silent=True)
        if not isinstance(value, dict):
            abort(400, description='Send a valid JSON object.')
        return value

    def text(data, key, maximum=2000):
        value = data.get(key, '')
        if not isinstance(value, str) or len(value) > maximum:
            abort(400, description=f'Check {key.replace("_", " ")}. Maximum length is {maximum} characters.')
        return value.strip()

    def record(pid):
        row = db().execute('SELECT * FROM assessments WHERE participant_id=?', (pid,)).fetchone()
        if not row:
            abort(404, description='No accessible assessment was found.')
        if g.user['role'] == 'participant' and row['user_id'] != g.user['id']:
            abort(403, description='You can only access your own assessment.')
        if g.user['role'] == 'counsellor' and row['assigned_to'] != g.user['id']:
            abort(403, description='This participant is not assigned to you.')
        return row

    def record_json(row, full=False):
        result = {key: row[key] for key in ('participant_id', 'submitted_at', 'updated', 'estimate', 'review_state', 'version', 'complete', 'assigned_to')}
        prediction_row = db().execute('SELECT result FROM model_predictions WHERE participant_id=?', (row['participant_id'],)).fetchone()
        prediction = json.loads(prediction_row['result']) if prediction_row else {
            'estimate': row['estimate'], 'model_version': 'v0.1-demo' if row['estimate'] else None,
            'source': 'legacy_example' if row['estimate'] else 'unavailable',
            'synthetic': True, 'probabilities': None,
            'reason': 'Preloaded fictional example; not generated by the trained model.' if row['estimate'] else 'This record has no saved model prediction.'}
        result.update(demo=True, model_version=prediction['model_version'], prediction=prediction,
                      questionnaire_version=row['questionnaire_version'],
                      model_reason=prediction.get('reason'),
                      instruments=ws['instruments'](row),
                      needs_direct_checkin=instruments.needs_direct_checkin(json.loads(row['answers'])),
                      conclusion=ws['conclusion'](row['participant_id'], g.user['role'] == 'participant'))
        if g.user['role'] == 'participant':
            for instrument in result['instruments']:
                instrument.pop('source_reference', None)
        if full:
            result['answers'] = json.loads(row['answers'])
            result['explanation'] = prediction.get('explanation') or model.explain(result['answers'], prediction)
            result['events'] = [dict(r) for r in db().execute(
                'SELECT actor,status,note,owner,due_date,outcome,created FROM reviews WHERE participant_id=? ORDER BY created,id', (row['participant_id'],))] if g.user['role'] == 'counsellor' else []
            result['contact'] = None
            if g.user['role'] == 'counsellor' and row['contact_opt_in']:
                identity = db().execute('SELECT method,details,times FROM contacts WHERE participant_id=? ORDER BY created DESC LIMIT 1', (row['participant_id'],)).fetchone()
                result['contact'] = dict(identity) if identity else None
        return result

    @app.get('/')
    def index():
        return send_from_directory(ROOT / 'static', 'index.html')

    @app.get('/api/session')
    def current_session():
        current = user()
        return jsonify(csrf=session['csrf'], demo=app.config['DEMO_MODE'],
                       expires=session.get('expires'),
                       user={k: current[k] for k in ('id', 'name', 'role')} if current else None)

    @app.post('/api/login')
    def login():
        data = payload()
        email, password = text(data, 'email', 254).lower(), text(data, 'password', 128)
        key = request.remote_addr or 'local'
        recent = db().execute('SELECT count(*) FROM login_attempts WHERE address=? AND attempted>?', (key, time.time() - 300)).fetchone()[0]
        if recent >= 20:
            abort(429, description='Too many sign-in attempts. Try again in five minutes.')
        current = db().execute('SELECT * FROM users WHERE email=? AND active=1', (email,)).fetchone()
        db().execute('INSERT INTO login_attempts(address,attempted) VALUES(?,?)', (key, time.time()))
        db().commit()
        if not current or not check_password_hash(current['password'], password):
            abort(401, description='The email or password is incorrect.')
        session.clear()
        session.update(user_id=current['id'], csrf=secrets.token_urlsafe(32), expires=time.time() + 1800, auth_version=ws['security_version'](current['id']))
        session.permanent = True
        audit('Signed in', current['id'])
        db().commit()
        return jsonify(user={k: current[k] for k in ('id', 'name', 'role')}, csrf=session['csrf'], expires=session['expires'])

    @app.post('/api/study-access')
    def study_access():
        if not app.config['DEMO_MODE']:
            abort(403, description='Public demo access is disabled. Use an invited account.')
        data = payload()
        if text(data, 'code', 40).upper() != 'BETWEEN-DEMO':
            abort(400, description='This demo study code was not recognised. Use BETWEEN-DEMO.')
        uid = 'demo-' + uuid.uuid4().hex[:12]
        pid = 'D-' + secrets.token_hex(4).upper()
        db().execute('INSERT INTO users VALUES(?,?,?,?,?,?,?)',
                     (uid, uid + '@demo.local', generate_password_hash(secrets.token_urlsafe(24)), 'Demo participant', 'participant', 1, now()))
        db().execute('INSERT INTO participants VALUES(?,?,?,?)', (uid, pid, 0, now()))
        session.clear()
        session.update(user_id=uid, csrf=secrets.token_urlsafe(32), expires=time.time() + 1800)
        session.permanent = True
        audit('Demo study access', pid)
        db().commit()
        return jsonify(user={'id': uid, 'name': 'Demo participant', 'role': 'participant'}, csrf=session['csrf'], expires=session['expires'])

    @app.post('/api/session/extend')
    @require()
    def extend_session():
        session['expires'] = time.time() + 1800
        return jsonify(expires=session['expires'])

    @app.post('/api/logout')
    def logout():
        if session.get('user_id'):
            audit('Signed out')
            db().commit()
        session.clear()
        return jsonify(ok=True)

    @app.get('/api/assessment')
    @require('participant')
    def get_assessment():
        participant = db().execute('SELECT * FROM participants WHERE user_id=?', (g.user['id'],)).fetchone()
        draft = db().execute('SELECT * FROM drafts WHERE user_id=?', (g.user['id'],)).fetchone()
        submitted = db().execute('SELECT * FROM assessments WHERE user_id=?', (g.user['id'],)).fetchone()
        return jsonify(participant_id=participant['participant_id'], withdrawn=bool(participant['withdrawn']),
                       repeat_open=ws['repeat_open'](g.user['id']),
                       draft={'answers': json.loads(draft['answers']), 'step': draft['step'], 'updated': draft['updated']} if draft else None,
                       submission=record_json(submitted, True) if submitted else None)

    def validate_answers(answers, complete=False):
        if not isinstance(answers, dict):
            abort(400, description='Answers must be an object.')
        allowed = {'age', 'consent', 'privacy', 'guardian', 'assent', 'contact_opt_in', 'gender', 'gender_other', 'education', 'education_other', 'platforms', 'platforms_other', 'daily_time', 'passive', 'active', 'night', 'cyberbullying', 'regular_count', 'wellbeing_opt_in', 'phq9', 'gad7', 'phq9_difficulty', 'gad7_difficulty'}
        if set(answers) - allowed:
            abort(400, description='Unrecognised questionnaire fields.')
        errors = {}
        if 'age' in answers or complete:
            age = answers.get('age')
            if type(age) is not int or not 13 <= age <= 24:
                errors['age'] = 'This study is for people aged 13–24.'
        for key in ('consent', 'privacy', 'guardian', 'assent', 'contact_opt_in'):
            if key in answers and type(answers[key]) is not bool:
                errors[key] = 'Choose yes or no.'
        for key in ('gender_other', 'education_other', 'platforms_other'):
            if key in answers and (not isinstance(answers[key], str) or len(answers[key]) > 150):
                errors[key] = 'Use at most 150 characters.'
        choices = {'gender': ('woman', 'man', 'nonbinary', 'other', 'prefer_not'),
                   'education': ('secondary', 'college', 'university', 'other'),
                   'daily_time': ('under1', '1to3', '3to5', '5plus'),
                   'passive': FREQUENCIES, 'active': FREQUENCIES, 'night': FREQUENCIES,
                   'cyberbullying': ('never', 'once', 'sometimes', 'often'),
                   'regular_count': ('1', '2', '3', '4plus')}
        for key, values in choices.items():
            if (complete or key in answers) and answers.get(key) not in values:
                errors[key] = 'Choose one of the listed answers.'
        if 'platforms' in answers or complete:
            platforms = answers.get('platforms')
            if not isinstance(platforms, list) or (complete and not platforms) or any(not isinstance(x, str) or x not in PLATFORMS for x in platforms) or len(platforms) != len(set(platforms)):
                errors['platforms'] = 'Choose at least one platform; duplicate selections are not allowed.'
        for key in ('gender', 'education'):
            if complete and answers.get(key) == 'other' and not answers.get(key + '_other', '').strip():
                errors[key + '_other'] = 'Tell us your other answer.'
        if complete and 'other' in answers.get('platforms', []) and not answers.get('platforms_other', '').strip():
            errors['platforms_other'] = 'Name the other platform.'
        if complete:
            for key in ('consent', 'privacy'):
                if answers.get(key) is not True:
                    errors[key] = 'Confirm this choice before continuing.'
            if type(answers.get('age')) is int and answers['age'] < 18:
                for key in ('guardian', 'assent'):
                    if answers.get(key) is not True:
                        errors[key] = 'The minor demo pathway requires both guardian authorisation and assent.'
        errors.update(instruments.validate(answers, complete))
        return errors

    @app.put('/api/assessment/draft')
    @require('participant')
    def save_draft():
        data = payload()
        answers = data.get('answers', {})
        errors = validate_answers(answers)
        if errors:
            return jsonify(error='Check your answers.', fields=errors), 400
        if answers.get('consent') is not True or answers.get('privacy') is not True:
            abort(400, description='Consent and privacy acknowledgement are required before saving research answers.')
        age = answers.get('age')
        if type(age) is not int or not 13 <= age <= 24:
            abort(400, description='Complete age eligibility before saving.')
        if age < 18 and (answers.get('guardian') is not True or answers.get('assent') is not True):
            abort(400, description='Complete the guardian and assent demo pathway before saving.')
        participant = db().execute('SELECT * FROM participants WHERE user_id=?', (g.user['id'],)).fetchone()
        if participant['withdrawn'] or db().execute('SELECT 1 FROM assessments WHERE user_id=?', (g.user['id'],)).fetchone() and not ws['repeat_open'](g.user['id']):
            abort(409, description='This assessment is no longer open for editing.')
        step = data.get('step', 1)
        if type(step) is not int or not 1 <= step <= 4:
            abort(400, description='Invalid assessment section.')
        stamp = now()
        db().execute('INSERT INTO drafts VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET answers=excluded.answers,step=excluded.step,updated=excluded.updated', (g.user['id'], json.dumps(answers), step, stamp))
        db().commit()
        return jsonify(saved=True, updated=stamp)

    @app.post('/api/assessment/submit')
    @require('participant')
    def submit():
        data = payload()
        submission_id = text(data, 'submission_id', 80)
        if not submission_id:
            abort(400, description='A submission reference is required.')
        historical = ws['historical_submission'](g.user['id'], submission_id)
        if historical:
            return jsonify(submission=historical, duplicate=True)
        existing = db().execute('SELECT * FROM assessments WHERE user_id=?', (g.user['id'],)).fetchone()
        if existing:
            if existing['submission_id'] == submission_id:
                return jsonify(submission=record_json(existing, True), duplicate=True)
            if not ws['repeat_open'](g.user['id']):
                abort(409, description='Start a follow-up assessment from your summary before submitting again.')
        answers = data.get('answers', {})
        errors = validate_answers(answers, True)
        if errors:
            return jsonify(error='Review the highlighted answers before submitting.', fields=errors), 400
        participant = db().execute('SELECT * FROM participants WHERE user_id=?', (g.user['id'],)).fetchone()
        if participant['withdrawn']:
            abort(409, description='This participation has been withdrawn.')
        prediction = model.predict(answers)
        first_clinician = db().execute("SELECT id FROM users WHERE role='counsellor' AND active=1 ORDER BY created,id LIMIT 1").fetchone()
        stamp = now()
        try:
            db().execute('BEGIN IMMEDIATE')
            latest = db().execute('SELECT * FROM assessments WHERE user_id=?', (g.user['id'],)).fetchone()
            if latest and latest['submission_id'] == submission_id:
                db().rollback()
                return jsonify(submission=record_json(latest, True), duplicate=True)
            if latest:
                if not ws['repeat_open'](g.user['id']):
                    abort(409, description='This assessment has already been submitted.')
                ws['archive'](latest)
            db().execute('INSERT INTO assessments VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(participant_id) DO UPDATE SET submission_id=excluded.submission_id,answers=excluded.answers,submitted_at=excluded.submitted_at,updated=excluded.updated,estimate=excluded.estimate,review_state=excluded.review_state,version=assessments.version+1,complete=excluded.complete,contact_opt_in=excluded.contact_opt_in,questionnaire_version=excluded.questionnaire_version',
                         (participant['participant_id'], g.user['id'], submission_id, json.dumps(answers), stamp, stamp,
                          prediction['estimate'], 'Needs review', first_clinician['id'] if first_clinician else None, 1, int(answers.get('wellbeing_opt_in') is True), int(answers.get('contact_opt_in', False)), 1, QUESTIONNAIRE_VERSION))
            db().execute('INSERT INTO model_predictions(participant_id,result,created) VALUES(?,?,?)',
                         (participant['participant_id'], json.dumps(prediction), stamp))
        except sqlite3.IntegrityError:
            db().rollback()
            existing = db().execute('SELECT * FROM assessments WHERE user_id=? AND submission_id=?', (g.user['id'], submission_id)).fetchone()
            if existing:
                return jsonify(submission=record_json(existing, True), duplicate=True)
            abort(409, description='A submission already exists. Open your summary.')
        db().execute('DELETE FROM drafts WHERE user_id=?', (g.user['id'],))
        db().execute('DELETE FROM assessment_cycles WHERE user_id=?', (g.user['id'],))
        audit('Demo assessment submitted', participant['participant_id'])
        assigned = db().execute('SELECT assigned_to FROM assessments WHERE participant_id=?', (participant['participant_id'],)).fetchone()[0]
        ws['notify'](assigned, 'assessment:'+submission_id,
                     'An assigned assessment needs a direct wellbeing check-in.' if instruments.needs_direct_checkin(answers) else 'A new assigned assessment is ready for review.',
                     '#staff/case/'+participant['participant_id']+'/overview')
        db().commit()
        row = db().execute('SELECT * FROM assessments WHERE user_id=?', (g.user['id'],)).fetchone()
        return jsonify(submission=record_json(row, True)), 201

    @app.post('/api/assessment/result')
    @require('participant')
    def calculate_missing_result():
        payload()
        participant = db().execute('SELECT * FROM participants WHERE user_id=?', (g.user['id'],)).fetchone()
        if participant['withdrawn']:
            abort(409, description='This participation has been withdrawn.')
        row = db().execute('SELECT * FROM assessments WHERE user_id=?', (g.user['id'],)).fetchone()
        if not row:
            abort(404, description='Submit your assessment before calculating a result.')
        if row['estimate'] is not None:
            return jsonify(submission=record_json(row, True), duplicate=True)
        if row['questionnaire_version'] != QUESTIONNAIRE_VERSION:
            abort(409, description='This assessment uses a different questionnaire version and needs staff review.')
        answers = json.loads(row['answers'])
        errors = validate_answers(answers, True)
        if errors:
            return jsonify(error='This saved assessment has missing or invalid answers and needs staff review.'), 409
        prediction = model.predict(answers)
        if prediction['estimate'] is None:
            return jsonify(error='Your answers are saved, but a result is still unavailable. Please try again after the service has been restored.'), 503
        stamp = now()
        changed = db().execute('UPDATE assessments SET estimate=?,updated=?,version=version+1 WHERE participant_id=? AND version=? AND estimate IS NULL',
                               (prediction['estimate'], stamp, row['participant_id'], row['version']))
        if changed.rowcount != 1:
            db().rollback()
            latest = db().execute('SELECT * FROM assessments WHERE user_id=?', (g.user['id'],)).fetchone()
            if latest and latest['estimate'] is not None:
                return jsonify(submission=record_json(latest, True), duplicate=True)
            abort(409, description='Your assessment was updated. Reload the page before trying again.')
        db().execute('INSERT INTO model_predictions(participant_id,result,created) VALUES(?,?,?) ON CONFLICT(participant_id) DO UPDATE SET result=excluded.result,created=excluded.created',
                     (row['participant_id'], json.dumps(prediction), stamp))
        audit('Calculated previously unavailable model result', row['participant_id'], prediction['model_version'])
        db().commit()
        latest = db().execute('SELECT * FROM assessments WHERE user_id=?', (g.user['id'],)).fetchone()
        return jsonify(submission=record_json(latest, True), duplicate=False)

    @app.post('/api/support')
    @require('participant')
    def support_request():
        data = payload()
        method = text(data, 'method', 20)
        details, times = text(data, 'details', 200), text(data, 'times', 300)
        if method not in ('email', 'phone') or not details or not times or data.get('permission') is not True:
            abort(400, description='Choose a contact method, add contact details and times, and give permission to share this request.')
        if method == 'email' and ('@' not in details or '.' not in details.split('@')[-1]):
            abort(400, description='Enter a valid demo email address.')
        pid = db().execute('SELECT participant_id FROM participants WHERE user_id=?', (g.user['id'],)).fetchone()[0]
        ref = 'SUP-' + secrets.token_hex(4).upper()
        db().execute('INSERT INTO contacts VALUES(?,?,?,?,?,?,?,?)', (ref, pid, method, details, times, 'Demo request recorded — not monitored', 'counsellor', now()))
        db().execute('UPDATE assessments SET contact_opt_in=1 WHERE participant_id=?', (pid,))
        audit('Demo support request', pid, ref)
        db().commit()
        return jsonify(reference=ref, status='Demo request recorded — not monitored', created=now()), 201

    @app.get('/api/privacy/requests')
    @require('participant')
    def privacy_requests():
        return jsonify(requests=[dict(r) for r in db().execute('SELECT reference,kind,status,created FROM privacy_requests WHERE user_id=? ORDER BY created DESC', (g.user['id'],))])

    @app.post('/api/privacy/requests')
    @require('participant')
    def privacy_request():
        data = payload()
        kind = text(data, 'kind', 20)
        if kind not in ('withdraw', 'removal') or data.get('confirmed') is not True:
            abort(400, description='Confirm the participation choice you want to make.')
        ref = 'PRV-' + secrets.token_hex(4).upper()
        status = 'Demo participation withdrawn' if kind == 'withdraw' else 'Demo removal request recorded — pending operator review'
        if kind == 'withdraw':
            db().execute('UPDATE participants SET withdrawn=1 WHERE user_id=?', (g.user['id'],))
            db().execute('DELETE FROM drafts WHERE user_id=?', (g.user['id'],))
        db().execute('INSERT INTO privacy_requests VALUES(?,?,?,?,?,?)', (ref, g.user['id'], kind, status, now(), 'Demo only; no live retention policy is configured.'))
        audit('Demo privacy choice', g.user['id'], kind)
        db().commit()
        return jsonify(reference=ref, status=status, created=now()), 201

    @app.get('/api/cases')
    @require('counsellor')
    def cases():
        rows = db().execute('SELECT * FROM assessments WHERE assigned_to=? ORDER BY updated DESC', (g.user['id'],)).fetchall()
        return jsonify(cases=[record_json(r) for r in rows])

    @app.get('/api/cases/<pid>')
    @require('counsellor')
    def case_detail(pid):
        row = record(pid)
        audit('Viewed assigned assessment', pid)
        db().commit()
        return jsonify(case=record_json(row, True))

    @app.post('/api/cases/<pid>/review')
    @require('counsellor')
    def save_review(pid):
        row = record(pid)
        data = payload()
        status = text(data, 'status', 40)
        note, owner, due_date, outcome = text(data, 'note'), text(data, 'owner', 100), text(data, 'due_date', 20), text(data, 'outcome', 500)
        if status not in STATES:
            abort(400, description='Choose a valid review status.')
        if status == 'Closed' and db().execute("SELECT 1 FROM appointments WHERE participant_id=? AND state='Scheduled'", (pid,)).fetchone():
            abort(409, description='Complete or cancel outstanding appointments before closing this case.')
        if status == 'Closed' and not outcome:
            abort(400, description='A short closing reason is required.')
        if row['review_state'] == 'Closed' and status != 'Closed' and not outcome:
            abort(400, description='Give a reason for reopening this case.')
        if status == 'Follow-up arranged' and (not owner or not due_date or not outcome):
            abort(400, description='A follow-up needs an owner, due date and agreed next action.')
        if due_date:
            try:
                datetime.strptime(due_date, '%Y-%m-%d')
            except ValueError:
                abort(400, description='Choose a valid follow-up date.')
        stamp = now()
        changed = db().execute('UPDATE assessments SET review_state=?,updated=?,version=version+1 WHERE participant_id=? AND version=?', (status, stamp, pid, data.get('version')))
        if changed.rowcount != 1:
            db().rollback()
            abort(409, description='Another reviewer has changed this record. Reload the record before saving; your note has been kept on this page.')
        db().execute('INSERT INTO reviews(participant_id,actor,status,note,owner,due_date,outcome,created) VALUES(?,?,?,?,?,?,?,?)', (pid, g.user['name'], status, note, owner, due_date, outcome, stamp))
        audit('Saved confidential review', pid, status)
        db().commit()
        return jsonify(saved=True, updated=stamp, version=row['version'] + 1)

    @app.get('/api/cases/<pid>/report')
    @require('counsellor')
    def case_report(pid):
        row = record(pid)
        audit('Opened research screening report', pid)
        db().commit()
        report = record_json(row, True)
        if report['conclusion']:
            report['conclusion'].pop('private_note', None)
        report.pop('contact', None)
        report['events'] = [{key: event[key] for key in ('status', 'owner', 'due_date', 'outcome', 'created')} for event in report['events']]
        return jsonify(report=report, generated_at=now())

    @app.get('/api/research')
    @require('researcher')
    def research():
        rows = db().execute('SELECT estimate,complete,submitted_at FROM assessments').fetchall()
        distribution = [{'label': label, 'count': sum(1 for r in rows if r['estimate'] == value)} for label, value in (('Low', 'Low'), ('Moderate', 'Moderate'), ('High', 'High'), ('No estimate', None))]
        audit('Viewed aggregate demo data')
        db().commit()
        return jsonify(total=len(rows), complete=sum(r['complete'] for r in rows), distribution=distribution,
                       suppression='Subgroup breakdowns disabled until a study suppression rule is approved.',
                       model=model.status())

    @app.get('/api/model')
    @require('researcher', 'counsellor', 'administrator')
    def model_status():
        return jsonify(model=model.status())

    @app.get('/api/research/export')
    @require('researcher')
    def export_research():
        rows = db().execute('SELECT estimate,COUNT(*) AS count FROM assessments GROUP BY estimate').fetchall()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['DEMO aggregate research screening summary', 'Generated ' + now()])
        writer.writerow(['Demo class (synthetic model or preloaded example; not clinically validated)', 'Count'])
        writer.writerows([(r['estimate'] or 'No estimate', r['count']) for r in rows])
        audit('Exported aggregate demo report')
        db().commit()
        response = make_response(output.getvalue())
        response.headers.update({'Content-Type': 'text/csv; charset=utf-8', 'Content-Disposition': 'attachment; filename=between-demo-aggregate.csv'})
        return response

    @app.get('/api/admin')
    @require('administrator')
    def admin():
        return jsonify(model=model.status(), accounts=[dict(r) for r in db().execute('SELECT id,email,name,role,active FROM users WHERE role != ? ORDER BY name', ('participant',))],
                       assignments=[dict(r) for r in db().execute('SELECT participant_id,assigned_to FROM assessments ORDER BY participant_id')],
                       config=[dict(r) for r in db().execute('SELECT key,value,version FROM config ORDER BY key')],
                       audit=[dict(r) for r in db().execute('SELECT * FROM audit ORDER BY id DESC LIMIT 100')])

    @app.post('/api/admin/account')
    @require('administrator')
    def account():
        data = payload()
        uid = text(data, 'id', 100)
        role = text(data, 'role', 30)
        if role not in ('counsellor', 'researcher', 'administrator') or type(data.get('active')) is not bool or data.get('confirmed') is not True:
            abort(400, description='Confirm the staff account, role and access state.')
        existing = db().execute('SELECT * FROM users WHERE id=? AND role != ?', (uid, 'participant')).fetchone()
        if not existing:
            abort(404, description='Staff account not found.')
        if uid == g.user['id']:
            abort(400, description='Ask another administrator to change your own access.')
        if existing['role'] == 'counsellor' and (not data['active'] or role != 'counsellor'):
            if db().execute("SELECT 1 FROM appointments WHERE owner_id=? AND state='Scheduled'", (uid,)).fetchone():
                abort(409, description='Reassign this clinician’s scheduled appointments before changing their access.')
            count = db().execute('SELECT count(*) FROM assessments WHERE assigned_to=? AND review_state != ?', (uid, 'Closed')).fetchone()[0]
            if count:
                abort(409, description='Reassign this counsellor’s open cases before changing their access.')
        db().execute('UPDATE users SET role=?,active=? WHERE id=?', (role, int(data['active']), uid))
        audit('Changed staff access', uid, role + (' active' if data['active'] else ' inactive'))
        db().commit()
        return jsonify(saved=True)

    @app.post('/api/admin/invite')
    @require('administrator')
    def invite():
        if not app.config['DEMO_MODE']:
            abort(403, description='Use account invitations to create staff access.')
        data = payload()
        email, name, role = text(data, 'email', 254).lower(), text(data, 'name', 100), text(data, 'role', 30)
        if '@' not in email or not name or role not in ('counsellor', 'researcher', 'administrator') or data.get('confirmed') is not True:
            abort(400, description='Provide a name, email, role and confirmation.')
        temporary_password = secrets.token_urlsafe(18)
        uid = 'staff-' + uuid.uuid4().hex[:12]
        try:
            db().execute('INSERT INTO users VALUES(?,?,?,?,?,?,?)', (uid, email, generate_password_hash(temporary_password), name, role, 1, now()))
        except sqlite3.IntegrityError:
            abort(409, description='An account already uses that email.')
        audit('Created demo staff access', uid, role)
        db().commit()
        return jsonify(saved=True, temporary_password=temporary_password, message='Demo account created. No invitation email has been sent.'), 201

    @app.post('/api/admin/assignment')
    @require('administrator')
    def assignment():
        data = payload()
        pid, owner = text(data, 'participant_id', 50), text(data, 'owner', 100)
        if not db().execute('SELECT 1 FROM users WHERE id=? AND role=? AND active=1', (owner, 'counsellor')).fetchone():
            abort(400, description='Choose an active counsellor.')
        changed = db().execute('UPDATE assessments SET assigned_to=?,version=version+1,updated=? WHERE participant_id=?', (owner, now(), pid))
        if changed.rowcount != 1:
            abort(404, description='Assessment not found.')
        db().execute("UPDATE appointments SET owner_id=?,version=version+1 WHERE participant_id=? AND state='Scheduled'", (owner, pid))
        ws['notify'](owner, 'assignment:'+pid+':'+now(), 'An assessment has been assigned to your workspace.', '#staff/case/'+pid+'/overview')
        audit('Changed assignment', pid, owner)
        db().commit()
        return jsonify(saved=True)

    @app.post('/api/admin/config')
    @require('administrator')
    def configure():
        data = payload()
        key, value = text(data, 'key', 50), text(data, 'value', 4000)
        if key not in ('consent', 'questionnaire', 'support_directory', 'enrolment'):
            abort(400, description='This configuration is read-only.')
        if not value:
            abort(400, description='Enter a configuration note.')
        if key == 'enrolment' and value != 'Demo only — live enrolment closed':
            abort(400, description='Live enrolment cannot be enabled in this prototype.')
        changed = db().execute('UPDATE config SET value=?,version=version+1 WHERE key=? AND version=?', (value, key, data.get('version')))
        if changed.rowcount != 1:
            abort(409, description='This configuration changed. Reload before saving.')
        audit('Versioned demo configuration', key, value)
        db().commit()
        return jsonify(saved=True)

    @app.get('/healthz')
    def health():
        return jsonify(status='ok')

    @app.get('/readyz')
    def ready():
        try:
            db().execute('SELECT 1').fetchone()
            sample={'age':19,'daily_time':'1to3','passive':'sometimes','active':'sometimes','night':'sometimes','cyberbullying':'never','regular_count':'2'}
            ok = model.status()['available'] and model.predict(sample)['estimate'] is not None
        except sqlite3.Error:
            ok = False
        return jsonify(status='ready' if ok else 'unavailable'), 200 if ok else 503

    with app.app_context():
        init_db(db(), seed=app.config['DEMO_MODE'])
        if app.config['PRODUCTION'] and db().execute("SELECT 1 FROM users WHERE active=1 AND email LIKE '%@between.demo'").fetchone():
            raise ValueError('Production cannot use active public example accounts. Configure a fresh private database and bootstrap an administrator.')
        workspace.init_schema(db())
    ws = workspace.register(app, db, require, user, payload, text, record, record_json, audit, now)
    app.extensions['workspace'] = ws
    return app


def init_db(connection, seed=True):
    connection.executescript('''
    CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,password TEXT NOT NULL,name TEXT NOT NULL,role TEXT NOT NULL,active INTEGER NOT NULL,created TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS participants(user_id TEXT PRIMARY KEY REFERENCES users(id),participant_id TEXT UNIQUE NOT NULL,withdrawn INTEGER NOT NULL,created TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS drafts(user_id TEXT PRIMARY KEY REFERENCES users(id),answers TEXT NOT NULL,step INTEGER NOT NULL,updated TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS assessments(participant_id TEXT PRIMARY KEY,user_id TEXT UNIQUE REFERENCES users(id),submission_id TEXT UNIQUE NOT NULL,answers TEXT NOT NULL,submitted_at TEXT NOT NULL,updated TEXT NOT NULL,estimate TEXT,review_state TEXT NOT NULL,assigned_to TEXT REFERENCES users(id),version INTEGER NOT NULL,complete INTEGER NOT NULL,contact_opt_in INTEGER NOT NULL,demo INTEGER NOT NULL,questionnaire_version TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS model_predictions(participant_id TEXT PRIMARY KEY REFERENCES assessments(participant_id),result TEXT NOT NULL,created TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY,participant_id TEXT REFERENCES assessments(participant_id),actor TEXT,status TEXT,note TEXT,owner TEXT,due_date TEXT,outcome TEXT,created TEXT);
    CREATE TABLE IF NOT EXISTS contacts(reference TEXT PRIMARY KEY,participant_id TEXT,method TEXT,details TEXT,times TEXT,status TEXT,assigned_to TEXT,created TEXT);
    CREATE TABLE IF NOT EXISTS privacy_requests(reference TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),kind TEXT,status TEXT,created TEXT,detail TEXT);
    CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,actor TEXT,action TEXT,target TEXT,detail TEXT,created TEXT);
    CREATE TABLE IF NOT EXISTS config(key TEXT PRIMARY KEY,value TEXT NOT NULL,version INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS login_attempts(id INTEGER PRIMARY KEY,address TEXT,attempted REAL);
    CREATE INDEX IF NOT EXISTS assigned_cases ON assessments(assigned_to,updated);
    CREATE INDEX IF NOT EXISTS review_events ON reviews(participant_id,created);
    ''')
    if not seed or connection.execute('SELECT 1 FROM users LIMIT 1').fetchone():
        return
    stamp = now()
    password = generate_password_hash('BetweenDemo!26')
    for uid, email, name, role in (
        ('participant', 'participant@between.demo', 'Alex', 'participant'),
        ('counsellor', 'counsellor@between.demo', 'Jamie Morgan', 'counsellor'),
        ('counsellor2', 'counsellor2@between.demo', 'Robin Kim', 'counsellor'),
        ('researcher', 'researcher@between.demo', 'Taylor Reed', 'researcher'),
        ('admin', 'admin@between.demo', 'Sam Patel', 'administrator')):
        connection.execute('INSERT INTO users VALUES(?,?,?,?,?,?,?)', (uid, email, password, name, role, 1, stamp))
    connection.execute('INSERT INTO participants VALUES(?,?,?,?)', ('participant', 'D-0201', 0, stamp))
    examples = [('P-0142', 'Moderate', 'Needs review', 'counsellor'), ('P-0108', 'High', 'Needs review', 'counsellor'),
                ('P-0186', None, 'Needs review', 'counsellor'), ('P-0094', 'Low', 'Follow-up arranged', 'counsellor'),
                ('P-0151', 'Moderate', 'In progress', 'counsellor'), ('P-0163', 'Low', 'Closed', 'counsellor'),
                ('P-0172', 'Moderate', 'Needs review', 'counsellor'), ('P-0087', 'Low', 'In progress', 'counsellor'),
                ('P-0999', 'High', 'Needs review', 'counsellor2')]
    for i, (pid, estimate, status, owner) in enumerate(examples):
        answers = {'age': 19, 'consent': True, 'privacy': True, 'contact_opt_in': False,
                   'gender': 'prefer_not', 'education': 'university', 'platforms': ['instagram', 'whatsapp', 'youtube'],
                   'daily_time': '1to3', 'passive': 'often', 'active': 'often', 'night': 'sometimes', 'cyberbullying': 'never', 'regular_count': '3'}
        if pid == 'P-0186':
            answers.pop('night')
        created = (datetime.now(timezone.utc) - timedelta(hours=i + 1)).isoformat(timespec='seconds')
        connection.execute('INSERT INTO assessments VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (pid, None, 'seed-' + pid, json.dumps(answers), created, created, estimate, status, owner, 1, 0, 0, 1, QUESTIONNAIRE_VERSION))
        if status in ('Follow-up arranged', 'Closed'):
            connection.execute('INSERT INTO reviews(participant_id,actor,status,note,owner,due_date,outcome,created) VALUES(?,?,?,?,?,?,?,?)', (pid, 'Jamie Morgan', status, 'Fictional demonstration review.', 'Jamie Morgan', '2026-11-10' if status != 'Closed' else '', 'Demo follow-up agreed.' if status != 'Closed' else 'Demo review completed.', created))
    for key, value in (
        ('consent', 'Demo consent v1. Research consent, guardian verification and assent wording await protocol approval.'),
        ('questionnaire', 'behaviour-demo-1 with optional wellbeing-1 PHQ-9/GAD-7 responses. WEMWBS totals require a licensed source administration. Local clinical protocol and age-group suitability need professional approval.'),
        ('support_directory', 'Manage source-checked contacts under Support directory. Support-request response coverage is an operator responsibility; the demonstration is not monitored.'),
        ('enrolment', 'Demo only — live enrolment closed')):
        connection.execute('INSERT INTO config VALUES(?,?,?)', (key, value, 1))
    connection.execute('INSERT INTO audit(actor,action,target,detail,created) VALUES(?,?,?,?,?)', ('system', 'Demo workspace created', 'study', 'All example records and model classes are fictional.', stamp))
    connection.commit()


if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=int(os.environ.get('PORT', '5000')), debug=False)
