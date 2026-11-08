"""Scientific and app integration checks for the synthetic research pipeline."""
import hashlib
import json
import shutil
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import create_app
from ml.generate_data import generate_data
from ml.schema import CATEGORIES, FEATURES, LABELS, target_label
from ml.service import DEFAULT_ARTIFACT_DIR, ModelService
from ml.train import clean_data, evaluate, preprocessing, sha256
from test_app import answers, login, submit


@pytest.fixture(scope='module')
def service():
    model = ModelService()
    assert model.pipeline is not None, model.reason
    return model


def test_synthetic_generation_is_reproducible_and_cleaning_is_real():
    first = generate_data(500, seed=17)
    pd.testing.assert_frame_equal(first, generate_data(500, seed=17))
    clean, report = clean_data(first)
    assert report['raw_rows'] == 511
    assert report['invalid_rows_removed'] == 6
    assert report['duplicates_removed'] == 5
    assert len(clean) == 500 and clean.synthetic_id.is_unique
    assert set(clean.risk_class) == set(LABELS)
    assert sum(report['missing_features'].values()) > 0


@pytest.mark.parametrize('phq,gad,expected', [(0,0,'Low'),(9,9,'Low'),(10,0,'Moderate'),
                                           (0,14,'Moderate'),(15,0,'High'),(0,15,'High'),(27,21,'High')])
def test_provisional_target_boundaries(phq, gad, expected):
    assert target_label(phq, gad) == expected


def test_conflicting_participant_ids_are_rejected():
    raw = generate_data(500)
    duplicate = raw.iloc[[10]].copy()
    duplicate['age'] = 18 if raw.iloc[10].age != 18 else 19
    with pytest.raises(ValueError, match='Conflicting'):
        clean_data(pd.concat([raw, duplicate], ignore_index=True))


def test_imputer_is_fitted_only_to_training_data():
    # A deliberately different validation age must not affect the fitted median.
    frame = pd.DataFrame([answers(age=14), answers(age=16), answers(age=18)])
    frame.loc[2, 'age'] = np.nan
    transform = preprocessing().fit(frame[list(FEATURES)])
    assert transform.named_transformers_['age'].named_steps['impute'].statistics_[0] == 15
    validation = pd.DataFrame([answers(age=24)])
    transform.transform(validation[list(FEATURES)])
    assert transform.named_transformers_['age'].named_steps['impute'].statistics_[0] == 15


def test_checked_in_metrics_and_split_provenance_match_model(service):
    report = service.status()
    artifact = DEFAULT_ARTIFACT_DIR
    data = pd.read_csv(artifact / 'processed.csv', dtype={key: str for key in CATEGORIES})
    assert data.synthetic_id.is_unique
    groups = {name: set(data.loc[data['split'].eq(name), 'synthetic_id']) for name in ('train', 'validation', 'test')}
    assert not (groups['train'] & groups['validation'] or groups['train'] & groups['test'] or groups['validation'] & groups['test'])
    for name, ids in groups.items():
        assert len(ids) == report['split'][name]
    assert sha256(artifact / 'processed.csv') == report['processed_sha256']
    assert sha256(ROOT / 'ml/data/synthetic_raw.csv') == report['dataset_sha256']
    test = data.loc[data['split'].eq('test')]
    recomputed = evaluate(service.pipeline, test[list(FEATURES)], test.risk_class)
    assert recomputed['confusion_matrix'] == report['confusion_matrix']
    for metric in ('accuracy', 'f1_macro', 'roc_auc_ovr_macro'):
        assert recomputed[metric] == pytest.approx(report['metrics'][metric])
    winner = max(report['comparisons'], key=lambda item: item['validation']['f1_macro'])
    assert winner['algorithm'] == report['algorithm']
    assert report['metrics']['sample_size'] == len(test)


def test_outcomes_identity_and_sensitive_background_are_not_predictors(service):
    original = service.predict(answers())
    extra = answers(gender='woman', education='other')
    extra.update(simulated_phq9_total=27, simulated_gad7_total=21, risk_class='High',
                 contact_details='never-use@example.com', participant_id='SHOULD-NOT-BE-USED')
    assert service.predict(extra) == original
    assert list(service.pipeline.feature_names_in_) == list(FEATURES)


