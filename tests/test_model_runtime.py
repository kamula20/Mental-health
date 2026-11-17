"""Distribution and recovery regressions for GitHub checkouts without ML packages."""
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import create_app
from ml.schema import CATEGORIES, FEATURES
from ml.service import DEFAULT_ARTIFACT_DIR, ModelService
from test_app import answers, login, submit


def test_portable_model_matches_fitted_pipeline_on_every_cleaned_example():
    saved = joblib.load(DEFAULT_ARTIFACT_DIR / 'model.joblib')['pipeline']
    model = ModelService()
    assert model.status()['runtime'] == 'portable'
    data = pd.read_csv(DEFAULT_ARTIFACT_DIR / 'processed.csv', dtype={key: str for key in CATEGORIES})
    x = data[list(FEATURES)]
    np.testing.assert_allclose(model.pipeline.predict_proba(x), saved.predict_proba(x), rtol=1e-12, atol=1e-13)
    assert model.pipeline.predict(x) == list(saved.predict(x))


def test_predictions_and_explanations_work_without_any_site_packages():
    result = subprocess.run([sys.executable, '-S', '-m', 'ml.check'], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr + result.stdout
    assert 'Runtime: portable' in result.stdout
    assert 'Integrity, prediction and explanation: OK' in result.stdout


def test_full_assessment_works_when_ml_imports_are_blocked(tmp_path):
    # Block even installed ML modules. Flask and the Python stdlib remain usable.
    code = '''
import importlib.abc,sys,json
class NoML(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] in {'numpy','pandas','sklearn','scipy','joblib'}:
            raise ImportError('Training libraries deliberately unavailable')
sys.meta_path.insert(0,NoML())
from app import create_app
app=create_app({'TESTING':True,'SECRET_KEY':'isolated-runtime','DATABASE':sys.argv[1]})
client=app.test_client()
csrf=client.get('/api/session').json['csrf']
access=client.post('/api/study-access',json={'code':'BETWEEN-DEMO'},headers={'X-CSRF-Token':csrf})
data=json.loads(sys.argv[2])
response=client.post('/api/assessment/submit',json={'answers':data,'submission_id':'portable-runtime'},headers={'X-CSRF-Token':access.json['csrf']})
assert response.status_code==201,response.json
record=response.json['submission']
assert record['estimate'] in ('Low','Moderate','High'),record
assert record['explanation'] is not None
assert app.extensions['between_model'].status()['runtime']=='portable'
assert not any(name.split('.')[0] in {'numpy','pandas','sklearn','scipy','joblib'} for name in sys.modules)
print('Assessment result:',record['estimate'])
'''
    result = subprocess.run([sys.executable, '-c', code, str(tmp_path / 'runtime.sqlite3'), json.dumps(answers())],
                            cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr + result.stdout
    assert 'Assessment result:' in result.stdout


def test_corrupted_portable_file_fails_closed_and_explains_recovery(tmp_path):
    shutil.copytree(DEFAULT_ARTIFACT_DIR, tmp_path / 'broken')
    (tmp_path / 'broken/model.json').write_text('{}', encoding='utf-8')
    model = ModelService(tmp_path / 'broken')
    assert not model.status()['available']
    assert model.status()['error_code'] == 'invalid_artifact'
    assert model.predict(answers())['estimate'] is None
    assert 'Restore' in model.status()['reason']


def test_legacy_artifact_still_loads_with_pinned_dependencies(tmp_path):
    directory = tmp_path / 'legacy'
    shutil.copytree(DEFAULT_ARTIFACT_DIR, directory)
    manifest = json.loads((directory / 'manifest.json').read_text())
    manifest.pop('portable_sha256')
    (directory / 'manifest.json').write_text(json.dumps(manifest))
    (directory / 'model.json').unlink()
    legacy = ModelService(directory)
    assert legacy.status()['runtime'] == 'sklearn'
    portable = ModelService()
    old, new = legacy.predict(answers()), portable.predict(answers())
    assert old['estimate'] == new['estimate']
    for label in old['probabilities']:
        assert old['probabilities'][label] == pytest.approx(new['probabilities'][label], abs=1e-13)
    # Already-saved results retain their fingerprint and can receive explanations.
    assert portable.explain(answers(), old) is not None


def test_saved_missing_result_can_be_retried_once_without_resubmission(tmp_path):
    config = {'TESTING': True, 'SECRET_KEY': 'retry-test', 'DATABASE': str(tmp_path / 'recover.sqlite3'),
              'ML_ARTIFACT_DIR': str(tmp_path / 'missing')}
    client = create_app(config).test_client()
    headers = login(client)
    original = submit(client, headers).json['submission']
    assert original['estimate'] is None
    outage = client.post('/api/assessment/result', json={}, headers=headers)
    assert outage.status_code == 503
    assert client.get('/api/assessment').json['submission']['estimate'] is None
    config['ML_ARTIFACT_DIR'] = str(DEFAULT_ARTIFACT_DIR)
    recovered = create_app(config).test_client()
    headers = login(recovered)
    # GET does not silently rescore saved records.
    assert recovered.get('/api/assessment').json['submission']['estimate'] is None
    result = recovered.post('/api/assessment/result', json={}, headers=headers)
    assert result.status_code == 200 and result.json['duplicate'] is False
    saved = result.json['submission']
    assert saved['estimate'] in ('Low', 'Moderate', 'High')
    assert saved['answers'] == original['answers'] and saved['submitted_at'] == original['submitted_at']
    assert saved['review_state'] == original['review_state'] and saved['version'] == original['version'] + 1
    repeated = recovered.post('/api/assessment/result', json={}, headers=headers)
    assert repeated.json['duplicate'] is True and repeated.json['submission']['prediction'] == saved['prediction']
    with sqlite3.connect(config['DATABASE']) as connection:
        assert connection.execute('SELECT count(*) FROM assessments WHERE user_id=?', ('participant',)).fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM audit WHERE action='Calculated previously unavailable model result'").fetchone()[0] == 1


def test_calculation_preserves_existing_prediction_and_access_controls(tmp_path):
    config = {'TESTING': True, 'SECRET_KEY': 'access-test', 'DATABASE': str(tmp_path / 'access.sqlite3')}
    client = create_app(config).test_client()
    csrf = client.get('/api/session').json['csrf']
    assert client.post('/api/assessment/result', json={}, headers={'X-CSRF-Token':csrf}).status_code == 401
    headers = login(client)
    assert client.post('/api/assessment/result', json={}, headers=headers).status_code == 404
    original = submit(client, headers).json['submission']
    assert client.post('/api/assessment/result', json={}).status_code == 403
    result = client.post('/api/assessment/result', json={}, headers=headers)
    assert result.json['submission']['prediction'] == original['prediction']
    assert result.json['submission']['version'] == original['version']
    client.post('/api/privacy/requests', json={'kind':'withdraw','confirmed':True}, headers=headers)
    assert client.post('/api/assessment/result', json={}, headers=headers).status_code == 409
    headers = login(client, 'researcher')
    assert client.post('/api/assessment/result', json={}, headers=headers).status_code == 403


def test_retry_rejects_corrupt_saved_answers_and_unsupported_questionnaire(tmp_path):
    config = {'TESTING':True,'SECRET_KEY':'version-test','DATABASE':str(tmp_path / 'version.sqlite3'),
              'ML_ARTIFACT_DIR':str(tmp_path / 'missing')}
    client = create_app(config).test_client()
    headers = login(client)
    submit(client,headers)
    with sqlite3.connect(config['DATABASE']) as connection:
        connection.execute("UPDATE assessments SET questionnaire_version='unsupported'")
    assert client.post('/api/assessment/result',json={},headers=headers).status_code == 409
    with sqlite3.connect(config['DATABASE']) as connection:
        data=answers(); data.pop('night')
        connection.execute('UPDATE assessments SET questionnaire_version=?,answers=?',('behaviour-demo-1',json.dumps(data)))
    assert client.post('/api/assessment/result',json={},headers=headers).status_code == 409
