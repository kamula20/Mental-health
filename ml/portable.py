"""Standard-library inference for an exported, fitted Logistic Regression model.

This evaluates the original preprocessing and learned weights; it is not a rule
based replacement or a newly trained model. No pickle or ML libraries are loaded.
"""
import math

from ml.schema import CATEGORIES, FEATURES, LABELS, SCHEMA_VERSION


class PortableModel:
    def __init__(self, data, report, model_hash, evaluation_hash):
        if (data['format'] != 'between-logistic-regression-1'
                or data['schema_version'] != SCHEMA_VERSION
                or data['features'] != list(FEATURES)
                or data['version'] != report['version']
                or data['model_sha256'] != model_hash
                or data['evaluation_sha256'] != evaluation_hash
                or report['algorithm'] != 'Logistic Regression'):
            raise ValueError('Portable model provenance or schema mismatch')
        self.classes_ = tuple(data['classes'])
        self.feature_names_in_ = FEATURES
        if set(self.classes_) != set(LABELS) or len(self.classes_) != len(LABELS):
            raise ValueError('Unexpected portable model classes')
        self.age = data['age']
        self.categories = data['categories']
        self.modes = data['category_modes']
        if set(self.categories) != set(CATEGORIES) or set(self.modes) != set(CATEGORIES):
            raise ValueError('Invalid categorical preprocessing')
        for key, values in CATEGORIES.items():
            if self.categories[key] != list(values) or self.modes[key] not in values:
                raise ValueError('Portable model category mismatch')
        self.weights, self.intercepts = data['coefficients'], data['intercepts']
        width = 1 + sum(len(values) for values in CATEGORIES.values())
        if (len(self.weights) != len(LABELS) or len(self.intercepts) != len(LABELS)
                or any(len(row) != width for row in self.weights)):
            raise ValueError('Invalid portable model dimensions')
        numbers = [*self.intercepts, *[value for row in self.weights for value in row],
                   self.age['median'], self.age['mean'], self.age['scale']]
        if any(type(n) not in (int, float) or not math.isfinite(n) for n in numbers) or self.age['scale'] <= 0:
            raise ValueError('Invalid portable model coefficients')

    @staticmethod
    def missing(value):
        return value is None or isinstance(value, float) and math.isnan(value)

    def encode(self, answers):
        age = answers.get('age')
        age = self.age['median'] if self.missing(age) else float(age)
        values = [(age - self.age['mean']) / self.age['scale']]
        for key in CATEGORIES:
            answer = answers.get(key)
            answer = self.modes[key] if self.missing(answer) else answer
            if answer not in self.categories[key]:
                raise ValueError('Unknown model category')
            values.extend(float(answer == category) for category in self.categories[key])
        return values

    def predict_proba(self, rows):
        # The optional dataframe path supports offline evaluation, without importing
        # pandas in the application runtime.
        if hasattr(rows, 'to_dict'):
            rows = rows.to_dict(orient='records')
        result = []
        for row in rows:
            encoded = self.encode(row)
            scores = [bias + sum(w * x for w, x in zip(weights, encoded))
                      for bias, weights in zip(self.intercepts, self.weights)]
            highest = max(scores)
            exps = [math.exp(score - highest) for score in scores]
            total = sum(exps)
            result.append([value / total for value in exps])
        return result

    def predict(self, rows):
        return [self.classes_[max(range(len(row)), key=row.__getitem__)] for row in self.predict_proba(rows)]

    def explain(self, answers, selected, other):
        reference = {'age': self.age['median'], **self.modes}
        encoded, baseline = self.encode(answers), self.encode(reference)
        chosen, compared = self.classes_.index(selected), self.classes_.index(other)
        weights = [a - b for a, b in zip(self.weights[chosen], self.weights[compared])]
        intercept = self.intercepts[chosen] - self.intercepts[compared]
        factors, offset = [], 0
        for key, width in zip(FEATURES, [1, *[len(values) for values in CATEGORIES.values()]]):
            effect = sum(weights[i] * (encoded[i] - baseline[i]) for i in range(offset, offset + width))
            factors.append({'feature': key, 'answer': answers[key], 'reference_answer': reference[key],
                            'contribution': effect,
                            'direction': 'toward' if effect > 1e-8 else 'away' if effect < -1e-8 else 'unchanged'})
            offset += width
        return {'method': 'linear_reference_contrast_v1', 'selected_class': selected,
                'compared_class': other, 'reference': 'Training median age and most common behaviour answers',
                'baseline_margin': intercept + sum(w * x for w, x in zip(weights, baseline)),
                'result_margin': intercept + sum(w * x for w, x in zip(weights, encoded)),
                'factors': sorted(factors, key=lambda item: item['contribution'], reverse=True),
                'limitation': 'These contributions explain this model relative to its training reference, not causes of a mental-health condition.'}
