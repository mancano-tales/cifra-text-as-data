from __future__ import annotations

import math

import pandas as pd
from sklearn.metrics import accuracy_score, cohen_kappa_score, precision_recall_fscore_support


def agreement_report(
    predicted: pd.DataFrame,
    gold: pd.DataFrame,
    id_col: str = "id",
    columns: list[str] | None = None,
) -> dict:
    """Compare LLM output against human-coded gold labels, column by column.

    Returns per-column accuracy, Cohen's kappa (chance-corrected -- a
    column where the LLM always predicts the majority class scores high on
    accuracy but low on kappa, which is exactly the failure mode worth
    catching before trusting the pipeline's output), precision/recall/F1
    per category label, and the list of mismatched rows for manual
    inspection.
    """
    merged = predicted.merge(gold, on=id_col, suffixes=("_pred", "_gold"))
    if columns is None:
        columns = [c for c in gold.columns if c != id_col]

    per_column = {}
    mismatches = []
    for col in columns:
        pred_col, gold_col = f"{col}_pred", f"{col}_gold"
        labels = sorted(set(merged[gold_col]) | set(merged[pred_col]))
        precision, recall, f1, _ = precision_recall_fscore_support(
            merged[gold_col], merged[pred_col], labels=labels, average=None, zero_division=0
        )
        kappa = cohen_kappa_score(merged[gold_col], merged[pred_col])
        if isinstance(kappa, float) and math.isnan(kappa):
            # sklearn returns nan (not an error) when there's only one label
            # in common between predicted and gold -- the exact "LLM always
            # predicts the majority class" case kappa exists to catch, so
            # this is an expected input, not a bug to raise on. `nan` isn't
            # valid JSON (json.dumps emits a bare `NaN` token that
            # JSON.parse() rejects), so it's reported as `None` instead.
            kappa = None
        per_column[col] = {
            "accuracy": accuracy_score(merged[gold_col], merged[pred_col]),
            "kappa": kappa,
            "precision": dict(zip(labels, precision)),
            "recall": dict(zip(labels, recall)),
            "f1": dict(zip(labels, f1)),
        }
        disagreements = merged[merged[pred_col] != merged[gold_col]]
        for _, row in disagreements.iterrows():
            mismatches.append(
                {
                    id_col: row[id_col],
                    "column": col,
                    "predicted": row[pred_col],
                    "gold": row[gold_col],
                }
            )

    return {"per_column": per_column, "mismatches": mismatches}
