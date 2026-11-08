"""Generate fictional participants, stochastic outcomes, and cleaning examples.

No real records, published population estimates, or clinical questionnaire items are
used. Coefficients below are deliberately invented simulation assumptions.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from ml.schema import CATEGORIES, DATASET_VERSION, target_label

DEFAULT_OUTPUT = Path(__file__).resolve().parent / 'data' / 'synthetic_raw.csv'


def generate_data(samples=6000, seed=2026):
    if samples < 300:
        raise ValueError('Use at least 300 simulated participants for stratified evaluation.')
    rng = np.random.default_rng(seed)
    intensity = rng.normal(0, 1, samples)
    daily = np.digitize(intensity + rng.normal(0, .55, samples), [-.9, .1, 1.05])
    passive = np.clip(np.rint(2 + .8 * intensity + rng.normal(0, 1, samples)), 0, 4).astype(int)
    active = np.clip(np.rint(2 + .3 * intensity + rng.normal(0, 1.2, samples)), 0, 4).astype(int)
    night = np.clip(np.rint(1.6 + .9 * intensity + rng.normal(0, 1, samples)), 0, 4).astype(int)
    bullying = rng.choice(4, samples, p=[.62, .21, .12, .05])
    count = np.clip(np.rint(1.4 + .6 * intensity + rng.normal(0, .9, samples)), 0, 3).astype(int)
    age = rng.integers(13, 25, samples)

    # Unobserved context and independent outcome noise ensure habits do not fully
    # determine a label. These are not fitted clinical or Kenyan population effects.
    context = rng.normal(0, .85, samples)
    latent = (-2.05 + .40 * daily + .22 * passive + .35 * night + .58 * bullying
              + .10 * count - .12 * active + .20 * (daily >= 2) * (night >= 3) + context)
    depression_p = 1 / (1 + np.exp(-(latent + rng.normal(0, .3, samples))))
    anxiety_p = 1 / (1 + np.exp(-(latent + .1 + rng.normal(0, .45, samples))))
    phq9 = rng.binomial(27, depression_p)
    gad7 = rng.binomial(21, anxiety_p)
    data = pd.DataFrame({
        'synthetic_id': [f'SYN-{i:06d}' for i in range(samples)],
        'data_source': DATASET_VERSION,
        'age': age,
        'gender': rng.choice(['woman', 'man', 'nonbinary', 'other', 'prefer_not'], samples),
        'education': np.where(age < 18, 'secondary', rng.choice(['college', 'university', 'other'], samples)),
        'simulated_phq9_total': phq9,
        'simulated_gad7_total': gad7,
    })
    for (key, choices), indices in zip(CATEGORIES.items(), [daily, passive, active, night, bullying, count]):
        data[key] = np.array(choices)[indices]
    data['risk_class'] = [target_label(p, a) for p, a in zip(phq9, gad7)]
    # Missingness is introduced after outcomes, independently of their class.
    for key in ('age', *CATEGORIES):
        data.loc[rng.random(samples) < .025, key] = np.nan
    duplicates = data.sample(n=max(1, samples // 100), random_state=seed).copy()
    invalid = data.iloc[:6].copy()
    invalid['synthetic_id'] = [f'SYN-{samples + i:06d}' for i in range(6)]
    invalid.loc[invalid.index[:2], 'age'] = 99
    invalid.loc[invalid.index[2:4], 'night'] = 'invalid-code'
    invalid.loc[invalid.index[4:], 'simulated_phq9_total'] = 80
    return pd.concat([data, duplicates, invalid], ignore_index=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', type=int, default=6000)
    parser.add_argument('--seed', type=int, default=2026)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    data = generate_data(args.samples, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(args.output, index=False)
    print(f'Wrote {len(data)} synthetic rows to {args.output}')


if __name__ == '__main__':
    main()
