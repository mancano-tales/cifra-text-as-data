# Slice 4 — Validation Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a researcher upload hand-reviewed gold labels for a run and see a validation report (per-category accuracy/kappa/precision/recall/F1 plus a disagreement list), closing the last unbuilt screen from `AGENTS.md`'s original MVP list.

**Architecture:** `validation.py` gains precision/recall/F1 per category (task 1, unblocked). Two new endpoints — `POST /runs/{id}/gold-labels` (CSV upload) and `GET /runs/{id}/validation` (the report) — write to and read from `HumanLabelRecord`, a table a peer Claude Code session is landing in parallel as part of QualiLab interop (tasks 2-3 are **blocked** on that landing; see the note at the start of Task 2). Frontend adds a "Validate" section to the existing `ResultsTable.tsx`, following the same list+detail conventions as every prior slice.

**Tech Stack:** Same as Slices 1-3 — FastAPI, SQLModel, `scikit-learn` (already a dependency), pytest; React, TypeScript.

**Design spec:** `docs/superpowers/specs/2026-09-02-slice-4-validation-screen-design.md` — read it first, especially "Why this scope, and the cross-session dependency" and "Gold-label CSV format."

---

## Before you start

Read, in order:
1. `text-as-data/docs/superpowers/specs/2026-09-02-slice-4-validation-screen-design.md` — this slice's design.
2. `text-as-data/docs/superpowers/specs/2026-09-02-qualilab-interop-design.md` § "Data model changes" — the `HumanLabelRecord` shape this plan is written against. **Before starting Task 2, check `src/text_as_data/db.py` for the actual, currently-landed class** — if a peer session's implementation differs from what's quoted there (field names, types), adapt Tasks 2-3 to match the real thing, not this document.
3. `text-as-data/src/text_as_data/app.py` (current `PUT /runs/{run_id}/results/{extraction_id}` and `GET /runs/{run_id}/results`) and `frontend/src/ResultsTable.tsx` — the exact patterns Tasks 2-6 extend.

---

## File Structure

- `src/text_as_data/validation.py` — **modify**: precision/recall/F1 in `agreement_report()`.
- `tests/test_pipeline.py` — **modify**: new test for the metric addition.
- `src/text_as_data/app.py` — **modify**: `POST /runs/{id}/gold-labels`, `GET /runs/{id}/validation`.
- `tests/test_app_validation.py` — **create**.
- `frontend/src/api.ts` — **modify**: gold-label upload + validation-report client functions.
- `frontend/src/ValidationPanel.tsx` — **create**: upload form / report display, composed into `ResultsTable.tsx`.
- `frontend/src/ResultsTable.tsx` — **modify**: render `ValidationPanel`.
- `frontend/src/locales/en.json`, `frontend/src/locales/pt-BR.json` — **modify**: `validation.*` keys.
- `TODO.md`, `NEWS.md` — **modify**: close out the slice.

---

## Task 1: `agreement_report()` — precision/recall/F1 per category (unblocked, start here)

**Files:**
- Modify: `src/text_as_data/validation.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_pipeline.py` (it already imports `agreement_report` and `pytest` — check the top of the file before adding a duplicate import):

```python
def test_agreement_report_includes_precision_recall_f1_per_category():
    predicted = pd.DataFrame(
        {"id": [1, 2, 3, 4], "categoria": ["protest", "protest", "not_protest", "protest"]}
    )
    gold = pd.DataFrame(
        {"id": [1, 2, 3, 4], "categoria": ["protest", "not_protest", "not_protest", "protest"]}
    )

    report = agreement_report(predicted, gold)

    metrics = report["per_column"]["categoria"]
    assert set(metrics["precision"].keys()) == {"protest", "not_protest"}
    # 3 rows predicted "protest" (1, 2, 4); 2 of those are actually gold "protest" (1, 4) -> 2/3
    assert metrics["precision"]["protest"] == pytest.approx(2 / 3)
    # 2 rows are actually gold "protest" (1, 4); both predicted correctly -> 2/2
    assert metrics["recall"]["protest"] == pytest.approx(1.0)
    assert "f1" in metrics
    assert metrics["f1"]["protest"] == pytest.approx(0.8)  # 2*P*R/(P+R) = 2*(2/3)*1/(2/3+1)
```

