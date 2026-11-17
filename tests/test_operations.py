"""Backup, deployment and external-evaluation evidence checks."""
import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest
from cryptography.fernet import Fernet, InvalidToken

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import create_app
from ml.validate_external import evaluate_external
from tools.manage import encrypted_backup, restore_backup
from test_app import answers, login, submit


def test_encrypted_backup_restores_consistent_data_and_never_overwrites(tmp_path):
    database=tmp_path / 'source.sqlite3'
    with sqlite3.connect(database) as connection:
        connection.execute('CREATE TABLE example(value TEXT)')
        connection.execute('INSERT INTO example VALUES(?)',('Private example content',))
    key=Fernet.generate_key()
    encrypted=encrypted_backup(database,tmp_path / 'backup.fernet',key)
    assert b'Private example content' not in encrypted.read_bytes()
    assert not encrypted.read_bytes().startswith(b'SQLite format')
    restored=restore_backup(encrypted,tmp_path / 'restored.sqlite3',key)
    with sqlite3.connect(restored) as connection:
        assert connection.execute('SELECT value FROM example').fetchone()[0]=='Private example content'
    with pytest.raises(ValueError,match='already exists'):
        encrypted_backup(database,encrypted,key)
    with pytest.raises(ValueError,match='new file'):
        restore_backup(encrypted,restored,key)
    with pytest.raises(InvalidToken):
        restore_backup(encrypted,tmp_path / 'wrong.sqlite3',Fernet.generate_key())
    assert not (tmp_path / 'wrong.sqlite3').exists()


def test_health_readiness_and_production_reject_public_example_accounts(tmp_path):
    config={'TESTING':True,'SECRET_KEY':'fixture','DATABASE':str(tmp_path / 'readiness.sqlite3'),'ML_ARTIFACT_DIR':str(tmp_path / 'absent')}
    client=create_app(config).test_client()
    assert client.get('/healthz').json=={'status':'ok'}
    assert client.get('/readyz').status_code==503
    assert client.get('/readyz').json=={'status':'unavailable'}
    config.update(PRODUCTION=True,DEMO_MODE=False,SECRET_KEY='x'*40,SESSION_COOKIE_SECURE=True,APP_BASE_URL='https://example.test',MAIL_MODE='manual')
    with pytest.raises(ValueError,match='public example accounts'):
        create_app(config)


def test_external_evaluation_requires_declarations_and_rejects_demo_data(tmp_path):
    rows=[]
    for i in range(30):
        row={**answers(),'study_id':f'FIXTURE-{i}','reference_class':['Low','Moderate','High'][i%3]}
        row['daily_time']=['under1','1to3','5plus'][i%3]
        rows.append(row)
    source=tmp_path / 'external-fixture.csv'
    pd.DataFrame(rows).to_csv(source,index=False)
    out=tmp_path / 'report.json'
    with pytest.raises(ValueError,match='Confirm consent'):
        evaluate_external(source,out,'Automated test fixture')
    report=evaluate_external(source,out,'Automated test fixture only; not a participant study',True)
    assert report['clinical_release'] is False and report['metrics']['sample_size']==30
    assert 'FIXTURE-' not in out.read_text()
    rows[0]['study_id']='SYN-000001'
    pd.DataFrame(rows).to_csv(source,index=False)
    with pytest.raises(ValueError,match='demonstration dataset'):
        evaluate_external(source,out,'Test fixture',True)


def test_history_submission_retry_does_not_create_another_visit(tmp_path):
    config={'TESTING':True,'SECRET_KEY':'fixture','DATABASE':str(tmp_path / 'history.sqlite3')}
    client=create_app(config).test_client(); h=login(client)
    first=submit(client,h).json['submission']
    client.post('/api/assessment/repeat',json={'confirmed':True},headers=h)
    second=client.post('/api/assessment/submit',json={'answers':answers(daily_time='under1'),'submission_id':'second'},headers=h)
    assert second.status_code==201
    replay=submit(client,h)
    assert replay.status_code==200 and replay.json['duplicate'] is True
    assert replay.json['submission']['answers']==first['answers']
    assert len(client.get('/api/assessment/history').json['visits'])==2
    assert client.get('/api/assessment').json['submission']['answers']['daily_time']=='under1'


def test_expired_invitation_is_unusable_and_nonadmins_cannot_read_mail(tmp_path):
    config={'TESTING':True,'SECRET_KEY':'fixture','DATABASE':str(tmp_path / 'tokens.sqlite3')}
    client=create_app(config).test_client(); h=login(client,'admin')
    client.post('/api/admin/invitations',json={'name':'Example','email':'expire@example.test','role':'participant','confirmed':True},headers=h)
    import re
    message=client.get('/api/admin/mail').json['messages'][0]['body']
    token=re.search(r'set-password/([A-Za-z0-9_-]+)',message).group(1)
    with sqlite3.connect(config['DATABASE']) as connection:
        connection.execute("UPDATE account_tokens SET expires='2000-01-01T00:00:00+00:00'")
    assert client.post('/api/account/password',json={'token':token,'password':'A-valid-long-password!'},headers=h).status_code==400
    login(client,'participant')
    assert client.get('/api/admin/mail').status_code==403
    login(client,'researcher')
    report=client.get('/api/research/validation').json
    assert report['report'] is None and 'pending' in report['message']
