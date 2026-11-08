import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app


@pytest.fixture
def app(tmp_path):
    return create_app({'TESTING': True, 'SECRET_KEY': 'test-only-key', 'DATABASE': str(tmp_path / 'test.sqlite3')})


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, role='participant'):
    csrf = client.get('/api/session').json['csrf']
    result = client.post('/api/login', json={'email': role + '@between.demo', 'password': 'BetweenDemo!26'}, headers={'X-CSRF-Token': csrf})
    assert result.status_code == 200
    return {'X-CSRF-Token': result.json['csrf']}


def answers(**overrides):
    data = {'age': 19, 'consent': True, 'privacy': True, 'contact_opt_in': False, 'gender': 'prefer_not',
            'education': 'university', 'platforms': ['instagram', 'youtube'], 'daily_time': '1to3',
            'passive': 'often', 'active': 'rarely', 'night': 'sometimes', 'cyberbullying': 'never', 'regular_count': '2'}
    data.update(overrides)
    return data


def submit(client, headers, **overrides):
    return client.post('/api/assessment/submit', json={'answers': answers(**overrides), 'submission_id': 'test-submission'}, headers=headers)


def test_home_assets_and_privacy_headers(client):
    response = client.get('/')
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    assert "frame-ancestors 'none'" in response.headers['Content-Security-Policy']
    assert client.get('/static/app.js').status_code == 200
    assert client.get('/static/fonts/font-0.woff2').status_code == 200


def test_csrf_is_required(client):
    client.get('/api/session')
    assert client.post('/api/login', json={'email': 'participant@between.demo', 'password': 'BetweenDemo!26'}).status_code == 403


def test_wrong_password_and_session_rotation(client):
    csrf = client.get('/api/session').json['csrf']
    bad = client.post('/api/login', json={'email': 'participant@between.demo', 'password': 'wrong'}, headers={'X-CSRF-Token': csrf})
    assert bad.status_code == 401
    headers = login(client)
    assert headers['X-CSRF-Token'] != csrf
    assert client.post('/api/session/extend', json={}, headers=headers).status_code == 200


@pytest.mark.parametrize('role,endpoint', [('participant','/api/cases'),('participant','/api/research'),('participant','/api/admin'),('counsellor','/api/admin'),('counsellor','/api/research'),('researcher','/api/cases'),('admin','/api/cases')])
def test_separate_role_permissions(client, role, endpoint):
    login(client, role)
    assert client.get(endpoint).status_code == 403


def test_assigned_cases_only(client):
    login(client, 'counsellor')
    rows = client.get('/api/cases').json['cases']
    assert len(rows) == 8
    assert 'P-0999' not in [r['participant_id'] for r in rows]
    assert client.get('/api/cases/P-0999').status_code == 403
    assert client.get('/api/cases/P-0999/report').status_code == 403


def test_server_draft_recovers_after_sign_in(client):
    headers = login(client)
    result = client.put('/api/assessment/draft', json={'answers': answers(), 'step': 2}, headers=headers)
    assert result.status_code == 200 and result.json['saved']
    client.post('/api/logout', json={}, headers=headers)
    assert client.get('/api/assessment').status_code == 401
    login(client)
    draft = client.get('/api/assessment').json['draft']
    assert draft['step'] == 2 and draft['answers']['night'] == 'sometimes'


def test_unanswered_draft_and_consent_enforcement(client):
    headers = login(client)
    assert client.put('/api/assessment/draft', json={'answers': {'age': 19, 'consent': True, 'privacy': True, 'platforms': []}, 'step': 2}, headers=headers).status_code == 200
    assert client.put('/api/assessment/draft', json={'answers': answers(consent=False), 'step': 2}, headers=headers).status_code == 400


@pytest.mark.parametrize('age', [12,25,13.5,True,'19'])
def test_invalid_age_rejected(client, age):
    headers = login(client)
    response = submit(client, headers, age=age)
    assert response.status_code == 400
    assert 'age' in response.json['fields']


