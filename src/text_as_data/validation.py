from __future__ import annotations

import pandas as pd
from sklearn.metrics import accuracy_score, cohen_kappa_score


def agreement_report(
    predicted: pd.DataFrame,
    gold: pd.DataFrame,
    id_col: str = "id",
    columns: list[str] | None = None,
) -> dict:
    """Compare LLM output against human-coded gold labels, column by column.

    Returns per-column accuracy and Cohen's kappa (chance-corrected — a
    column where the LLM always predicts the majority class scores high on
    accuracy but low on kappa, which is exactly the failure mode worth
    catching before trusting the pipeline's output) plus the list of
    mismatched rows for manual inspection.
    """
    merged = predicted.merge(gold, on=id_col, suffixes=("_pred", "_gold"))
    if columns is None:
        columns = [c for c in gold.columns if c != id_col]

    per_column = {}
    mismatches = []
    for col in columns:
        pred_col, gold_col = f"{col}_pred", f"{col}_gold"
        per_column[col] = {
            "accuracy": accuracy_score(merged[gold_col], merged[pred_col]),
            "kappa": cohen_kappa_score(merged[gold_col], merged[pred_col]),
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
