# Experiment protocol

## Classification

Baseline: word unigram/bigram TF-IDF with logistic regression. Improved semantic experiment: a supervised logistic-regression classifier over locally computed Sentence Transformer embeddings. The embedding model directory is supplied by the operator and loaded with network access disabled. Both experiments use seed 42 by default. The synthetic generator uses scenario-group holdout to keep the two phrasings of a scenario on the same side of the split. Institution-labeled data uses a stratified random holdout and requires an institution-specific leakage review.

Report accuracy, macro precision, macro recall, macro F1, and the confusion matrix. Record the dataset type, row counts, seed, software version, model version, and feature configuration. Do not compare scores across different data versions as if they shared one test set.

## Duplicate retrieval

The API provides TF-IDF cosine-similarity candidate retrieval. When a local sentence model and FAISS CPU are installed, it uses normalized embeddings and an in-memory index rebuilt from the current authorized database records. `scripts/evaluate_duplicate_retrieval.py` evaluates a human-labeled candidate-pair CSV and reports precision@K, recall@K, and thresholded F1. The candidate list is advisory and never merges requests.

## Resolution time

The deployed fallback is the historical category median when at least ten resolved cases are available. The Random Forest experiment requires twenty institutionally resolved rows, uses category/department/priority features, seed 42, and a held-out 20% test partition. Report MAE, RMSE, and R² beside the median baseline. Persist experiment configuration and measured metrics. An estimate is not a deadline.

## Workflow analysis

Export only authorized request event logs. PM4Py discovers a directly-follows graph and performance edge gaps. The API also reports event variants and inter-event gaps directly from live records. Interpret bottleneck signals with case context; observed timing does not establish cause.

## Reproducibility

Run scripts from `backend/` in the pinned environment. Keep generated models under ignored `.models/`; keep dataset provenance, metrics, and configuration files in `research/`. The code writes measured metrics; it does not write claimed improvements. A research claim requires a predeclared comparison, sufficient labeled data, repeated or justified split procedure, and observed results.
