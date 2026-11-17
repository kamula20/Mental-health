"""Cross-role journeys for screening, longitudinal records and clinician follow-up."""
import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from app import create_app
from instruments import score, validate
from test_app import answers, login, submit


@pytest.fixture
def app(tmp_path):
    return create_app({'TESTING':True,'SECRET_KEY':'workspace-test','DATABASE':str(tmp_path / 'workspace.sqlite3')})


def test_screening_boundaries_and_no_missing_score_imputation():
    for total, band in [(0,'Minimal'),(5,'Mild'),(10,'Moderate'),(15,'Moderately severe'),(20,'Severe'),(27,'Severe')]:
        values=[min(3,max(0,total-3*i)) for i in range(9)]
        data=answers(wellbeing_opt_in=True,phq9=values,gad7=[0]*7,phq9_difficulty=0)
        assert score(data)[0]['score']==total
        assert score(data)[0]['band']==band
    assert score(answers())[0]['score'] is None
    assert 'phq9' in validate(answers(wellbeing_opt_in=True,phq9=[True]*9,gad7=[0]*7),True)
    assert 'phq9' in validate(answers(wellbeing_opt_in=True,phq9=[None]*9,gad7=[0]*7),True)
    assert 'phq9_difficulty' in validate(answers(wellbeing_opt_in=True,phq9=[1]*9,gad7=[0]*7),True)


def test_optional_questionnaires_are_scored_separately_from_model(app):
    client=app.test_client(); headers=login(client)
    data=answers(wellbeing_opt_in=True,phq9=[1]*9,gad7=[2]*7,phq9_difficulty=1,gad7_difficulty=2)
    response=client.post('/api/assessment/submit',json={'answers':data,'submission_id':'screening'},headers=headers)
    assert response.status_code==201,response.json
    r=response.json['submission']
    assert r['instruments'][0]['score']==9 and r['instruments'][1]['score']==14
    assert r['instruments'][2]['score'] is None
    assert r['needs_direct_checkin'] is True
    direct=app.extensions['between_model'].predict(answers())
    assert r['prediction']['probabilities']==direct['probabilities']


def test_repeated_assessments_preserve_history_and_private_review_boundaries(app):
    client=app.test_client(); headers=login(client)
    old=submit(client,headers).json['submission']
    staff=login(client,'counsellor')
    client.post('/api/cases/D-0201/review',json={'version':1,'status':'In progress','note':'OLD PRIVATE NOTE'},headers=staff)
    signed=client.post('/api/cases/D-0201/conclusion',json={'record_version':2,'version':0,'conclusion':'Further conversation recommended','agreement':'Disagree','rationale':'Clinical context differs','private_note':'PRIVATE CONCLUSION','shared_summary':'Let us discuss your sleep.','published':True},headers=staff)
    assert signed.status_code==200,signed.json
    assert signed.json['review_state']=='In progress'
    headers=login(client)
    assert client.get('/api/assessment').json['submission']['conclusion']['shared_summary']=='Let us discuss your sleep.'
    assert 'PRIVATE' not in client.get('/api/assessment').get_data(as_text=True)
    assert client.post('/api/assessment/repeat',json={'confirmed':True},headers=headers).status_code==200
    data=answers(daily_time='under1')
    assert client.put('/api/assessment/draft',json={'answers':data,'step':2},headers=headers).status_code==200
    result=client.post('/api/assessment/submit',json={'answers':data,'submission_id':'follow-up-2'},headers=headers)
    assert result.status_code==201,result.json
    new=result.json['submission']
    assert new['submitted_at'] and new['answers']['daily_time']=='under1'
    assert new['version']==4 and new['conclusion'] is None
    history=client.get('/api/assessment/history')
    assert len(history.json['visits'])==2
    assert history.json['visits'][0]['answers']==old['answers']
    assert 'PRIVATE' not in history.get_data(as_text=True)
    login(client,'counsellor')
    private=client.get('/api/cases/D-0201/history')
    assert 'OLD PRIVATE NOTE' in private.get_data(as_text=True)
    assert 'PRIVATE CONCLUSION' in private.get_data(as_text=True)
    login(client,'counsellor2')
    assert client.get('/api/cases/D-0201/history').status_code==403


def test_signoff_and_wemwbs_require_assignment_version_and_provenance(app):
    client=app.test_client(); h=login(client,'counsellor')
    data={'version':0,'record_version':1,'conclusion':'Assessment complete','agreement':'Disagree','published':False}
    assert client.post('/api/cases/P-0142/conclusion',json=data,headers=h).status_code==400
    data['rationale']='Independent clinical assessment'
    assert client.post('/api/cases/P-0142/conclusion',json=data,headers=h).status_code==200
    assert client.post('/api/cases/P-0142/conclusion',json=data,headers=h).status_code==409
    total={'total':45,'record_version':2,'source_reference':'Licensed paper form 1','licensed_administration':True}
    assert client.post('/api/cases/P-0142/wemwbs',json=total,headers=h).status_code==200
    assert client.get('/api/cases/P-0142').json['case']['instruments'][2]['score']==45
    total['licensed_administration']=False
    assert client.post('/api/cases/P-0142/wemwbs',json=total,headers=h).status_code==400


