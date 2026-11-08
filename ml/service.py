"""Load a trusted local artifact once; unavailable ML never prevents saving answers."""
import hashlib
import json
import logging
import math
import warnings
from pathlib import Path

from ml.schema import FEATURES, LABELS, LIMITATION, SCHEMA_VERSION, input_errors

DEFAULT_ARTIFACT_DIR = Path(__file__).resolve().parent / 'artifacts'
logger = logging.getLogger(__name__)


class ModelService:
    def __init__(self, artifact_dir=DEFAULT_ARTIFACT_DIR):
        self.pipeline = None
        self.report = None
        self.reason = 'Synthetic model unavailable. Install ML requirements, train the model and restart the app.'
        try:
            import joblib
            import pandas as pd
            import sklearn
            from sklearn.exceptions import InconsistentVersionWarning

            directory = Path(artifact_dir)
            manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
            for filename, key in [('model.joblib', 'model_sha256'), ('evaluation.json', 'evaluation_sha256')]:
                if hashlib.sha256((directory / filename).read_bytes()).hexdigest() != manifest[key]:
                    raise ValueError('Artifact integrity check failed')
            report = json.loads((directory / 'evaluation.json').read_text(encoding='utf-8'))
            if (report['schema_version'] != SCHEMA_VERSION or report['features'] != list(FEATURES)
                    or report['environment']['scikit_learn'] != sklearn.__version__
                    or report['synthetic'] is not True or report['released'] is not False):
                raise ValueError('Incompatible model metadata')
            # joblib is pickle-based: load only developer-controlled local artifacts.
            # A checksum detects accidental corruption; it is not an authenticity proof.
            with warnings.catch_warnings():
                warnings.simplefilter('error', InconsistentVersionWarning)
                bundle = joblib.load(directory / 'model.joblib')
            if bundle['schema_version'] != SCHEMA_VERSION or bundle['version'] != report['version']:
                raise ValueError('Model/report version mismatch')
            pipeline = bundle['pipeline']
            if set(pipeline.classes_) != set(LABELS):
                raise ValueError('Unexpected model classes')
            self.pipeline, self.report, self.frame = pipeline, report, pd.DataFrame
            self.artifact_hash = manifest['model_sha256']
            self.reason = None
        except Exception as error:
            # Do not log answers or patient identifiers. Loading must fail closed.
            logger.warning('Synthetic ML unavailable (%s).', type(error).__name__)

    def status(self):
        if self.report:
            return self.report
        return {'available': False, 'released': False, 'synthetic': True, 'version': None,
                'dataset': None, 'target': None, 'evaluation_date': None,
                'test_sample_size': None, 'metrics': None, 'confusion_matrix': None,
                'reason': self.reason, 'limitations': LIMITATION}

    def predict(self, answers):
        result = {'estimate': None, 'model_version': None, 'probabilities': None,
                  'source': 'unavailable', 'synthetic': True, 'limitations': LIMITATION,
                  'reason': self.reason, 'explanation': None}
        errors = input_errors(answers)
        if errors:
            result['reason'] = 'Missing or invalid model inputs: ' + ', '.join(errors) + '.'
            return result
        if self.pipeline is None:
            return result
        try:
            frame = self.frame([{key: answers[key] for key in FEATURES}], columns=FEATURES)
            vector = self.pipeline.predict_proba(frame)[0]
            probabilities = {str(label): float(value) for label, value in zip(self.pipeline.classes_, vector)}
            if (any(not math.isfinite(value) or not 0 <= value <= 1 for value in probabilities.values())
                    or not math.isclose(sum(probabilities.values()), 1, abs_tol=1e-6)):
                raise ValueError('Invalid model probabilities')
            result.update(estimate=max(probabilities, key=probabilities.get),
                          model_version=self.report['version'], probabilities=probabilities,
                          source='synthetic_model', reason=None, artifact_sha256=self.artifact_hash)
            result['explanation'] = self.explain(answers, result)
        except Exception as error:
            logger.warning('Synthetic ML prediction unavailable (%s).', type(error).__name__)
            result['reason'] = 'The synthetic model could not process this assessment.'
        return result

    def explain(self, answers, prediction):
        """Exact linear contributions relative to a training-derived reference.

        Contrast the selected class with its runner-up. Group encoded columns back
        to original answers. This explains the fitted classifier, not health causes.
        Older snapshots are explainable only if their full probabilities reproduce.
        Unsupported/replaced models receive no invented explanation.
        """
        if (self.pipeline is None or input_errors(answers)
                or prediction.get('source') != 'synthetic_model'
                or prediction.get('model_version') != self.report['version']
                or prediction.get('artifact_sha256', self.artifact_hash) != self.artifact_hash):
            return None
        try:
            import numpy as np

            classifier = self.pipeline.named_steps['classifier']
            if not hasattr(classifier, 'coef_') or classifier.coef_.shape[0] != len(LABELS):
                return None
            frame = self.frame([{key: answers[key] for key in FEATURES}], columns=FEATURES)
            classes = list(self.pipeline.classes_)
            actual = self.pipeline.predict_proba(frame)[0]
            saved = prediction.get('probabilities') or {}
            if set(saved) != set(classes) or any(not math.isclose(float(saved[label]), float(value), rel_tol=1e-9, abs_tol=1e-10)
                                                 for label, value in zip(classes, actual)):
                return None
            selected = prediction['estimate']
            if selected != classes[int(np.argmax(actual))]:
                return None
            other = max((label for label in classes if label != selected), key=saved.get)
            transform = self.pipeline.named_steps['preprocess']
            age_imputer = transform.named_transformers_['age'].named_steps['impute']
            behaviour = transform.named_transformers_['behaviour']
            categories = behaviour.named_steps['encode'].categories_
            modes = behaviour.named_steps['impute'].statistics_
            reference = {'age': float(age_imputer.statistics_[0]),
                         **{key: str(value) for key, value in zip(FEATURES[1:], modes)}}
            baseline = self.frame([reference], columns=FEATURES)
            encoded = np.asarray(transform.transform(frame))[0]
            reference_encoded = np.asarray(transform.transform(baseline))[0]
            weights = classifier.coef_[classes.index(selected)] - classifier.coef_[classes.index(other)]
            contributions = weights * (encoded - reference_encoded)
            factors, offset = [], 0
            for key, width in zip(FEATURES, [1, *[len(values) for values in categories]]):
                effect = float(contributions[offset:offset + width].sum())
                factors.append({'feature': key, 'answer': answers[key], 'reference_answer': reference[key],
                                'contribution': effect, 'direction': 'toward' if effect > 1e-8 else 'away' if effect < -1e-8 else 'unchanged'})
                offset += width
            if offset != len(contributions):
                return None
            intercept = float(classifier.intercept_[classes.index(selected)] - classifier.intercept_[classes.index(other)])
            baseline_margin = float(intercept + weights @ reference_encoded)
            return {'method': 'linear_reference_contrast_v1', 'selected_class': selected,
                    'compared_class': other, 'reference': 'Training median age and most common behaviour answers',
                    'baseline_margin': baseline_margin, 'result_margin': float(intercept + weights @ encoded),
                    'factors': sorted(factors, key=lambda item: item['contribution'], reverse=True),
                    'limitation': 'These contributions explain this model relative to its training reference, not causes of a mental-health condition.'}
        except Exception as error:
            logger.warning('Model explanation unavailable (%s).', type(error).__name__)
            return None