def test_minor_authorisation_and_assent_separate(client):
    headers = login(client)
    response = submit(client, headers, age=16, guardian=True, assent=False)
    assert response.status_code == 400
    assert 'assent' in response.json['fields']
    response = submit(client, headers, age=16, guardian=True, assent=True)
    assert response.status_code == 201


def test_saved_synthetic_estimate_and_no_fabricated_questionnaire_scores(client):
    headers = login(client)
    result = submit(client, headers)
    assert result.status_code == 201
    record = result.json['submission']
    assert record['estimate'] in ('Low', 'Moderate', 'High')
    assert record['model_version'] == 'synthetic-v1'
    assert record['prediction']['source'] == 'synthetic_model'
    assert record['prediction']['synthetic'] is True
    assert sum(record['prediction']['probabilities'].values()) == pytest.approx(1)
    assert all(i['score'] is None and i['status'] == 'Not administered' for i in record['instruments'])
    duplicate = submit(client, headers).json
    assert duplicate['duplicate'] is True
    assert duplicate['submission']['prediction'] == record['prediction']
    result = client.post('/api/assessment/submit', json={'answers': answers(), 'submission_id': 'different-id'}, headers=headers)
    assert result.status_code == 409


def test_missing_input_cannot_become_zero_or_low(client):
    headers = login(client)
    data = answers(); del data['night']
    response = client.post('/api/assessment/submit', json={'answers': data, 'submission_id': 'missing'}, headers=headers)
    assert response.status_code == 400 and 'night' in response.json['fields']
    assert client.get('/api/assessment').json['submission'] is None


def test_malicious_questionnaire_value_does_not_crash(client):
    headers = login(client)
    result = submit(client, headers, platforms=[{'bad': 'value'}])
    assert result.status_code == 400


def test_staff_notes_never_returned_to_participant(client):
    headers = login(client)
    assert submit(client, headers).status_code == 201
    headers = login(client, 'counsellor')
    result = client.post('/api/cases/D-0201/review', json={'version': 1, 'status': 'In progress', 'note': 'Staff confidential note'}, headers=headers)
    assert result.status_code == 200
    assert client.get('/api/cases/D-0201').json['case']['events'][0]['note'] == 'Staff confidential note'
    login(client)
    result = client.get('/api/assessment')
    assert 'Staff confidential note' not in result.get_data(as_text=True)
    assert result.json['submission']['events'] == []


def test_review_conflicts_and_closing_reason(client):
    headers = login(client, 'counsellor')
    path = '/api/cases/P-0142/review'
    assert client.post(path, json={'version': 1, 'status': 'Closed'}, headers=headers).status_code == 400
    assert client.post(path, json={'version': 1, 'status': 'In progress', 'note': 'First review'}, headers=headers).status_code == 200
    assert client.post(path, json={'version': 1, 'status': 'Closed', 'outcome': 'Stale write'}, headers=headers).status_code == 409
    record = client.get('/api/cases/P-0142').json['case']
    assert record['review_state'] == 'In progress' and record['estimate'] == 'Moderate'
    assert client.post(path, json={'version': 2, 'status': 'Closed', 'outcome': 'Demo completed'}, headers=headers).status_code == 200
    assert client.post(path, json={'version': 3, 'status': 'In progress'}, headers=headers).status_code == 400


def test_follow_up_requires_owner_due_date_and_next_action(client):
    headers = login(client, 'counsellor')
    path = '/api/cases/P-0142/review'
    data = {'version': 1, 'status': 'Follow-up arranged', 'owner': 'Jamie', 'due_date': 'not-a-date', 'outcome': 'Conversation'}
    assert client.post(path, json=data, headers=headers).status_code == 400
    data['due_date'] = '2026-11-20'
    assert client.post(path, json=data, headers=headers).status_code == 200


def test_report_excludes_confidential_notes(client):
    headers = login(client, 'counsellor')
    client.post('/api/cases/P-0142/review', json={'version': 1, 'status': 'In progress', 'note': 'Private staff content', 'outcome': 'Agreed demo next action'}, headers=headers)
    result = client.get('/api/cases/P-0142/report')
    assert result.status_code == 200
    assert 'Private staff content' not in result.get_data(as_text=True)
    assert 'Agreed demo next action' in result.get_data(as_text=True)


