"""Versioned PHQ-9/GAD-7 administration and deterministic screening scores.

Developed by Spitzer, Williams, Kroenke and colleagues with Pfizer support.
PHQ/GAD materials state no permission is required to reproduce/display/distribute.
Sources: https://uwhatc.uw.edu/wp-content/uploads/2022/07/PHQ9-English-1.pdf
https://www.hiv.uw.edu/page/mental-health-screening/gad-7
WEMWBS wording is intentionally not distributed: a separate Warwick licence is needed.
"""
VERSION = 'wellbeing-1'
OPTIONS = ('Not at all', 'Several days', 'More than half the days', 'Nearly every day')
DIFFICULTY = ('Not difficult at all', 'Somewhat difficult', 'Very difficult', 'Extremely difficult')
DEFINITIONS = {
    'phq9': {'name': 'PHQ-9', 'title': 'How you have been feeling', 'maximum': 27,
             'source': 'https://uwhatc.uw.edu/wp-content/uploads/2022/07/PHQ9-English-1.pdf',
             'items': [
                 'Little interest or pleasure in doing things',
                 'Feeling down, depressed, or hopeless',
                 'Trouble falling or staying asleep, or sleeping too much',
                 'Feeling tired or having little energy',
                 'Poor appetite or overeating',
                 'Feeling bad about yourself — or that you are a failure or have let yourself or your family down',
                 'Trouble concentrating on things, such as reading the newspaper or watching television',
                 'Moving or speaking so slowly that other people could have noticed? Or the opposite — being so fidgety or restless that you have been moving around a lot more than usual',
                 'Thoughts that you would be better off dead or of hurting yourself in some way',
             ]},
    'gad7': {'name': 'GAD-7', 'title': 'Worry and anxiety', 'maximum': 21,
             'source': 'https://www.hiv.uw.edu/page/mental-health-screening/gad-7',
             'items': [
                 'Feeling nervous, anxious or on edge',
                 'Not being able to stop or control worrying',
                 'Worrying too much about different things',
                 'Trouble relaxing',
                 'Being so restless that it is hard to sit still',
                 'Becoming easily annoyed or irritable',
                 'Feeling afraid as if something awful might happen',
             ]},
}


def validate(answers, complete=False):
    errors = {}
    opted = answers.get('wellbeing_opt_in', False)
    if type(opted) is not bool:
        errors['wellbeing_opt_in'] = 'Choose whether to answer the wellbeing questions.'
    for key, definition in DEFINITIONS.items():
        values = answers.get(key)
        if values is None and not (complete and opted):
            continue
        if not opted:
            errors[key] = 'Choose to answer the wellbeing questions, or remove these responses.'
            continue
        if (not isinstance(values, list) or len(values) != len(definition['items'])
                or any(v is not None and (type(v) is not int or not 0 <= v <= 3) for v in values)
                or complete and any(v is None for v in values)):
            errors[key] = 'Answer every question, or choose to skip the wellbeing questions.'
        difficulty = answers.get(key + '_difficulty')
        if difficulty is not None and (type(difficulty) is not int or not 0 <= difficulty <= 3):
            errors[key + '_difficulty'] = 'Choose one of the listed difficulty answers.'
        if complete and isinstance(values, list) and any(type(v) is int and v > 0 for v in values) and difficulty is None:
            errors[key + '_difficulty'] = 'Tell us how much these experiences affected your day-to-day life.'
    return errors


def score(answers):
    result = []
    for key, definition in DEFINITIONS.items():
        values = answers.get(key)
        valid = answers.get('wellbeing_opt_in') is True and isinstance(values, list) and len(values) == len(definition['items']) and all(type(v) is int and 0 <= v <= 3 for v in values)
        total = sum(values) if valid else None
        band = None
        if total is not None:
            band = 'Severe' if total >= (20 if key == 'phq9' else 15) else 'Moderately severe' if key == 'phq9' and total >= 15 else 'Moderate' if total >= 10 else 'Mild' if total >= 5 else 'Minimal'
        result.append({'name': definition['name'], 'key': key, 'title': definition['title'],
                       'status': 'Completed' if valid else 'Not administered', 'score': total,
                       'maximum': definition['maximum'], 'band': band, 'version': VERSION,
                       'difficulty': answers.get(key + '_difficulty') if valid else None,
                       'source': definition['source']})
    result.append({'name': 'WEMWBS', 'key': 'wemwbs', 'title': 'Mental wellbeing', 'status': 'Not administered',
                   'score': None, 'maximum': 70, 'band': None, 'version': None,
                   'source': 'https://warwick.ac.uk/services/innovations/wemwbs/licenses/'})
    return result


def needs_direct_checkin(answers):
    values = answers.get('phq9')
    return answers.get('wellbeing_opt_in') is True and isinstance(values, list) and len(values) == 9 and type(values[8]) is int and values[8] > 0
