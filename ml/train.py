"""Clean synthetic data, compare three algorithms, evaluate and save one model.

Run from the project root: python -m ml.generate_data; python -m ml.train
"""
import argparse
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix,
                             f1_score, precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

from ml.schema import (CATEGORIES, DATASET_VERSION, FEATURES, LABELS, LIMITATION,
                       MODEL_VERSION, SCHEMA_VERSION, SOURCES, TARGET, target_label)

ROOT = Path(__file__).resolve().parent


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def clean_data(raw):
    required = {'synthetic_id', 'data_source', *FEATURES, 'simulated_phq9_total', 'simulated_gad7_total'}
    if required - set(raw):
        raise ValueError(f'Missing columns: {sorted(required - set(raw))}')
    data = raw.copy()
    valid = data['data_source'].eq(DATASET_VERSION) & data['synthetic_id'].str.match(r'^SYN-\d{6,}$', na=False)
    for key, lower, upper in [('age', 13, 24), ('simulated_phq9_total', 0, 27), ('simulated_gad7_total', 0, 21)]:
        numeric = pd.to_numeric(data[key], errors='coerce')
        allowed_missing = data[key].isna() if key == 'age' else False
        valid &= allowed_missing | (numeric.between(lower, upper) & numeric.mod(1).eq(0))
        data[key] = numeric
    for key, choices in CATEGORIES.items():
        valid &= data[key].isna() | data[key].isin(choices)
    # Reject wholly unusable rows; partial missing features are imputed within folds.
    valid &= data[list(FEATURES)].notna().any(axis=1)
    valid_data = data.loc[valid].copy()
    duplicate = valid_data.duplicated('synthetic_id', keep=False)
    # Identical repeated rows are safe to deduplicate; conflicting IDs are an error.
    if valid_data.loc[duplicate].drop_duplicates().duplicated('synthetic_id').any():
        raise ValueError('Conflicting records share a synthetic participant ID.')
    cleaned = valid_data.drop_duplicates('synthetic_id').copy().reset_index(drop=True)
    cleaned['risk_class'] = [target_label(p, a) for p, a in zip(cleaned.simulated_phq9_total, cleaned.simulated_gad7_total)]
    report = {'raw_rows': len(raw), 'invalid_rows_removed': int((~valid).sum()),
              'duplicates_removed': len(valid_data) - len(cleaned), 'clean_rows': len(cleaned),
              'missing_features': {key: int(cleaned[key].isna().sum()) for key in FEATURES},
              'class_counts': {label: int(cleaned.risk_class.eq(label).sum()) for label in LABELS}}
    return cleaned, report


def preprocessing():
    return ColumnTransformer([
        ('age', Pipeline([('impute', SimpleImputer(strategy='median')),
                          ('scale', StandardScaler())]), ['age']),
        ('behaviour', Pipeline([('impute', SimpleImputer(strategy='most_frequent')),
                               ('encode', OneHotEncoder(categories=list(CATEGORIES.values()),
                                                        handle_unknown='error', sparse_output=False))]), list(CATEGORIES)),
    ], remainder='drop')


def evaluate(model, features, target):
    predicted = model.predict(features)
    probabilities = model.predict_proba(features)
    classes = list(model.classes_)
    ordered_labels = sorted(LABELS)
    auc = roc_auc_score(target, probabilities[:, [classes.index(label) for label in ordered_labels]],
                        labels=ordered_labels, multi_class='ovr', average='macro')
    matrix = confusion_matrix(target, predicted, labels=LABELS)
    specifics = {}
    for i, label in enumerate(LABELS):
        tp = matrix[i, i]
        fn = matrix[i].sum() - tp
        fp = matrix[:, i].sum() - tp
        tn = matrix.sum() - tp - fn - fp
        specifics[label] = float(tn / (tn + fp)) if tn + fp else None
    return {'sample_size': len(target), 'accuracy': float(accuracy_score(target, predicted)),
            'precision_macro': float(precision_score(target, predicted, average='macro', zero_division=0)),
            'recall_macro': float(recall_score(target, predicted, average='macro', zero_division=0)),
            'f1_macro': float(f1_score(target, predicted, average='macro', zero_division=0)),
            'roc_auc_ovr_macro': float(auc), 'specificity_ovr': specifics,
            'confusion_matrix': matrix.tolist(), 'label_order': list(LABELS),
            'class_counts': {label: int(target.eq(label).sum()) for label in LABELS},
            'per_class': classification_report(target, predicted, labels=LABELS, output_dict=True, zero_division=0)}


