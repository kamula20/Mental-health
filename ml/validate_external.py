"""Evaluate an independently labelled, consented external CSV without training.

Required columns: study_id, reference_class, age, daily_time, passive, active,
night, cyberbullying, regular_count. This produces evidence, not a clinical release.
Install requirements-ml.txt and keep private input/output in ignored storage.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ml.schema import FEATURES, LABELS, input_errors
from ml.service import ModelService
from ml.train import evaluate


def evaluate_external(path, output, description, confirmed=False):
    if not confirmed or not description.strip():
        raise ValueError('Confirm consent and provide an honest dataset/label-source description.')
    frame = pd.read_csv(path, dtype={'study_id':str, **{key:str for key in FEATURES if key != 'age'}})
    required = {'study_id', 'reference_class', *FEATURES}
    if required - set(frame.columns):
        raise ValueError('Missing external-data columns: ' + ', '.join(sorted(required - set(frame.columns))))
    if len(frame) < 30 or frame.study_id.isna().any() or not frame.study_id.is_unique:
        raise ValueError('Use at least 30 independent records with unique non-empty study IDs.')
    if frame.study_id.str.startswith('SYN-').any() or 'simulated_phq9_total' in frame or 'risk_class' in frame:
        raise ValueError('The demonstration dataset must not be passed off as an independent real-world study.')
    if set(frame.reference_class) != set(LABELS):
        raise ValueError('The reference data must include Low, Moderate and High with independently defined labels.')
    if frame.reference_class.value_counts().min() < 5:
        raise ValueError('Provide at least five independent reference examples per class; small samples still have substantial uncertainty.')
    for index, row in frame.iterrows():
        try:
            age = float(row['age'])
            if not age.is_integer():
                raise ValueError()
        except (ValueError, TypeError):
            raise ValueError(f'Invalid age in data row {index+2}.') from None
        values = {key: row[key] for key in FEATURES}
        values['age'] = int(age)
        if input_errors(values):
            raise ValueError(f'Missing or invalid feature codes in data row {index+2}.')
    model = ModelService()
    if model.pipeline is None:
        raise ValueError(model.reason)
    metrics = evaluate(model.pipeline, frame[list(FEATURES)], frame.reference_class)
    report = {'kind':'external-evaluation-1','clinical_release':False,'independent_data_declared':True,
              'dataset_description':description.strip(),'model_version':model.report['version'],
              'model_sha256':model.artifact_hash,'input_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),
              'evaluated_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'metrics':metrics,
              'limitations':'Consent and independence are operator declarations. This report does not verify recruitment, reference-label quality, institutional approval, generalisability or clinical effectiveness. No clinical release is granted.'}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    output.chmod(0o600)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('instance/external-evaluation.json'))
    parser.add_argument('--description', required=True)
    parser.add_argument('--confirm-consented-independent-data', action='store_true')
    args=parser.parse_args()
    report=evaluate_external(args.input,args.output,args.description,args.confirm_consented_independent_data)
    print('External evaluation written:',args.output)
    print('Records:',report['metrics']['sample_size'],'Clinical release:',report['clinical_release'])


if __name__=='__main__':
    main()