@pytest.mark.parametrize('overrides', [
    {},
    {'daily_time':'under1','passive':'never','active':'often','night':'never','cyberbullying':'never','regular_count':'1'},
    {'daily_time':'5plus','passive':'always','active':'rarely','night':'always','cyberbullying':'often','regular_count':'4plus'},
])
def test_local_explanation_reconstructs_actual_model_decision(service, overrides):
    data=answers(**overrides)
    prediction=service.predict(data)
    explanation=prediction['explanation']
    assert explanation is not None
    assert explanation['selected_class']==prediction['estimate']
    assert explanation['compared_class']!=prediction['estimate']
    assert {factor['feature'] for factor in explanation['factors']}==set(FEATURES)
    assert explanation['baseline_margin']+sum(f['contribution'] for f in explanation['factors'])==pytest.approx(explanation['result_margin'])
    probabilities=prediction['probabilities']
    assert np.log(probabilities[explanation['selected_class']]/probabilities[explanation['compared_class']])==pytest.approx(explanation['result_margin'])
    for factor in explanation['factors']:
        assert factor['answer']==data[factor['feature']]
        if factor['direction']=='toward':
            assert factor['contribution']>0


def test_old_snapshot_explanation_requires_reproducing_the_saved_result(service):
    data=answers()
    saved=service.predict(data)
    old={key:value for key,value in saved.items() if key not in ('explanation','artifact_sha256')}
    assert service.explain(data,old)==saved['explanation']
    changed=dict(old,probabilities={'Low':.1,'Moderate':.2,'High':.7})
    assert service.explain(data,changed) is None
    assert service.explain(data,dict(saved,artifact_sha256='different-model')) is None
    assert service.explain(data,dict(old,source='legacy_example')) is None


def test_existing_saved_assessment_gets_explanation_without_changing_prediction(tmp_path):
    config={'TESTING':True,'SECRET_KEY':'test-key','DATABASE':str(tmp_path / 'older-result.sqlite3')}
    client=create_app(config).test_client()
    headers=login(client)
    prediction=submit(client,headers).json['submission']['prediction']
    original={key:value for key,value in prediction.items() if key not in ('explanation','artifact_sha256')}
    with sqlite3.connect(config['DATABASE']) as db:
        db.execute('UPDATE model_predictions SET result=?',(json.dumps(original),))
    record=client.get('/api/assessment').json['submission']
    assert record['prediction']==original
    assert record['explanation'] is not None
    assert record['explanation']['selected_class']==record['estimate']
    with sqlite3.connect(config['DATABASE']) as db:
        assert json.loads(db.execute('SELECT result FROM model_predictions').fetchone()[0])==original


@pytest.mark.parametrize('key,value', [('age',True),('age',25),('night',None),('night','unknown'),
                                      ('night',{'bad':True}),('regular_count',2),('daily_time',[])])
def test_missing_and_invalid_inference_inputs_abstain(service, key, value):
    prediction = service.predict(answers(**{key:value}))
    assert prediction['estimate'] is None and prediction['probabilities'] is None
    assert key in prediction['reason']


def test_missing_and_corrupt_artifacts_abstain(tmp_path):
    missing = ModelService(tmp_path)
    assert missing.status()['available'] is False
    assert missing.predict(answers())['estimate'] is None
    shutil.copytree(DEFAULT_ARTIFACT_DIR, tmp_path / 'corrupt')
    (tmp_path / 'corrupt/model.joblib').write_bytes(b'corrupted artifact')
    corrupt = ModelService(tmp_path / 'corrupt')
    assert corrupt.pipeline is None
    assert corrupt.predict(answers())['estimate'] is None


