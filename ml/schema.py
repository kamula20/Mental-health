"""Versioned feature and target definitions shared by training and inference."""

SCHEMA_VERSION = 'between-features-1'
MODEL_VERSION = 'synthetic-v1'
DATASET_VERSION = 'between-synthetic-1'
LABELS = ('Low', 'Moderate', 'High')
FREQUENCIES = ('never', 'rarely', 'sometimes', 'often', 'always')
CATEGORIES = {
    'daily_time': ('under1', '1to3', '3to5', '5plus'),
    'passive': FREQUENCIES,
    'active': FREQUENCIES,
    'night': FREQUENCIES,
    'cyberbullying': ('never', 'once', 'sometimes', 'often'),
    'regular_count': ('1', '2', '3', '4plus'),
}
FEATURES = ('age', *CATEGORIES)
TARGET = ('Provisional synthetic class: High if either simulated PHQ-9 or GAD-7 '
          'total is >=15; Moderate if either is 10-14 and neither is >=15; '
          'otherwise Low. This combined target is a project convention, not a validated scale.')
LIMITATION = ('Trained and evaluated only on synthetic data. Not validated for real people, '
              'diagnosis, clinical urgency, causation or future illness. Class probabilities '
              'are outputs of a simulation, not real-world health probabilities.')
SOURCES = [
    'https://www.hiv.uw.edu/go/basic-primary-care/screening-mental-disorders/core-concept/6',
    'https://www.hiv.uw.edu/page/mental-health-screening/gad-7',
    'https://scikit-learn.org/1.5/common_pitfalls.html',
    'https://scikit-learn.org/1.5/model_persistence.html',
]


def target_label(phq9, gad7):
    """Collapse simulated outcome totals; never use these totals as predictors."""
    maximum = max(phq9, gad7)
    return 'High' if maximum >= 15 else 'Moderate' if maximum >= 10 else 'Low'


def input_errors(answers):
    if not isinstance(answers, dict):
        return ['answers']
    errors = []
    age = answers.get('age')
    if type(age) is not int or not 13 <= age <= 24:
        errors.append('age')
    for key, choices in CATEGORIES.items():
        if not isinstance(answers.get(key), str) or answers[key] not in choices:
            errors.append(key)
    return errors