def test_support_needs_separate_permission_and_restricts_identity(client):
    headers = login(client)
    data = {'method': 'email', 'details': 'example@example.com', 'times': 'Afternoons', 'permission': False}
    assert client.post('/api/support', json=data, headers=headers).status_code == 400
    submit(client, headers)
    data['permission'] = True
    result = client.post('/api/support', json=data, headers=headers)
    assert result.status_code == 201 and 'not monitored' in result.json['status']
    login(client, 'counsellor')
    assert client.get('/api/cases/D-0201').json['case']['contact']['details'] == 'example@example.com'
    login(client, 'researcher')
    assert 'example@example.com' not in client.get('/api/research').get_data(as_text=True)


def test_withdrawal_removes_draft_and_prevents_submission(client):
    headers = login(client)
    client.put('/api/assessment/draft', json={'answers': answers(), 'step': 2}, headers=headers)
    result = client.post('/api/privacy/requests', json={'kind': 'withdraw', 'confirmed': True}, headers=headers)
    assert result.status_code == 201
    assert client.get('/api/assessment').json['draft'] is None
    assert submit(client, headers).status_code == 409
    assert len(client.get('/api/privacy/requests').json['requests']) == 1


def test_removal_is_request_not_claim_of_erasure(client):
    headers = login(client)
    submit(client, headers)
    result = client.post('/api/privacy/requests', json={'kind': 'removal', 'confirmed': True}, headers=headers)
    assert 'pending operator review' in result.json['status']
    assert client.get('/api/assessment').json['submission'] is not None


def test_aggregate_only_research_and_no_estimate_separate(client):
    login(client, 'researcher')
    result = client.get('/api/research').json
    assert sum(d['count'] for d in result['distribution']) == result['total']
    assert next(d['count'] for d in result['distribution'] if d['label'] == 'No estimate') == 1
    assert result['model']['available'] is True
    assert result['model']['synthetic'] is True
    assert result['model']['released'] is False
    assert result['model']['metrics']['sample_size'] == 900
    assert 'P-0142' not in json.dumps(result)
    export = client.get('/api/research/export').get_data(as_text=True)
    assert 'No estimate' in export and 'P-0142' not in export


def test_reassignment_enforced_immediately_and_audited(client):
    headers = login(client, 'admin')
    result = client.post('/api/admin/assignment', json={'participant_id': 'P-0142', 'owner': 'counsellor2'}, headers=headers)
    assert result.status_code == 200
    assert any(e['action'] == 'Changed assignment' for e in client.get('/api/admin').json['audit'])
    login(client, 'counsellor')
    assert client.get('/api/cases/P-0142').status_code == 403
    login(client, 'counsellor2')
    assert client.get('/api/cases/P-0142').status_code == 200


def test_admin_protects_own_account_and_open_case_owners(client):
    headers = login(client, 'admin')
    assert client.post('/api/admin/account', json={'id':'admin','role':'researcher','active':False,'confirmed':True}, headers=headers).status_code == 400
    assert client.post('/api/admin/account', json={'id':'counsellor','role':'counsellor','active':False,'confirmed':True}, headers=headers).status_code == 409


def test_configuration_versioning_and_live_enrolment_locked(client):
    headers = login(client, 'admin')
    data = {'key': 'consent', 'value': 'New demo note', 'version': 1}
    assert client.post('/api/admin/config', json=data, headers=headers).status_code == 200
    assert client.post('/api/admin/config', json=data, headers=headers).status_code == 409
    assert client.post('/api/admin/config', json={'key':'enrolment','value':'Open','version':1}, headers=headers).status_code == 400


def test_expired_and_deactivated_sessions_are_rejected(app, client):
    headers = login(client)
    with client.session_transaction() as session:
        session['expires'] = 0
    assert client.get('/api/assessment').status_code == 401
    login(client)
    with sqlite3.connect(app.config['DATABASE']) as connection:
        connection.execute("UPDATE users SET active=0 WHERE id='participant'")
    assert client.get('/api/assessment').status_code == 401