def test_incompatible_artifact_metadata_abstains_before_loading(tmp_path):
    shutil.copytree(DEFAULT_ARTIFACT_DIR, tmp_path / 'incompatible')
    directory = tmp_path / 'incompatible'
    metadata = json.loads((directory / 'evaluation.json').read_text())
    metadata['environment']['scikit_learn'] = 'incompatible-version'
    (directory / 'evaluation.json').write_text(json.dumps(metadata))
    manifest = json.loads((directory / 'manifest.json').read_text())
    manifest['evaluation_sha256'] = hashlib.sha256((directory / 'evaluation.json').read_bytes()).hexdigest()
    (directory / 'manifest.json').write_text(json.dumps(manifest))
    assert ModelService(directory).status()['available'] is False


def test_submission_survives_model_outage_and_is_not_recomputed(tmp_path):
    config = {'TESTING': True, 'SECRET_KEY': 'test-key', 'DATABASE': str(tmp_path / 'outage.sqlite3'),
              'ML_ARTIFACT_DIR': str(tmp_path / 'missing')}
    app = create_app(config)
    client = app.test_client()
    headers = login(client)
    response = submit(client, headers)
    assert response.status_code == 201
    record = response.json['submission']
    assert record['estimate'] is None and record['prediction']['source'] == 'unavailable'
    with sqlite3.connect(config['DATABASE']) as db:
        assert db.execute('SELECT count(*) FROM model_predictions').fetchone()[0] == 1
    config['ML_ARTIFACT_DIR'] = str(DEFAULT_ARTIFACT_DIR)
    restarted = create_app(config).test_client()
    login(restarted)
    assert restarted.get('/api/assessment').json['submission']['prediction'] == record['prediction']


def test_prediction_is_stable_across_reload_review_and_model_outage(tmp_path):
    config = {'TESTING': True, 'SECRET_KEY': 'test-key', 'DATABASE': str(tmp_path / 'stable.sqlite3')}
    client = create_app(config).test_client()
    headers = login(client)
    saved = submit(client, headers).json['submission']['prediction']
    assert client.get('/api/assessment').json['submission']['prediction'] == saved
    headers = login(client, 'counsellor')
    reviewed = client.post('/api/cases/D-0201/review', json={'version':1,'status':'In progress','note':'Keep prediction stable'}, headers=headers)
    assert reviewed.status_code == 200
    assert client.get('/api/cases/D-0201').json['case']['prediction'] == saved
    assert client.get('/api/cases/D-0201/report').json['report']['prediction'] == saved
    config['ML_ARTIFACT_DIR'] = str(tmp_path / 'missing')
    restarted = create_app(config).test_client()
    login(restarted)
    assert restarted.get('/api/assessment').json['submission']['prediction'] == saved


def test_existing_database_gains_prediction_table_without_changing_examples(tmp_path):
    config = {'TESTING':True,'SECRET_KEY':'test-key','DATABASE':str(tmp_path / 'existing.sqlite3')}
    create_app(config)
    with sqlite3.connect(config['DATABASE']) as db:
        db.execute('DROP TABLE model_predictions')
        original = db.execute('SELECT participant_id,estimate,answers FROM assessments ORDER BY participant_id').fetchall()
    client = create_app(config).test_client()
    login(client, 'counsellor')
    assert client.get('/api/cases/P-0142').json['case']['prediction']['source'] == 'legacy_example'
    with sqlite3.connect(config['DATABASE']) as db:
        assert db.execute('SELECT participant_id,estimate,answers FROM assessments ORDER BY participant_id').fetchall() == original


@pytest.mark.parametrize('role,status', [('participant',403),('researcher',200),('counsellor',200),('admin',200)])
def test_model_metadata_has_staff_permissions_and_no_case_data(tmp_path, role, status):
    client = create_app({'TESTING':True,'SECRET_KEY':'test-key','DATABASE':str(tmp_path / 'access.sqlite3')}).test_client()
    assert client.get('/api/model').status_code == 401
    login(client, role)
    response = client.get('/api/model')
    assert response.status_code == status
    if status == 200:
        assert response.json['model']['synthetic'] is True
        assert 'P-0142' not in response.get_data(as_text=True)