def test_appointment_scope_conflicts_notifications_and_reminders(app):
    client=app.test_client(); h=login(client)
    submit(client,h)
    h=login(client,'counsellor')
    starts=(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat()
    data={'starts_at':starts,'duration':30,'mode':'Video','location':'Discuss connection details with your clinician','state':'Scheduled'}
    response=client.post('/api/cases/D-0201/appointments',json=data,headers=h)
    assert response.status_code==200,response.json
    appt=response.json
    assert client.get('/api/cases/D-0201').json['case']['review_state']=='Follow-up arranged'
    data.update(id=appt['id'],version=0,state='Completed')
    assert client.post('/api/cases/D-0201/appointments',json=data,headers=h).status_code==409
    login(client,'counsellor2')
    assert not client.get('/api/appointments').json['appointments']
    login(client)
    assert len(client.get('/api/appointments').json['appointments'])==1
    assert len(client.get('/api/notifications').json['notifications'])==1
    with app.app_context():
        assert app.extensions['workspace']['send_reminders']()==1
        assert app.extensions['workspace']['send_reminders']()==0
    assert len(client.get('/api/notifications').json['notifications'])==2


def test_service_directory_only_publishes_staff_checked_contacts(app):
    client=app.test_client(); h=login(client,'admin')
    service={'name':'Fictional campus counselling desk','kind':'In person','contact':'Example student services office','hours':'Weekdays 09:00-17:00','eligibility':'Example campus members','source_url':'https://example.org/services','checked_on':datetime.now(timezone.utc).date().isoformat(),'confirmed_checked':True,'active':True,'version':0}
    response=client.post('/api/admin/services',json=service,headers=h)
    assert response.status_code==200,response.json
    assert len(client.get('/api/support/services').json['services'])==1
    service.update(id=response.json['id'],version=1,active=False)
    assert client.post('/api/admin/services',json=service,headers=h).status_code==200
    assert not client.get('/api/support/services').json['services']


def test_invitation_activation_reset_single_use_and_session_revocation(app):
    client=app.test_client(); h=login(client,'admin')
    invitation=client.post('/api/admin/invitations',json={'name':'Invited clinician','email':'invite@example.test','role':'counsellor','confirmed':True},headers=h)
    assert invitation.status_code==201,invitation.json
    mail=client.get('/api/admin/mail').json['messages'][0]
    token=re.search(r'/#account/set-password/([A-Za-z0-9_-]+)',mail['body']).group(1)
    recipient=app.test_client(); csrf=recipient.get('/api/session').json['csrf']
    changed=recipient.post('/api/account/password',json={'token':token,'password':'A-long-new-password!'},headers={'X-CSRF-Token':csrf})
    assert changed.status_code==200,changed.json
    csrf=recipient.get('/api/session').json['csrf']
    assert recipient.post('/api/account/password',json={'token':token,'password':'Another-password!'},headers={'X-CSRF-Token':csrf}).status_code==400
    signed=recipient.post('/api/login',json={'email':'invite@example.test','password':'A-long-new-password!'},headers={'X-CSRF-Token':csrf})
    assert signed.status_code==200
    anonymous=app.test_client(); csrf=anonymous.get('/api/session').json['csrf']
    known=anonymous.post('/api/account/recovery',json={'email':'invite@example.test'},headers={'X-CSRF-Token':csrf})
    unknown=anonymous.post('/api/account/recovery',json={'email':'absent@example.test'},headers={'X-CSRF-Token':csrf})
    assert known.json==unknown.json
    with sqlite3.connect(app.config['DATABASE']) as conn:
        body=conn.execute("SELECT body FROM mail_outbox WHERE subject='Reset your Between password'").fetchone()[0]
    reset=re.search(r'/#account/set-password/([A-Za-z0-9_-]+)',body).group(1)
    assert anonymous.post('/api/account/password',json={'token':reset,'password':'A-different-password!'},headers={'X-CSRF-Token':csrf}).status_code==200
    assert recipient.get('/api/cases').status_code==401


def test_production_disables_demo_seeding_and_requires_secure_settings(tmp_path):
    with pytest.raises(ValueError):
        create_app({'PRODUCTION':True,'DATABASE':str(tmp_path / 'bad.sqlite3')})
    app=create_app({'TESTING':True,'PRODUCTION':True,'DEMO_MODE':False,'SECRET_KEY':'x'*40,'SESSION_COOKIE_SECURE':True,'APP_BASE_URL':'https://example.test','MAIL_MODE':'manual','DATABASE':str(tmp_path / 'secure.sqlite3')})
    with sqlite3.connect(app.config['DATABASE']) as conn:
        assert conn.execute('SELECT count(*) FROM users').fetchone()[0]==0
    assert app.test_client().get('/healthz').status_code==200
    assert app.test_client().get('/readyz').status_code==200