Check whether `tests/test_pipeline.py` already imports `pandas as pd` at the top — if not, add `import pandas as pd` alongside the existing imports.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline.py::test_agreement_report_includes_precision_recall_f1_per_category -v`
Expected: FAIL with `KeyError: 'precision'`

- [ ] **Step 3: Implement**

Replace the full contents of `src/text_as_data/validation.py`:

```python
from __future__ import annotations

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
        per_column[col] = {
            "accuracy": accuracy_score(merged[gold_col], merged[pred_col]),
            "kappa": cohen_kappa_score(merged[gold_col], merged[pred_col]),
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline.py -v`
Expected: all pass (both the new test and the pre-existing `test_agreement_report_flags_mismatches`, which only checks `accuracy` and isn't affected by the new keys)

- [ ] **Step 5: Run the full suite**

Run: `pytest -v`
Expected: all pass — this only adds keys to a returned dict, nothing removed.

- [ ] **Step 6: Commit**

```bash
git add src/text_as_data/validation.py tests/test_pipeline.py
git commit -m "feat: add precision/recall/F1 per category to agreement_report"
```

---

## Task 2: `POST /runs/{run_id}/gold-labels` — CSV upload

> **BLOCKED until `HumanLabelRecord` exists in `src/text_as_data/db.py`.** Check the file first. The class this task is written against (from `docs/superpowers/specs/2026-09-02-qualilab-interop-design.md`):
> ```python
> class HumanLabelRecord(SQLModel, table=True):
>     __tablename__ = "human_labels"
>     id: int | None = Field(default=None, primary_key=True)
>     document_id: int = Field(foreign_key="documents.id")
>     codebook_id: int = Field(foreign_key="codebooks.id")
>     category: str
>     coder: str
>     source: str = "manual"
>     created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
> ```
> If the landed version differs, adjust the field names used below accordingly.

**Files:**
- Modify: `src/text_as_data/app.py`
- Test: `tests/test_app_validation.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_app_validation.py`:

```python
from fastapi.testclient import TestClient

from text_as_data.app import app, get_engine_dependency, get_provider_dependency
from text_as_data.db import get_engine
from text_as_data.providers import Provider, ProviderResult

VALID_SPEC = {
    "concept": "protest",
    "description": "A collective public event.",
    "categories": [
        {"label": "protest", "definition": "An occupation, march, or strike."},
        {"label": "not_protest", "definition": "Any event that does not meet the criteria above."},
    ],
}


class FakeProvider(Provider):
    def extract(self, messages, schema):
        parsed = schema(categoria="protest", justificativa="because", trecho_evidencia="quote")
        return ProviderResult(parsed=parsed, prompt="fake prompt", raw_response="fake raw response")


def _make_test_client(n_documents: int = 1):
    engine = get_engine("sqlite://")
    app.dependency_overrides[get_engine_dependency] = lambda: engine
    app.dependency_overrides[get_provider_dependency] = lambda: FakeProvider()
    client = TestClient(app)

    codebook_id = client.post("/codebooks", json=VALID_SPEC).json()["id"]
    for i in range(n_documents):
        client.post("/corpora/paste", json={"name": "demo" if i == 0 else f"demo{i}", "text": f"document {i}"})
    # _make_test_client's corpus_id must be a single corpus for a run -- for
    # n_documents > 1 use CSV import instead of multiple pastes; see Step
    # below for the multi-document variant used by validation-report tests.
    run_id = client.post(
        "/runs", json={"codebook_id": codebook_id, "corpus_id": "demo", "model": "fake-model"}
    ).json()["run_id"]

    return client, codebook_id, run_id


def _document_id(client, run_id: int) -> int:
    return client.get(f"/runs/{run_id}/results").json()[0]["document_id"]


def test_upload_gold_labels_creates_human_label_rows():
    client, codebook_id, run_id = _make_test_client()
    document_id = _document_id(client, run_id)
    csv_content = f"document_id,gold_categoria\n{document_id},not_protest\n".encode("utf-8")

    response = client.post(
        f"/runs/{run_id}/gold-labels",
        files={"file": ("gold.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 200
    assert response.json() == {"imported": 1, "skipped_blank": 0}


def test_upload_gold_labels_skips_blank_rows_without_error():
    client, codebook_id, run_id = _make_test_client()
    document_id = _document_id(client, run_id)
    csv_content = f"document_id,gold_categoria\n{document_id},\n".encode("utf-8")

    response = client.post(
        f"/runs/{run_id}/gold-labels",
        files={"file": ("gold.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 200
    assert response.json() == {"imported": 0, "skipped_blank": 1}


def test_upload_gold_labels_rejects_whole_file_on_invalid_category():
    client, codebook_id, run_id = _make_test_client()
    document_id = _document_id(client, run_id)
    csv_content = f"document_id,gold_categoria\n{document_id},not_a_real_label\n".encode("utf-8")

    response = client.post(
        f"/runs/{run_id}/gold-labels",
        files={"file": ("gold.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 422
    assert "not_a_real_label" in response.json()["detail"]


def test_upload_gold_labels_404_for_unknown_run():
    client, codebook_id, run_id = _make_test_client()
    csv_content = b"document_id,gold_categoria\n1,protest\n"

    response = client.post(
        "/runs/999/gold-labels",
        files={"file": ("gold.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_app_validation.py -v`
Expected: FAIL — `404 Not Found` (route doesn't exist yet)

- [ ] **Step 3: Implement**

In `src/text_as_data/app.py`, add this import alongside the existing ones (adjust the class name/module if the landed `HumanLabelRecord` lives elsewhere):

```python
from .db import CodebookRecord, DocumentRecord, ExtractionRecord, HumanLabelRecord, RunRecord, get_engine
```

Add this endpoint after the existing `PUT /runs/{run_id}/results/{extraction_id}`:

```python
@app.post("/runs/{run_id}/gold-labels")
async def upload_gold_labels(
    run_id: int, file: UploadFile = File(...), engine=Depends(get_engine_dependency)
):
    with Session(engine) as session:
        run = session.get(RunRecord, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"run {run_id} not found")

        codebook = session.get(CodebookRecord, run.codebook_id)
        valid_labels = {c["label"] for c in spec_from_yaml_string(codebook.yaml_raw)["categories"]}

    content = await file.read()
    try:
        rows = parse_csv_rows(content)
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"could not decode file as UTF-8: {exc}") from exc
    if not rows or "document_id" not in rows[0] or "gold_categoria" not in rows[0]:
        raise HTTPException(
            status_code=422,
            detail="file must have 'document_id' and 'gold_categoria' columns "
            "(export a run's results and add a gold_categoria column to it)",
        )

    to_import: list[tuple[int, str]] = []
    skipped_blank = 0
    bad_rows: list[str] = []
    for row in rows:
        value = (row.get("gold_categoria") or "").strip()
        if not value:
            skipped_blank += 1
            continue
        if value not in valid_labels:
            bad_rows.append(f"document_id {row['document_id']}: {value!r} is not a valid category")
            continue
        to_import.append((int(row["document_id"]), value))

    if bad_rows:
        raise HTTPException(
            status_code=422,
            detail=f"expected one of {sorted(valid_labels)}; problems found: " + "; ".join(bad_rows),
        )

    with Session(engine) as session:
        for document_id, category in to_import:
            session.add(
                HumanLabelRecord(
                    document_id=document_id,
                    codebook_id=run.codebook_id,
                    category=category,
                    coder="manual",
                    source="manual",
                )
            )
        session.commit()

    return {"imported": len(to_import), "skipped_blank": skipped_blank}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_app_validation.py -v`
Expected: 4 passed

- [ ] **Step 5: Run the full suite**

Run: `pytest -v`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add src/text_as_data/app.py tests/test_app_validation.py
git commit -m "feat: add POST /runs/{id}/gold-labels (CSV upload)"
```

---

## Task 3: `GET /runs/{run_id}/validation` — the report

> Same blocking note as Task 2 — `HumanLabelRecord` must exist first.

**Files:**
- Modify: `src/text_as_data/app.py`
- Test: `tests/test_app_validation.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_app_validation.py`:

```python
def _upload_gold(client, run_id, document_id, categoria):
    csv_content = f"document_id,gold_categoria\n{document_id},{categoria}\n".encode("utf-8")
    response = client.post(
        f"/runs/{run_id}/gold-labels", files={"file": ("gold.csv", csv_content, "text/csv")}
    )
    assert response.status_code == 200
    return response


def test_validation_report_returns_coverage_and_metrics():
    client, codebook_id, run_id = _make_test_client()
    document_id = _document_id(client, run_id)
    _upload_gold(client, run_id, document_id, "protest")  # matches FakeProvider's prediction

    response = client.get(f"/runs/{run_id}/validation")

    assert response.status_code == 200
    body = response.json()
    assert body["coverage"] == {"labeled": 1, "total": 1, "excluded_multi_coder": 0}
    assert body["per_category"]["accuracy"] == 1.0
    assert body["disagreements"] == []


def test_validation_report_lists_disagreements_with_snippet():
    client, codebook_id, run_id = _make_test_client()
    document_id = _document_id(client, run_id)
    _upload_gold(client, run_id, document_id, "not_protest")  # FakeProvider predicts "protest"

    response = client.get(f"/runs/{run_id}/validation")

    assert response.status_code == 200
    body = response.json()
    assert body["per_category"]["accuracy"] == 0.0
    assert len(body["disagreements"]) == 1
    disagreement = body["disagreements"][0]
    assert disagreement["predicted"] == "protest"
    assert disagreement["gold"] == "not_protest"
    assert "document_snippet" in disagreement


def test_validation_report_excludes_multi_coder_documents():
    client, codebook_id, run_id = _make_test_client()
    document_id = _document_id(client, run_id)
    _upload_gold(client, run_id, document_id, "protest")
    # A second, differently-labeled gold entry for the SAME document
    # simulates a QualiLab multi-coder import -- the report must exclude
    # this document rather than pick one value silently.
    _upload_gold(client, run_id, document_id, "not_protest")

    response = client.get(f"/runs/{run_id}/validation")

    assert response.status_code == 200
    body = response.json()
    assert body["coverage"] == {"labeled": 0, "total": 1, "excluded_multi_coder": 1}
    assert body["disagreements"] == []


def test_validation_report_404_for_unknown_run():
    client, codebook_id, run_id = _make_test_client()

    response = client.get("/runs/999/validation")

    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_app_validation.py -v`
Expected: FAIL — `404 Not Found` for the new tests (route doesn't exist yet)

- [ ] **Step 3: Implement**

In `src/text_as_data/app.py`, add this import alongside the existing ones:

```python
import pandas as pd

from .validation import agreement_report
```

Add this endpoint after `upload_gold_labels`:

```python
@app.get("/runs/{run_id}/validation")
def get_run_validation(run_id: int, engine=Depends(get_engine_dependency)):
    with Session(engine) as session:
        run = session.get(RunRecord, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"run {run_id} not found")

        extractions = session.exec(select(ExtractionRecord).where(ExtractionRecord.run_id == run_id)).all()
        total_documents = len(
            session.exec(select(DocumentRecord).where(DocumentRecord.corpus_id == run.corpus_id)).all()
        )
        gold_rows = session.exec(
            select(HumanLabelRecord).where(HumanLabelRecord.codebook_id == run.codebook_id)
        ).all()

        gold_by_document: dict[int, list[str]] = {}
        for row in gold_rows:
            gold_by_document.setdefault(row.document_id, []).append(row.category)

        single_gold: dict[int, str] = {}
        excluded_multi_coder = 0
        for document_id, categories in gold_by_document.items():
            if len(set(categories)) > 1 or len(categories) > 1:
                excluded_multi_coder += 1
                continue
            single_gold[document_id] = categories[0]

        predicted_rows = [
            {"id": e.document_id, "categoria": e.categoria}
            for e in extractions
            if e.document_id in single_gold
        ]
        gold_df_rows = [{"id": doc_id, "categoria": cat} for doc_id, cat in single_gold.items() if
                        any(p["id"] == doc_id for p in predicted_rows)]

        if not predicted_rows:
            return {
                "coverage": {
                    "labeled": len(single_gold),
                    "total": total_documents,
                    "excluded_multi_coder": excluded_multi_coder,
                },
                "per_category": {},
                "disagreements": [],
            }

        predicted_df = pd.DataFrame(predicted_rows)
        gold_df = pd.DataFrame(gold_df_rows)
        report = agreement_report(predicted_df, gold_df, id_col="id", columns=["categoria"])
        metrics = report["per_column"]["categoria"]

        extraction_by_document = {e.document_id: e for e in extractions}
        disagreements = []
        for mismatch in report["mismatches"]:
            document_id = mismatch["id"]
            extraction = extraction_by_document[document_id]
            document = session.get(DocumentRecord, document_id)
            disagreements.append(
                {
                    "document_id": document_id,
                    "document_snippet": document.text[:160] if document else "",
                    "predicted": mismatch["predicted"],
                    "gold": mismatch["gold"],
                }
            )

        return {
            "coverage": {
                "labeled": len(single_gold),
                "total": total_documents,
                "excluded_multi_coder": excluded_multi_coder,
            },
            "per_category": metrics,
            "disagreements": disagreements,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_app_validation.py -v`
Expected: 8 passed

- [ ] **Step 5: Run the full suite**

Run: `pytest -v`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add src/text_as_data/app.py tests/test_app_validation.py
git commit -m "feat: add GET /runs/{id}/validation (report endpoint)"
```

---

## Task 4: `api.ts` — validation client functions

> Blocked on Tasks 2-3 (the endpoints must exist to call them), which are blocked on `HumanLabelRecord`.

**Files:**
- Modify: `frontend/src/api.ts`

- [ ] **Step 1: Add the types and functions**

Append to `frontend/src/api.ts`:

```typescript
export interface GoldLabelUploadResult {
  imported: number;
  skipped_blank: number;
}

export async function uploadGoldLabels(runId: number, file: File): Promise<GoldLabelUploadResult> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE}/runs/${runId}/gold-labels`, { method: "POST", body: formData });
  return handleResponse(response);
}

export interface CategoryMetrics {
  accuracy: number;
  kappa: number;
  precision: Record<string, number>;
  recall: Record<string, number>;
  f1: Record<string, number>;
}

export interface Disagreement {
  document_id: number;
  document_snippet: string;
  predicted: string;
  gold: string;
}

export interface ValidationReport {
  coverage: { labeled: number; total: number; excluded_multi_coder: number };
  per_category: CategoryMetrics | Record<string, never>;
  disagreements: Disagreement[];
}

export async function getRunValidation(runId: number): Promise<ValidationReport> {
  const response = await fetch(`${API_BASE}/runs/${runId}/validation`);
  return handleResponse(response);
}
```

- [ ] **Step 2: Verify it type-checks**

From `frontend/`: `npx tsc -b`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api.ts
git commit -m "feat: add validation client functions to frontend API client"
```

---

## Task 5: `ValidationPanel.tsx`

**Files:**
- Create: `frontend/src/ValidationPanel.tsx`

- [ ] **Step 1: Write the component**

Create `frontend/src/ValidationPanel.tsx`:

```tsx
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { getRunValidation, uploadGoldLabels } from "./api";
import type { ValidationReport } from "./api";

interface ValidationPanelProps {
  runId: number;
  onError: (err: unknown) => void;
}

export function ValidationPanel({ runId, onError }: ValidationPanelProps) {
  const { t } = useTranslation();
  const [report, setReport] = useState<ValidationReport | null>(null);
  const [file, setFile] = useState<File | null>(null);

  async function loadReport() {
    try {
      setReport(await getRunValidation(runId));
    } catch (err) {
      onError(err);
    }
  }

  useEffect(() => {
    loadReport();
  }, [runId]);

  async function handleUpload(event: React.FormEvent) {
    event.preventDefault();
    if (!file) return;
    try {
      await uploadGoldLabels(runId, file);
      setFile(null);
      await loadReport();
    } catch (err) {
      onError(err);
    }
  }

  const categories = report?.per_category && "precision" in report.per_category
    ? Object.keys(report.per_category.precision)
    : [];

  return (
    <div className="category-card">
      <div className="category-card-header">
        <span className="category-card-title">{t("validation.title")}</span>
      </div>

      {report && (
        <p className="empty-state">
          {t("validation.coverage", {
            labeled: report.coverage.labeled,
            total: report.coverage.total,
          })}
          {report.coverage.excluded_multi_coder > 0 &&
            ` · ${t("validation.excluded", { count: report.coverage.excluded_multi_coder })}`}
        </p>
      )}

      {report && categories.length > 0 && "precision" in report.per_category && (
        <table className="results-table">
          <thead>
            <tr>
              <th>{t("validation.colCategory")}</th>
              <th>{t("validation.colPrecision")}</th>
              <th>{t("validation.colRecall")}</th>
              <th>{t("validation.colF1")}</th>
            </tr>
          </thead>
          <tbody>
            {categories.map((label) => (
              <tr key={label}>
                <td>{label}</td>
                <td>{report.per_category.precision[label].toFixed(2)}</td>
                <td>{report.per_category.recall[label].toFixed(2)}</td>
                <td>{report.per_category.f1[label].toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {report && "accuracy" in report.per_category && (
        <p className="empty-state">
          {t("validation.overall", {
            accuracy: report.per_category.accuracy.toFixed(2),
            kappa: report.per_category.kappa.toFixed(2),
          })}
        </p>
      )}

      {report && report.disagreements.length > 0 && (
        <table className="results-table">
          <thead>
            <tr>
              <th>{t("runs.colDocument")}</th>
              <th>{t("validation.colPredicted")}</th>
              <th>{t("validation.colGold")}</th>
            </tr>
          </thead>
          <tbody>
            {report.disagreements.map((d) => (
              <tr key={d.document_id}>
                <td>{d.document_snippet}</td>
                <td>
                  <span className="pill">{d.predicted}</span>
                </td>
                <td>
                  <span className="pill">{d.gold}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <form onSubmit={handleUpload} className="actions-row">
        <input type="file" accept=".csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} required />
        <button className="btn btn-primary" type="submit">
          {t("validation.upload")}
        </button>
      </form>
    </div>
  );
}
```

- [ ] **Step 2: Verify it type-checks**

From `frontend/`: `npx tsc -b`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/ValidationPanel.tsx
git commit -m "feat: add ValidationPanel component"
```

---

## Task 6: wire `ValidationPanel` into `ResultsTable.tsx`, add locale keys

**Files:**
- Modify: `frontend/src/ResultsTable.tsx`
- Modify: `frontend/src/locales/en.json`, `frontend/src/locales/pt-BR.json`

- [ ] **Step 1: Add locale keys**

In `frontend/src/locales/en.json`, add a `"validation"` block after the `"runs"` block:

```json
  "validation": {
    "title": "Validate",
    "coverage": "{{labeled}} of {{total}} documents have a gold label",
    "excluded": "{{count}} excluded (multiple coders)",
    "colCategory": "Category",
    "colPrecision": "Precision",
    "colRecall": "Recall",
    "colF1": "F1",
    "colPredicted": "Predicted",
    "colGold": "Gold",
    "overall": "Overall accuracy {{accuracy}}, kappa {{kappa}}",
    "upload": "Upload gold labels"
  },
```

In `frontend/src/locales/pt-BR.json`, add the matching block:

```json
  "validation": {
    "title": "Validar",
    "coverage": "{{labeled}} de {{total}} documentos têm rótulo padrão-ouro",
    "excluded": "{{count}} excluídos (múltiplos coders)",
    "colCategory": "Categoria",
    "colPrecision": "Precisão",
    "colRecall": "Recall",
    "colF1": "F1",
    "colPredicted": "Previsto",
    "colGold": "Padrão-ouro",
    "overall": "Acurácia geral {{accuracy}}, kappa {{kappa}}",
    "upload": "Enviar rótulos padrão-ouro"
  },
```

- [ ] **Step 2: Wire the component into `ResultsTable.tsx`**

In `frontend/src/ResultsTable.tsx`, add the import:

```tsx
import { ValidationPanel } from "./ValidationPanel";
```

Add `<ValidationPanel runId={runId} onError={onError} />` right after the closing `</table>` of the main results table, before the final closing `</div>` of the component.

- [ ] **Step 3: Verify it builds**

From `frontend/`: `npm run build`
Expected: no TypeScript errors, `frontend/dist/` written

- [ ] **Step 4: Commit**

```bash
git add frontend/src/ResultsTable.tsx frontend/src/locales/en.json frontend/src/locales/pt-BR.json
git commit -m "feat: wire ValidationPanel into ResultsTable"
```

---

## Task 7: manual end-to-end verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend test suite**

Run: `pytest -v`
Expected: all pass

- [ ] **Step 2: Start both servers, run a small run**

Via `scripts/dev.sh` (check for other sessions' servers on the default ports first, use alternate ports if needed — see Slice 3's plan for the pattern). Create or reuse a corpus + codebook, start a run, wait for it to finish.

- [ ] **Step 3: Export, edit, re-upload as gold**

From the finished run's results, click "Export CSV", open it, add a `gold_categoria` value for at least one row (matching one of the codebook's real category labels), save, and upload it back via the new "Validate" section's upload form.

Expected: the coverage line updates, a per-category metrics table appears, and the row you graded either shows 100% agreement (if you matched the model's prediction) or appears in a disagreements list (if you didn't) — try both by uploading one gold value that matches and, after seeing the report, uploading a second run's export with one that doesn't.

- [ ] **Step 4: Check the browser console**

No errors during any of the above (`read_console_messages` with `onlyErrors: true` if driving this via the Claude Browser pane).

- [ ] **Step 5: Confirm the language toggle covers the new section**

Switch PT/EN on the Validate section specifically — every label should translate.

---

## Task 8: close out the slice — `TODO.md`, `NEWS.md`

**Files:**
- Modify: `TODO.md`
- Modify: `NEWS.md`

- [ ] **Step 1: Update `TODO.md`**

**Re-read `TODO.md` first** — multiple sessions have been actively appending to it today. Remove the "Validation screen (Screen 5)..." line from `## Pending` (only that line), and add under `## Done` a summary of this slice: the gold-label CSV upload (reusing the results-export shape), the validation report endpoint (coverage, per-category accuracy/kappa/precision/recall/F1, disagreements), the multi-coder-exclusion behavior, and that this closes out every screen in `AGENTS.md`'s original MVP list.

- [ ] **Step 2: Update `NEWS.md`**

**Re-read `NEWS.md` first**, check what date/section-number is already at the top (multiple sessions have been adding entries today), and add a new section above it summarizing the same points as the `TODO.md` entry, in the style of the existing entries.

- [ ] **Step 3: Commit**

```bash
git add TODO.md NEWS.md
git commit -m "docs: close out Slice 4 (Validation screen) -- MVP screens complete"
```

---

## Self-Review Notes

- **Spec coverage**: every design-spec requirement has a task — precision/recall/F1 (Task 1), the CSV upload reusing the export shape with all-or-nothing validity / non-blocking coverage (Task 2), the report endpoint with multi-coder exclusion (Task 3), the frontend upload+report UI wired into the existing Runs detail view rather than a new tab (Tasks 4-6), and manual verification of the actual export-edit-reupload loop (Task 7).
- **Cross-session dependency handled explicitly**: Tasks 2-3 (and everything downstream of them, Tasks 4-6) carry an explicit blocking note and tell the implementer to check the real `HumanLabelRecord` shape in `db.py` before writing code against the version quoted from the design spec, in case the peer session's landed version differs.
- **Type consistency checked**: `GoldLabelUploadResult`, `CategoryMetrics`, `Disagreement`, `ValidationReport` in `api.ts` (Task 4) match the exact JSON shape `GET /runs/{id}/validation` and `POST /runs/{id}/gold-labels` return in Task 3/2; `ValidationPanel.tsx` (Task 5) consumes exactly those fields.
- **Not in this plan** (explicitly out of scope per the design spec): resolving multi-coder gold labels automatically, a UI for browsing/editing individual `human_labels` rows outside the CSV flow, any QualiLab-specific UI, auto-recomputing the report when results are edited.
