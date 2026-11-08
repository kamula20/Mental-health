# Synthetic model evaluation

Trained and evaluated only on synthetic data. Not validated for real people, diagnosis, clinical urgency, causation or future illness. Class probabilities are outputs of a simulation, not real-world health probabilities.

Selected algorithm: **Logistic Regression**.

| Metric (held-out synthetic test) | Value |
| --- | ---: |
| sample_size | 900.0000 |
| accuracy | 0.6144 |
| precision_macro | 0.5931 |
| recall_macro | 0.5870 |
| f1_macro | 0.5868 |
| roc_auc_ovr_macro | 0.7740 |

Majority baseline accuracy: 0.4344.

See evaluation.json for validation comparisons, per-class sensitivity, specificity, confusion matrix, provenance and feature importance.

These metrics cannot test the proposal's real-world AUC hypothesis.