def train(input_path, output_dir, seed=2026):
    raw = pd.read_csv(input_path, dtype={key: str for key in CATEGORIES})
    data, cleaning = clean_data(raw)
    if len(data) < 300 or data.risk_class.value_counts().min() < 30 or data.risk_class.nunique() != 3:
        raise ValueError('Need at least 300 clean rows and 30 examples of each class.')
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    train_idx, other_idx = train_test_split(data.index, test_size=.30, stratify=data.risk_class, random_state=seed)
    val_idx, test_idx = train_test_split(other_idx, test_size=.50, stratify=data.loc[other_idx, 'risk_class'], random_state=seed + 1)
    data['split'] = ''
    for name, indices in [('train', train_idx), ('validation', val_idx), ('test', test_idx)]:
        data.loc[indices, 'split'] = name
    processed_path = output_dir / 'processed.csv'
    data.to_csv(processed_path, index=False)
    x, y = data[list(FEATURES)], data.risk_class
    candidates = [
        ('Logistic Regression', LogisticRegression(max_iter=2000, random_state=seed), {'classifier__C': [.1, 1, 10], 'classifier__class_weight': [None, 'balanced']}),
        ('Decision Tree', DecisionTreeClassifier(random_state=seed), {'classifier__max_depth': [4, 7], 'classifier__min_samples_leaf': [15, 40], 'classifier__class_weight': [None, 'balanced']}),
        ('Random Forest', RandomForestClassifier(n_estimators=120, n_jobs=1, random_state=seed), {'classifier__max_depth': [8, 12], 'classifier__min_samples_leaf': [10, 30], 'classifier__class_weight': [None, 'balanced']}),
    ]
    comparisons, fitted = [], {}
    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=seed)
    for name, classifier, grid in candidates:
        print(f'Training {name}...', flush=True)
        pipeline = Pipeline([('preprocess', preprocessing()), ('classifier', classifier)])
        search = GridSearchCV(pipeline, grid, scoring='f1_macro', cv=cv, n_jobs=1, error_score='raise')
        search.fit(x.loc[train_idx], y.loc[train_idx])
        fitted[name] = search.best_estimator_
        comparisons.append({'algorithm': name, 'best_parameters': search.best_params_,
                            'cv_f1_macro': float(search.best_score_),
                            'validation': evaluate(search.best_estimator_, x.loc[val_idx], y.loc[val_idx])})
    winner = max(comparisons, key=lambda row: row['validation']['f1_macro'])['algorithm']
    # Feature importance uses validation only; it is global association in the simulator.
    importance = permutation_importance(fitted[winner], x.loc[val_idx], y.loc[val_idx],
                                       scoring='f1_macro', n_repeats=5, random_state=seed, n_jobs=1)
    final = clone(fitted[winner])
    final_indices = np.concatenate([train_idx, val_idx])
    final.fit(x.loc[final_indices], y.loc[final_indices])
    # Only the preselected winner and a fixed baseline see held-out test data.
    metrics = evaluate(final, x.loc[test_idx], y.loc[test_idx])
    baseline = DummyClassifier(strategy='prior').fit(x.loc[final_indices], y.loc[final_indices])
    baseline_metrics = evaluate(baseline, x.loc[test_idx], y.loc[test_idx])
    report = {
        'schema_version': SCHEMA_VERSION, 'version': MODEL_VERSION, 'dataset': DATASET_VERSION,
        'available': True, 'released': False, 'synthetic': True, 'algorithm': winner,
        'evaluation_date': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'target': TARGET, 'limitations': LIMITATION, 'features': list(FEATURES), 'label_order': list(LABELS),
        'cleaning': cleaning, 'seed': seed, 'dataset_sha256': sha256(input_path),
        'processed_sha256': sha256(processed_path),
        'split': {'train': len(train_idx), 'validation': len(val_idx), 'test': len(test_idx),
                  'method': 'Stratified 70/15/15 by unique synthetic participant; train-only 3-fold tuning; validation macro-F1 selects winner; refit train+validation; one final test.'},
        'selection_metric': 'validation macro F1', 'comparisons': comparisons,
        'metrics': metrics, 'test_sample_size': len(test_idx), 'confusion_matrix': metrics['confusion_matrix'],
        'baseline': baseline_metrics,
        'feature_importance': sorted([{'feature': key, 'mean_f1_decrease': float(mean), 'std': float(std)}
                                      for key, mean, std in zip(FEATURES, importance.importances_mean, importance.importances_std)],
                                     key=lambda item: item['mean_f1_decrease'], reverse=True),
        'environment': {'python': platform.python_version(), 'scikit_learn': sklearn.__version__,
                        'numpy': np.__version__, 'pandas': pd.__version__, 'joblib': joblib.__version__},
        'sources': SOURCES,
    }
    joblib.dump({'pipeline': final, 'schema_version': SCHEMA_VERSION, 'version': MODEL_VERSION}, output_dir / 'model.joblib', compress=3)
    write_json(output_dir / 'evaluation.json', report)
    write_json(output_dir / 'manifest.json', {'model_sha256': sha256(output_dir / 'model.joblib'),
                                            'evaluation_sha256': sha256(output_dir / 'evaluation.json')})
    write_json(output_dir / 'cleaning.json', cleaning)
    pd.DataFrame({'synthetic_id': data.loc[test_idx, 'synthetic_id'], 'actual': y.loc[test_idx],
                  'predicted': final.predict(x.loc[test_idx])}).to_csv(output_dir / 'test_predictions.csv', index=False)
    lines = ['# Synthetic model evaluation', '', LIMITATION, '', f'Selected algorithm: **{winner}**.',
             '', '| Metric (held-out synthetic test) | Value |', '| --- | ---: |']
    for key in ('sample_size', 'accuracy', 'precision_macro', 'recall_macro', 'f1_macro', 'roc_auc_ovr_macro'):
        lines.append(f'| {key} | {metrics[key]:.4f} |')
    lines += ['', f'Majority baseline accuracy: {baseline_metrics["accuracy"]:.4f}.', '',
              'See evaluation.json for validation comparisons, per-class sensitivity, specificity, confusion matrix, provenance and feature importance.', '',
              'These metrics cannot test the proposal\'s real-world AUC hypothesis.']
    (output_dir / 'evaluation.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'Selected {winner}. Synthetic test accuracy={metrics["accuracy"]:.3f}, macro-F1={metrics["f1_macro"]:.3f}, AUC={metrics["roc_auc_ovr_macro"]:.3f}', flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT / 'data' / 'synthetic_raw.csv')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'artifacts')
    parser.add_argument('--seed', type=int, default=2026)
    args = parser.parse_args()
    train(args.input, args.output_dir, args.seed)


if __name__ == '__main__':
    main()
