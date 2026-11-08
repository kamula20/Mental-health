"""Export shareable figures from stored synthetic model evaluation.

Optional dependency: matplotlib. Run: python tools/plot_ml_evaluation.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import ConfusionMatrixDisplay, roc_curve, auc

from ml.schema import CATEGORIES, FEATURES, LABELS
from ml.service import DEFAULT_ARTIFACT_DIR, ModelService


def main():
    model = ModelService()
    if model.pipeline is None:
        raise RuntimeError(model.reason)
    report = model.status()
    out = DEFAULT_ARTIFACT_DIR / 'figures'
    out.mkdir(exist_ok=True)
    plt.rcParams.update({'font.size': 11, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, ax = plt.subplots(figsize=(7, 6), constrained_layout=True)
    ConfusionMatrixDisplay(np.array(report['confusion_matrix']), display_labels=LABELS).plot(ax=ax, cmap='Blues', colorbar=False)
    ax.set_title(f'Synthetic test data only (n={report["test_sample_size"]})\n{report["algorithm"]} confusion matrix')
    fig.savefig(out / 'confusion_matrix.png', dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5), constrained_layout=True)
    names = [item['algorithm'] for item in report['comparisons']]
    scores = [item['validation']['f1_macro'] for item in report['comparisons']]
    bars = ax.bar(names, scores, color=['#486d81', '#78a0a3', '#b38d67'])
    ax.bar_label(bars, labels=[f'{score:.3f}' for score in scores], padding=4)
    ax.set(ylim=(0, 1), ylabel='Macro F1', title='Synthetic validation data only\nAlgorithm comparison (not real-world performance)')
    fig.savefig(out / 'algorithm_comparison.png', dpi=180)
    plt.close(fig)

    data = pd.read_csv(DEFAULT_ARTIFACT_DIR / 'processed.csv', dtype={key: str for key in CATEGORIES})
    test = data.loc[data['split'].eq('test')]
    probabilities = model.pipeline.predict_proba(test[list(FEATURES)])
    fig, ax = plt.subplots(figsize=(7, 6), constrained_layout=True)
    for label, color in zip(LABELS, ['#486d81', '#b38d67', '#935b69']):
        index = list(model.pipeline.classes_).index(label)
        fpr, tpr, _ = roc_curve(test.risk_class.eq(label), probabilities[:, index])
        ax.plot(fpr, tpr, color=color, label=f'{label} vs rest (AUC {auc(fpr,tpr):.3f})')
    ax.plot([0, 1], [0, 1], '--', color='gray', label='Chance')
    ax.set(xlim=(0, 1), ylim=(0, 1), xlabel='False positive rate', ylabel='True positive rate',
           title='Synthetic test data only\nOne-vs-rest ROC curves')
    ax.legend(loc='lower right')
    fig.savefig(out / 'roc_curves.png', dpi=180)
    plt.close(fig)
    print(f'Saved synthetic evaluation figures in {out}')


if __name__ == '__main__':
    main()
