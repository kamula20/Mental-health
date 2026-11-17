"""Export the trusted fitted model for inference without ML dependencies.

Run with the training requirements installed: python -m ml.export_model
"""
import argparse
import hashlib
import json
from pathlib import Path

from ml.schema import FEATURES, SCHEMA_VERSION

DEFAULT_DIRECTORY = Path(__file__).resolve().parent / 'artifacts'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export_model(directory=DEFAULT_DIRECTORY):
    import joblib
    import sklearn
    from sklearn.linear_model import LogisticRegression

    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    for filename, key in [('model.joblib', 'model_sha256'), ('evaluation.json', 'evaluation_sha256')]:
        if digest(directory / filename) != manifest[key]:
            raise ValueError(f'Integrity check failed for {filename}')
    report = json.loads((directory / 'evaluation.json').read_text(encoding='utf-8'))
    if report['environment']['scikit_learn'] != sklearn.__version__:
        raise ValueError('Export with the scikit-learn version in requirements-ml.txt.')
    # This command is for developer-controlled local artifacts, never uploads.
    bundle = joblib.load(directory / 'model.joblib')
    pipeline = bundle['pipeline']
    classifier = pipeline.named_steps['classifier']
    if (not isinstance(classifier, LogisticRegression) or classifier.solver == 'liblinear'
            or classifier.multi_class == 'ovr'):
        # A later non-linear winner must use the version-matched sklearn runtime.
        # Never leave a stale portable model paired with a newly trained model.
        (directory / 'model.json').unlink(missing_ok=True)
        manifest.pop('portable_sha256', None)
        (directory / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
        return None
    transform = pipeline.named_steps['preprocess']
    age = transform.named_transformers_['age']
    behaviour = transform.named_transformers_['behaviour']
    data = {
        'format': 'between-logistic-regression-1', 'schema_version': SCHEMA_VERSION,
        'version': bundle['version'], 'features': list(FEATURES), 'classes': classifier.classes_.tolist(),
        'model_sha256': manifest['model_sha256'], 'evaluation_sha256': manifest['evaluation_sha256'],
        'age': {'median': float(age.named_steps['impute'].statistics_[0]),
                'mean': float(age.named_steps['scale'].mean_[0]),
                'scale': float(age.named_steps['scale'].scale_[0])},
        'categories': {key: values.tolist() for key, values in zip(FEATURES[1:], behaviour.named_steps['encode'].categories_)},
        'category_modes': {key: str(value) for key, value in zip(FEATURES[1:], behaviour.named_steps['impute'].statistics_)},
        'coefficients': classifier.coef_.tolist(), 'intercepts': classifier.intercept_.tolist(),
    }
    path = directory / 'model.json'
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n', encoding='utf-8', newline='\n')
    manifest['portable_sha256'] = digest(path)
    (directory / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact-dir', type=Path, default=DEFAULT_DIRECTORY)
    args = parser.parse_args()
    output = export_model(args.artifact_dir)
    print(f'Exported {output}' if output else 'Non-linear model: use the version-matched training dependencies for inference.')


if __name__ == '__main__':
    main()
