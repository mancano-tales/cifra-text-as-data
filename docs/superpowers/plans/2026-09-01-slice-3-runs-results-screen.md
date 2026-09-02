# Slice 3 — Runs + Results Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Runs" tab to the frontend — create a run, watch it progress live, then view/filter/edit/export its results — closing the gap between Slice 2's Corpus+Codebook screens and a usable end-to-end flow.

**Architecture:** Backend gains a new `export.py` (three pure CSV/XLSX/JSON serializers, same pattern as `corpus_import.py`) and four `app.py` additions (`GET /runs` list, an extended `GET /runs/{id}/results` that joins in a document snippet, a new `PUT /runs/{id}/results/{id}` edit endpoint validated against the run's own codebook labels, and a `GET /runs/{id}/export` download endpoint). Frontend gains three new components (`RunForm.tsx`, `ResultsTable.tsx`, `RunsPage.tsx`) composed the same list+detail way `CodebookEditor.tsx` already is, plus new `runs.*` locale keys and a few CSS additions.

**Tech Stack:** Same as Slices 1-2 — FastAPI, SQLModel, `openpyxl`, pytest; React, TypeScript, `react-i18next`.

**Design spec:** `docs/superpowers/specs/2026-09-01-slice-3-runs-results-screen-design.md` — read it first.

**Note on shared state:** other Claude Code sessions are also active on this same repo/branch right now. Before editing any file this plan touches, check whether it has changed since you last read it (the harness surfaces this automatically) and re-read before editing if so — don't blindly overwrite a concurrent edit. Never delete or reset `codifica.sqlite` — it may be a live shared database another session's backend process has open.

---

## Before you start

Read, in order:
1. `text-as-data/docs/superpowers/specs/2026-09-01-slice-3-runs-results-screen-design.md` — this slice's design and rationale (why one "Runs" tab, not two).
2. `text-as-data/src/text_as_data/app.py` — the exact current endpoints this plan extends, including the CLI-mode fields on `CreateRunRequest` (`provider_mode`, `cli_command`, `cli_prompt_mode`) that a different session already added.
3. `text-as-data/frontend/src/CodebookEditor.tsx` and `frontend/src/api.ts` — the list+detail pattern and API-client conventions this plan follows.

---

## File Structure

- `src/text_as_data/export.py` — **create**: `results_to_csv_bytes`, `results_to_xlsx_bytes`, `results_to_json_bytes`.
- `src/text_as_data/app.py` — **modify**: extend `get_run_results`, add `list_runs`, `update_extraction`, `export_run_results`.
- `tests/test_export.py` — **create**.
- `tests/test_app_runs.py` — **create**.
- `frontend/src/api.ts` — **modify**: add run-related types and functions.
- `frontend/src/RunForm.tsx` — **create**: the "create a new run" form.
- `frontend/src/ResultsTable.tsx` — **create**: filter/edit/export table for a done run.
- `frontend/src/RunsPage.tsx` — **create**: list + detail composition, polling.
- `frontend/src/App.tsx` — **modify**: add the third tab.
- `frontend/src/index.css` — **modify**: `.runs-layout`, progress bar, results table styles.
- `frontend/src/locales/en.json`, `frontend/src/locales/pt-BR.json` — **modify**: add `runs.*` keys.
- `TODO.md`, `NEWS.md` — **modify**: close out the slice.

---

## Task 1: `export.py` — pure CSV/XLSX/JSON serializers

**Files:**
- Create: `src/text_as_data/export.py`
- Test: `tests/test_export.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_export.py`:

```python
import csv
import io
import json

import openpyxl

from text_as_data.export import results_to_csv_bytes, results_to_json_bytes, results_to_xlsx_bytes

SAMPLE_ROWS = [
    {"document_snippet": "About 200 people occupied...", "categoria": "protest", "justificativa": "clear demand"},
    {"document_snippet": "A music festival happened...", "categoria": "not_protest", "justificativa": "no claim"},
]


def test_results_to_csv_bytes_round_trips():
    content = results_to_csv_bytes(SAMPLE_ROWS)

    reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
    rows = list(reader)

    assert rows == SAMPLE_ROWS


def test_results_to_csv_bytes_handles_empty_list():
    assert results_to_csv_bytes([]) == b""


def test_results_to_xlsx_bytes_round_trips():
    content = results_to_xlsx_bytes(SAMPLE_ROWS)

    workbook = openpyxl.load_workbook(io.BytesIO(content))
    sheet = workbook.active
    rows_iter = sheet.iter_rows(values_only=True)
    header = next(rows_iter)
    rows = [dict(zip(header, values)) for values in rows_iter]

    assert rows == SAMPLE_ROWS


def test_results_to_json_bytes_round_trips():
    content = results_to_json_bytes(SAMPLE_ROWS)

    assert json.loads(content.decode("utf-8")) == SAMPLE_ROWS
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_export.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'text_as_data.export'`

- [ ] **Step 3: Implement**

Create `src/text_as_data/export.py`:

```python
from __future__ import annotations

import csv
import io
import json

import openpyxl


def results_to_csv_bytes(rows: list[dict]) -> bytes:
    if not rows:
        return b""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def results_to_xlsx_bytes(rows: list[dict]) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    if rows:
        headers = list(rows[0].keys())
        sheet.append(headers)
        for row in rows:
            sheet.append([row.get(h) for h in headers])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def results_to_json_bytes(rows: list[dict]) -> bytes:
    return json.dumps(rows, ensure_ascii=False, indent=2).encode("utf-8")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_export.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/text_as_data/export.py tests/test_export.py
git commit -m "feat: add CSV/XLSX/JSON result serializers"
```

---

## Task 2: extend `GET /runs/{run_id}/results` with `document_snippet`

**Files:**
- Modify: `src/text_as_data/app.py`
- Test: `tests/test_app_runs.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_app_runs.py`:

```python
from fastapi.testclient import TestClient
from sqlmodel import Session

from text_as_data.app import app, get_engine_dependency, get_provider_dependency
from text_as_data.db import get_engine
from text_as_data.providers import Provider

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
        return schema(categoria="protest", justificativa="because", trecho_evidencia="quote")


def _make_test_client():
    engine = get_engine("sqlite://")
    app.dependency_overrides[get_engine_dependency] = lambda: engine
    app.dependency_overrides[get_provider_dependency] = lambda: FakeProvider()
    client = TestClient(app)

    codebook_id = client.post("/codebooks", json=VALID_SPEC).json()["id"]
    client.post("/corpora/paste", json={"name": "demo", "text": "About 200 people occupied the square."})
    run_id = client.post(
        "/runs", json={"codebook_id": codebook_id, "corpus_id": "demo", "model": "fake-model"}
    ).json()["run_id"]

    return client, codebook_id, run_id


def test_get_run_results_includes_document_snippet():
    client, codebook_id, run_id = _make_test_client()

    response = client.get(f"/runs/{run_id}/results")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["document_snippet"].startswith("About 200 people occupied")
    assert body[0]["categoria"] == "protest"
```

Note: `Session` is imported but unused by this first test — later tasks in this file use it, so leave the import in place.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_app_runs.py -v`
Expected: FAIL — `assert "document_snippet" ...` raises `KeyError` (the field doesn't exist in the response yet)

- [ ] **Step 3: Implement**

In `src/text_as_data/app.py`, replace the existing `get_run_results` function:

```python
@app.get("/runs/{run_id}/results")
def get_run_results(run_id: int, engine=Depends(get_engine_dependency)):
    with Session(engine) as session:
        run = session.get(RunRecord, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"run {run_id} not found")

        rows = session.exec(select(ExtractionRecord).where(ExtractionRecord.run_id == run_id)).all()
        return [_extraction_with_snippet(session, row) for row in rows]
```

Add this helper right above it:

```python
def _extraction_with_snippet(session: Session, extraction: ExtractionRecord) -> dict:
    document = session.get(DocumentRecord, extraction.document_id)
    snippet = document.text[:160] if document else ""
    return {**extraction.model_dump(), "document_snippet": snippet}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_app_runs.py -v`
Expected: 1 passed

- [ ] **Step 5: Run the full suite**

Run: `pytest -v`
Expected: all pass — this only adds a field, nothing removed.

- [ ] **Step 6: Commit**

```bash
git add src/text_as_data/app.py tests/test_app_runs.py
git commit -m "feat: include document_snippet in run results"
```

---

## Task 3: `GET /runs` — list all runs

**Files:**
- Modify: `src/text_as_data/app.py`
- Test: `tests/test_app_runs.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_app_runs.py`:

```python
def test_list_runs_returns_run_with_codebook_name_and_counts():
    client, codebook_id, run_id = _make_test_client()

    response = client.get("/runs")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == run_id
    assert body[0]["corpus_id"] == "demo"
    assert body[0]["codebook_id"] == codebook_id
    assert body[0]["codebook_name"] == "protest"
    assert body[0]["status"] == "done"
    assert body[0]["processed"] == 1
    assert body[0]["total"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_app_runs.py::test_list_runs_returns_run_with_codebook_name_and_counts -v`
Expected: FAIL with `404 Not Found` (route doesn't exist yet)

- [ ] **Step 3: Implement**

In `src/text_as_data/app.py`, add this endpoint right before `@app.post("/runs")`:

```python
@app.get("/runs")
def list_runs(engine=Depends(get_engine_dependency)):
    with Session(engine) as session:
        runs = session.exec(select(RunRecord).order_by(RunRecord.created_at.desc())).all()
        results = []
        for run in runs:
            codebook = session.get(CodebookRecord, run.codebook_id)
            total = len(
                session.exec(select(DocumentRecord).where(DocumentRecord.corpus_id == run.corpus_id)).all()
            )
            processed = len(session.exec(select(ExtractionRecord).where(ExtractionRecord.run_id == run.id)).all())
            results.append(
                {
                    "id": run.id,
                    "corpus_id": run.corpus_id,
                    "codebook_id": run.codebook_id,
                    "codebook_name": codebook.name if codebook else None,
                    "model": run.model,
                    "status": run.status,
                    "processed": processed,
                    "total": total,
                    "created_at": run.created_at,
                }
            )
        return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_app_runs.py -v`
Expected: 2 passed

- [ ] **Step 5: Run the full suite**

Run: `pytest -v`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add src/text_as_data/app.py tests/test_app_runs.py
git commit -m "feat: add GET /runs (list all runs)"
```

---

## Task 4: `PUT /runs/{run_id}/results/{extraction_id}` — edit a result

**Files:**
- Modify: `src/text_as_data/app.py`
- Test: `tests/test_app_runs.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_app_runs.py`:

```python
def test_update_extraction_changes_categoria_and_justificativa():
    client, codebook_id, run_id = _make_test_client()
    extraction_id = client.get(f"/runs/{run_id}/results").json()[0]["id"]

    response = client.put(
        f"/runs/{run_id}/results/{extraction_id}",
        json={"categoria": "not_protest", "justificativa": "corrected by hand"},
    )

    assert response.status_code == 200
    assert response.json()["categoria"] == "not_protest"
    body = client.get(f"/runs/{run_id}/results").json()
    assert body[0]["categoria"] == "not_protest"
    assert body[0]["justificativa"] == "corrected by hand"


def test_update_extraction_rejects_invalid_categoria():
    client, codebook_id, run_id = _make_test_client()
    extraction_id = client.get(f"/runs/{run_id}/results").json()[0]["id"]

    response = client.put(
        f"/runs/{run_id}/results/{extraction_id}",
        json={"categoria": "not_a_real_label", "justificativa": "x"},
    )

    assert response.status_code == 422


def test_update_extraction_404_for_unknown_extraction():
    client, codebook_id, run_id = _make_test_client()

    response = client.put(
        f"/runs/{run_id}/results/999",
        json={"categoria": "protest", "justificativa": "x"},
    )

    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_app_runs.py -v`
Expected: FAIL — 3 new failures, `405 Method Not Allowed` (no `PUT` route at that path yet)

- [ ] **Step 3: Implement**

In `src/text_as_data/app.py`, add this request model near `PasteCorpusRequest`:

```python
class UpdateExtractionRequest(BaseModel):
    categoria: str
    justificativa: str
```

Add this endpoint after `get_run_results`:

```python
@app.put("/runs/{run_id}/results/{extraction_id}")
def update_extraction(
    run_id: int, extraction_id: int, request: UpdateExtractionRequest, engine=Depends(get_engine_dependency)
):
    with Session(engine) as session:
        run = session.get(RunRecord, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"run {run_id} not found")

        extraction = session.get(ExtractionRecord, extraction_id)
        if extraction is None or extraction.run_id != run_id:
            raise HTTPException(status_code=404, detail=f"extraction {extraction_id} not found in run {run_id}")

        codebook = session.get(CodebookRecord, run.codebook_id)
        valid_labels = {c["label"] for c in spec_from_yaml_string(codebook.yaml_raw)["categories"]}
        if request.categoria not in valid_labels:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"categoria {request.categoria!r} is not a valid label for this codebook; "
                    f"expected one of {sorted(valid_labels)}"
                ),
            )

        extraction.categoria = request.categoria
        extraction.justificativa = request.justificativa
        session.add(extraction)
        session.commit()
        session.refresh(extraction)
        return _extraction_with_snippet(session, extraction)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_app_runs.py -v`
Expected: 5 passed

- [ ] **Step 5: Run the full suite**

Run: `pytest -v`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add src/text_as_data/app.py tests/test_app_runs.py
git commit -m "feat: add PUT /runs/{id}/results/{id} to edit a result"
```

---

## Task 5: `GET /runs/{run_id}/export` — download results

**Files:**
- Modify: `src/text_as_data/app.py`
- Test: `tests/test_app_runs.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_app_runs.py`:

```python
def test_export_run_results_csv():
    client, codebook_id, run_id = _make_test_client()

    response = client.get(f"/runs/{run_id}/export?format=csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "protest" in response.text


def test_export_run_results_json():
    client, codebook_id, run_id = _make_test_client()

    response = client.get(f"/runs/{run_id}/export?format=json")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["categoria"] == "protest"


def test_export_run_results_xlsx():
    import io

    import openpyxl

    client, codebook_id, run_id = _make_test_client()

    response = client.get(f"/runs/{run_id}/export?format=xlsx")

    assert response.status_code == 200
    workbook = openpyxl.load_workbook(io.BytesIO(response.content))
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    assert len(rows) == 2  # header + 1 data row


def test_export_run_results_404_for_unknown_run():
    client, codebook_id, run_id = _make_test_client()

    response = client.get("/runs/999/export?format=csv")

    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_app_runs.py -v`
Expected: FAIL — 4 new failures, `404 Not Found` (route doesn't exist yet)

- [ ] **Step 3: Implement**

In `src/text_as_data/app.py`, change this import line:

```python
from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, UploadFile
```

to:

```python
from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Response, UploadFile
```

Add this import near the top, alongside the `.codebook` import:

```python
from .export import results_to_csv_bytes, results_to_json_bytes, results_to_xlsx_bytes
```

Add this near the top of the file (module level, after the imports, before `app = FastAPI(...)` or anywhere at module scope):

```python
_EXPORT_CONTENT_TYPES = {
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "json": "application/json",
}
_EXPORT_BUILDERS = {
    "csv": results_to_csv_bytes,
    "xlsx": results_to_xlsx_bytes,
    "json": results_to_json_bytes,
}
```

Add this endpoint after `update_extraction`:

```python
@app.get("/runs/{run_id}/export")
def export_run_results(
    run_id: int, format: Literal["csv", "xlsx", "json"] = "csv", engine=Depends(get_engine_dependency)
):
    with Session(engine) as session:
        run = session.get(RunRecord, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"run {run_id} not found")

        rows = session.exec(select(ExtractionRecord).where(ExtractionRecord.run_id == run_id)).all()
        result_rows = [_extraction_with_snippet(session, row) for row in rows]

    content = _EXPORT_BUILDERS[format](result_rows)
    return Response(
        content=content,
        media_type=_EXPORT_CONTENT_TYPES[format],
        headers={"Content-Disposition": f'attachment; filename="run_{run_id}_results.{format}"'},
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_app_runs.py -v`
Expected: 9 passed

- [ ] **Step 5: Run the full suite**

Run: `pytest -v`
Expected: all pass (should be ~85 tests by this point)

- [ ] **Step 6: Commit**

```bash
git add src/text_as_data/app.py tests/test_app_runs.py
git commit -m "feat: add GET /runs/{id}/export (CSV/XLSX/JSON download)"
```

---

## Task 6: `api.ts` — run-related client functions

**Files:**
- Modify: `frontend/src/api.ts`

- [ ] **Step 1: Add the types and functions**

Append to `frontend/src/api.ts`:

```typescript
export interface RunSummary {
  id: number;
  corpus_id: string;
  codebook_id: number;
  codebook_name: string;
  model: string;
  status: string;
  processed: number;
  total: number;
  created_at: string;
}

export interface RunStatus {
  id: number;
  status: string;
  processed: number;
  total: number;
}

export interface ExtractionResult {
  id: number;
  run_id: number;
  document_id: number;
  categoria: string;
  justificativa: string;
  trecho_evidencia: string;
  tokens_used: number | null;
  document_snippet: string;
}

export interface CreateRunRequest {
  codebook_id: number;
  corpus_id: string;
  model: string;
  provider_mode: "api_key" | "cli";
  cli_command?: string[];
  cli_prompt_mode?: "stdin" | "arg";
}

export async function listRuns(): Promise<RunSummary[]> {
  const response = await fetch(`${API_BASE}/runs`);
  return handleResponse(response);
}

export async function getRun(id: number): Promise<RunStatus> {
  const response = await fetch(`${API_BASE}/runs/${id}`);
  return handleResponse(response);
}

export async function getRunResults(id: number): Promise<ExtractionResult[]> {
  const response = await fetch(`${API_BASE}/runs/${id}/results`);
  return handleResponse(response);
}

export async function createRun(request: CreateRunRequest): Promise<{ run_id: number }> {
  const response = await fetch(`${API_BASE}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return handleResponse(response);
}

export async function updateExtraction(
  runId: number,
  extractionId: number,
  categoria: string,
  justificativa: string
): Promise<ExtractionResult> {
  const response = await fetch(`${API_BASE}/runs/${runId}/results/${extractionId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ categoria, justificativa }),
  });
  return handleResponse(response);
}

export function exportRunUrl(runId: number, format: "csv" | "xlsx" | "json"): string {
  return `${API_BASE}/runs/${runId}/export?format=${format}`;
}
```

- [ ] **Step 2: Verify it type-checks**

From `frontend/`: `npx tsc -b`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api.ts
git commit -m "feat: add run-related functions to frontend API client"
```

---

## Task 7: locale keys for the Runs screen

**Files:**
- Modify: `frontend/src/locales/en.json`, `frontend/src/locales/pt-BR.json`

- [ ] **Step 1: Add English keys**

In `frontend/src/locales/en.json`, add a `"runs"` key at the same level as `"corpus"` and `"codebook"` (after the `"codebook"` block, before `"errors"`):

```json
  "runs": {
    "listTitle": "Runs",
    "newRun": "+ New run",
    "none": "No runs yet.",
    "corpus": "Corpus",
    "codebook": "Codebook",
    "selectCorpus": "Select a corpus...",
    "selectCodebook": "Select a codebook...",
    "model": "Model",
    "providerMode": "Provider",
    "providerApiKey": "API key (Anthropic)",
    "providerCli": "CLI",
    "cliCommand": "CLI command (e.g. claude -p)",
    "cliPromptMode": "Prompt delivery",
    "start": "Start run",
    "inProgress": "Running...",
    "runFailed": "This run failed to complete.",
    "resultsTitle": "Results",
    "filterByCategory": "Filter by category",
    "allCategories": "All categories",
    "exportCsv": "Export CSV",
    "exportXlsx": "Export XLSX",
    "exportJson": "Export JSON",
    "colDocument": "Document",
    "colCategory": "Category",
    "colJustification": "Justification",
    "edit": "Edit",
    "save": "Save"
  },
```

Also add `"runs": "Runs"` inside the existing `"app.nav"` block, alongside `"corpus"` and `"codebook"`:

```json
    "nav": {
      "corpus": "Corpus",
      "codebook": "Codebook",
      "runs": "Runs"
    }
```

- [ ] **Step 2: Add the matching Portuguese keys**

In `frontend/src/locales/pt-BR.json`, add the same two blocks, translated:

```json
  "runs": {
    "listTitle": "Execuções",
    "newRun": "+ Nova execução",
    "none": "Nenhuma execução ainda.",
    "corpus": "Corpus",
    "codebook": "Codebook",
    "selectCorpus": "Selecione um corpus...",
    "selectCodebook": "Selecione um codebook...",
    "model": "Modelo",
    "providerMode": "Provedor",
    "providerApiKey": "Chave de API (Anthropic)",
    "providerCli": "CLI",
    "cliCommand": "Comando CLI (ex: claude -p)",
    "cliPromptMode": "Envio do prompt",
    "start": "Iniciar execução",
    "inProgress": "Executando...",
    "runFailed": "Esta execução falhou.",
    "resultsTitle": "Resultados",
    "filterByCategory": "Filtrar por categoria",
    "allCategories": "Todas as categorias",
    "exportCsv": "Exportar CSV",
    "exportXlsx": "Exportar XLSX",
    "exportJson": "Exportar JSON",
    "colDocument": "Documento",
    "colCategory": "Categoria",
    "colJustification": "Justificativa",
    "edit": "Editar",
    "save": "Salvar"
  },
```

```json
    "nav": {
      "corpus": "Corpus",
      "codebook": "Codebook",
      "runs": "Execuções"
    }
```

- [ ] **Step 3: Verify both files are valid JSON**

Run: `node -e "JSON.parse(require('fs').readFileSync('frontend/src/locales/en.json'))" && node -e "JSON.parse(require('fs').readFileSync('frontend/src/locales/pt-BR.json'))"`
Expected: no output, no error (a JSON syntax error throws and prints a stack trace)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/locales/en.json frontend/src/locales/pt-BR.json
git commit -m "feat: add runs.* locale keys (EN/PT-BR)"
```

---

## Task 8: CSS additions for the Runs screen

**Files:**
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Add the styles**

Append to `frontend/src/index.css`:

```css
/* Runs screen */

.runs-layout {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

@media (max-width: 800px) {
  .runs-layout {
    grid-template-columns: 1fr;
  }
}

.progress-track {
  background: var(--bg);
  border: 0.8px solid var(--border);
  border-radius: 999px;
  height: 10px;
  overflow: hidden;
  margin: 8px 0;
}

.progress-fill {
  background: var(--accent);
  height: 100%;
  transition: width 0.3s ease;
}

.results-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
  margin-top: 12px;
}

.results-table th,
.results-table td {
  text-align: left;
  padding: 8px;
  border-bottom: 0.8px solid var(--border);
  vertical-align: top;
}

.results-table th {
  color: var(--text-muted);
  font-weight: 500;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
```

Also add `text-decoration: none;` to the existing `.btn` rule (the export buttons are `<a>` tags styled as buttons, and anchors show an underline by default):

```css
.btn {
  appearance: none;
  font-family: var(--font);
  font-size: 12.5px;
  font-weight: 600;
  border-radius: var(--radius);
  padding: 7px 14px;
  cursor: pointer;
  border: 0.8px solid var(--border);
  background: var(--surface);
  color: var(--text);
  text-decoration: none;
  display: inline-block;
}
```

(This replaces the existing `.btn { ... }` rule — same properties plus `text-decoration: none;` and `display: inline-block;`, the latter so padding renders correctly on an `<a>`.)

- [ ] **Step 2: Commit**

```bash
git add frontend/src/index.css
git commit -m "style: add Runs screen CSS (progress bar, results table)"
```

---

## Task 9: `RunForm.tsx` — the create-run form

**Files:**
- Create: `frontend/src/RunForm.tsx`

- [ ] **Step 1: Write the component**

Create `frontend/src/RunForm.tsx`:

```tsx
import { useState } from "react";
import type { FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { createRun } from "./api";
import type { CodebookSummary, CorpusSummary } from "./api";

interface RunFormProps {
  corpora: CorpusSummary[];
  codebooks: CodebookSummary[];
  onCreated: (runId: number) => void;
  onError: (err: unknown) => void;
}

export function RunForm({ corpora, codebooks, onCreated, onError }: RunFormProps) {
  const { t } = useTranslation();
  const [corpusId, setCorpusId] = useState("");
  const [codebookId, setCodebookId] = useState("");
  const [model, setModel] = useState("claude-sonnet-5");
  const [providerMode, setProviderMode] = useState<"api_key" | "cli">("api_key");
  const [cliCommand, setCliCommand] = useState("claude -p");
  const [cliPromptMode, setCliPromptMode] = useState<"stdin" | "arg">("stdin");

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    try {
      const { run_id } = await createRun({
        codebook_id: Number(codebookId),
        corpus_id: corpusId,
        model,
        provider_mode: providerMode,
        ...(providerMode === "cli"
          ? { cli_command: cliCommand.split(" ").filter(Boolean), cli_prompt_mode: cliPromptMode }
          : {}),
      });
      onCreated(run_id);
    } catch (err) {
      onError(err);
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <h3 className="card-title">{t("runs.newRun")}</h3>
      <div className="field">
        <label className="field-label">{t("runs.corpus")}</label>
        <select value={corpusId} onChange={(e) => setCorpusId(e.target.value)} required>
          <option value="" disabled>
            {t("runs.selectCorpus")}
          </option>
          {corpora.map((c) => (
            <option key={c.corpus_id} value={c.corpus_id}>
              {c.corpus_id} ({c.document_count})
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label className="field-label">{t("runs.codebook")}</label>
        <select value={codebookId} onChange={(e) => setCodebookId(e.target.value)} required>
          <option value="" disabled>
            {t("runs.selectCodebook")}
          </option>
          {codebooks.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label className="field-label">{t("runs.model")}</label>
        <input value={model} onChange={(e) => setModel(e.target.value)} required />
      </div>
      <div className="field">
        <label className="field-label">{t("runs.providerMode")}</label>
        <select value={providerMode} onChange={(e) => setProviderMode(e.target.value as "api_key" | "cli")}>
          <option value="api_key">{t("runs.providerApiKey")}</option>
          <option value="cli">{t("runs.providerCli")}</option>
        </select>
      </div>
      {providerMode === "cli" && (
        <>
          <div className="field">
            <label className="field-label">{t("runs.cliCommand")}</label>
            <input value={cliCommand} onChange={(e) => setCliCommand(e.target.value)} required />
          </div>
          <div className="field">
            <label className="field-label">{t("runs.cliPromptMode")}</label>
            <select value={cliPromptMode} onChange={(e) => setCliPromptMode(e.target.value as "stdin" | "arg")}>
              <option value="stdin">stdin</option>
              <option value="arg">arg</option>
            </select>
          </div>
        </>
      )}
      <button type="submit" className="btn btn-primary">
        {t("runs.start")}
      </button>
    </form>
  );
}
```

- [ ] **Step 2: Verify it type-checks**

From `frontend/`: `npx tsc -b`
Expected: no errors (this component isn't wired into `App.tsx` yet, but `tsc -b` checks every file in the project)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/RunForm.tsx
git commit -m "feat: add RunForm component"
```

---

## Task 10: `ResultsTable.tsx` — filter/edit/export table

**Files:**
- Create: `frontend/src/ResultsTable.tsx`

- [ ] **Step 1: Write the component**

Create `frontend/src/ResultsTable.tsx`:

```tsx
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { exportRunUrl, updateExtraction } from "./api";
import type { ExtractionResult } from "./api";

interface ResultsTableProps {
  runId: number;
  results: ExtractionResult[];
  codebookLabels: string[];
  onResultsChange: (results: ExtractionResult[]) => void;
  onError: (err: unknown) => void;
}

export function ResultsTable({ runId, results, codebookLabels, onResultsChange, onError }: ResultsTableProps) {
  const { t } = useTranslation();
  const [categoryFilter, setCategoryFilter] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editCategoria, setEditCategoria] = useState("");
  const [editJustificativa, setEditJustificativa] = useState("");

  function startEdit(row: ExtractionResult) {
    setEditingId(row.id);
    setEditCategoria(row.categoria);
    setEditJustificativa(row.justificativa);
  }

  async function saveEdit(row: ExtractionResult) {
    try {
      const updated = await updateExtraction(runId, row.id, editCategoria, editJustificativa);
      onResultsChange(results.map((r) => (r.id === row.id ? updated : r)));
      setEditingId(null);
    } catch (err) {
      onError(err);
    }
  }

  const filteredResults = categoryFilter ? results.filter((r) => r.categoria === categoryFilter) : results;

  return (
    <div>
      <h3 className="card-title">{t("runs.resultsTitle")}</h3>
      <div className="field">
        <label className="field-label">{t("runs.filterByCategory")}</label>
        <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}>
          <option value="">{t("runs.allCategories")}</option>
          {codebookLabels.map((label) => (
            <option key={label} value={label}>
              {label}
            </option>
          ))}
        </select>
      </div>
      <div className="actions-row">
        <a className="btn" href={exportRunUrl(runId, "csv")}>
          {t("runs.exportCsv")}
        </a>
        <a className="btn" href={exportRunUrl(runId, "xlsx")}>
          {t("runs.exportXlsx")}
        </a>
        <a className="btn" href={exportRunUrl(runId, "json")}>
          {t("runs.exportJson")}
        </a>
      </div>
      <table className="results-table">
        <thead>
          <tr>
            <th>{t("runs.colDocument")}</th>
            <th>{t("runs.colCategory")}</th>
            <th>{t("runs.colJustification")}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {filteredResults.map((row) => (
            <tr key={row.id}>
              <td>{row.document_snippet}</td>
              <td>
                {editingId === row.id ? (
                  <select value={editCategoria} onChange={(e) => setEditCategoria(e.target.value)}>
                    {codebookLabels.map((label) => (
                      <option key={label} value={label}>
                        {label}
                      </option>
                    ))}
                  </select>
                ) : (
                  <span className="pill">{row.categoria}</span>
                )}
              </td>
              <td>
                {editingId === row.id ? (
                  <textarea value={editJustificativa} onChange={(e) => setEditJustificativa(e.target.value)} />
                ) : (
                  row.justificativa
                )}
              </td>
              <td>
                {editingId === row.id ? (
                  <button type="button" className="btn" onClick={() => saveEdit(row)}>
                    {t("runs.save")}
                  </button>
                ) : (
                  <button type="button" className="btn-danger-text" onClick={() => startEdit(row)}>
                    {t("runs.edit")}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 2: Verify it type-checks**

From `frontend/`: `npx tsc -b`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/ResultsTable.tsx
git commit -m "feat: add ResultsTable component (filter, inline edit, export)"
```

---

## Task 11: `RunsPage.tsx` — list + detail + polling

**Files:**
- Create: `frontend/src/RunsPage.tsx`

- [ ] **Step 1: Write the component**

Create `frontend/src/RunsPage.tsx`:

```tsx
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { getCodebook, getRun, getRunResults, listCodebooks, listCorpora, listRuns } from "./api";
import type { CodebookSummary, CorpusSummary, ExtractionResult, RunStatus, RunSummary } from "./api";
import { describeApiError } from "./errorMessages";
import { RunForm } from "./RunForm";
import { ResultsTable } from "./ResultsTable";

const ACTIVE_STATUSES = new Set(["pending", "running"]);

export function RunsPage() {
  const { t } = useTranslation();
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [corpora, setCorpora] = useState<CorpusSummary[]>([]);
  const [codebooks, setCodebooks] = useState<CodebookSummary[]>([]);

  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [selectedStatus, setSelectedStatus] = useState<RunStatus | null>(null);
  const [results, setResults] = useState<ExtractionResult[] | null>(null);
  const [codebookLabels, setCodebookLabels] = useState<string[]>([]);
  const [error, setError] = useState<unknown>(null);
  const shownError = error ? describeApiError(error, t) : null;

  const pollRef = useRef<number | null>(null);

  async function refreshRuns() {
    try {
      setRuns(await listRuns());
    } catch (err) {
      setError(err);
    }
  }

  async function loadFormOptions() {
    try {
      const [corporaList, codebooksList] = await Promise.all([listCorpora(), listCodebooks()]);
      setCorpora(corporaList);
      setCodebooks(codebooksList);
    } catch (err) {
      setError(err);
    }
  }

  useEffect(() => {
    refreshRuns();
    loadFormOptions();
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, []);

  function stopPolling() {
    if (pollRef.current) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  async function loadRunDetail(runId: number, codebookId: number) {
    try {
      const status = await getRun(runId);
      setSelectedStatus(status);

      if (ACTIVE_STATUSES.has(status.status)) {
        if (!pollRef.current) {
          pollRef.current = window.setInterval(() => loadRunDetail(runId, codebookId), 2000);
        }
        return;
      }

      stopPolling();
      await refreshRuns();

      if (status.status === "done") {
        const [rows, codebookDetail] = await Promise.all([getRunResults(runId), getCodebook(codebookId)]);
        setResults(rows);
        setCodebookLabels(codebookDetail.spec.categories.map((c) => c.label));
      }
    } catch (err) {
      stopPolling();
      setError(err);
    }
  }

  function selectRun(run: RunSummary) {
    setError(null);
    stopPolling();
    setSelectedRunId(run.id);
    setResults(null);
    setCodebookLabels([]);
    loadRunDetail(run.id, run.codebook_id);
  }

  function startNewRun() {
    setError(null);
    stopPolling();
    setSelectedRunId(null);
    setSelectedStatus(null);
    setResults(null);
  }

  async function handleCreated(runId: number) {
    await refreshRuns();
    const run = (await listRuns()).find((r) => r.id === runId);
    if (run) selectRun(run);
  }

  return (
    <div className="screen">
      {shownError && (
        <div className="banner-error">
          {shownError.message}
          {shownError.detail && <div className="banner-error-detail">{shownError.detail}</div>}
        </div>
      )}

      <div className="runs-layout">
        <section className="card">
          <h2 className="card-title">{t("runs.listTitle")}</h2>
          <button type="button" className="btn btn-ghost" onClick={startNewRun}>
            {t("runs.newRun")}
          </button>
          {runs.length === 0 ? (
            <p className="empty-state">{t("runs.none")}</p>
          ) : (
            <ul className="codebook-list">
              {runs.map((r) => (
                <li key={r.id}>
                  <button type="button" onClick={() => selectRun(r)}>
                    #{r.id} {r.codebook_name} · {r.corpus_id} <span className="pill">{r.status}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <div className="card">
          {selectedRunId === null && (
            <RunForm corpora={corpora} codebooks={codebooks} onCreated={handleCreated} onError={setError} />
          )}

          {selectedRunId !== null && selectedStatus && ACTIVE_STATUSES.has(selectedStatus.status) && (
            <div>
              <h3 className="card-title">{t("runs.inProgress")}</h3>
              <div className="progress-track">
                <div
                  className="progress-fill"
                  style={{
                    width:
                      selectedStatus.total > 0
                        ? `${(selectedStatus.processed / selectedStatus.total) * 100}%`
                        : "0%",
                  }}
                />
              </div>
              <p className="empty-state">
                {selectedStatus.processed} / {selectedStatus.total}
              </p>
            </div>
          )}

          {selectedRunId !== null && selectedStatus?.status === "error" && (
            <div className="banner-error">{t("runs.runFailed")}</div>
          )}

          {selectedRunId !== null && results && (
            <ResultsTable
              runId={selectedRunId}
              results={results}
              codebookLabels={codebookLabels}
              onResultsChange={setResults}
              onError={setError}
            />
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify it type-checks**

From `frontend/`: `npx tsc -b`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/RunsPage.tsx
git commit -m "feat: add RunsPage (list + detail + live polling)"
```

---

## Task 12: wire the third tab into `App.tsx`

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Add the tab**

Replace the full contents of `frontend/src/App.tsx` with:

```tsx
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { CodebookEditor } from "./CodebookEditor";
import { CorpusPage } from "./CorpusPage";
import { RunsPage } from "./RunsPage";

type Tab = "corpus" | "codebook" | "runs";

function App() {
  const { t, i18n } = useTranslation();
  const [tab, setTab] = useState<Tab>("corpus");

  return (
    <>
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark">C</span>
          <span className="app-title">{t("app.title")}</span>
          <span className="app-tagline">{t("app.tagline")}</span>
        </div>
        <div className="header-controls">
          <div className="seg">
            <button className="seg-btn" disabled={tab === "corpus"} onClick={() => setTab("corpus")}>
              {t("app.nav.corpus")}
            </button>
            <span className="seg-sep" />
            <button className="seg-btn" disabled={tab === "codebook"} onClick={() => setTab("codebook")}>
              {t("app.nav.codebook")}
            </button>
            <span className="seg-sep" />
            <button className="seg-btn" disabled={tab === "runs"} onClick={() => setTab("runs")}>
              {t("app.nav.runs")}
            </button>
          </div>
          <div className="seg" aria-label="Language">
            <button
              className="seg-btn"
              disabled={i18n.resolvedLanguage === "pt-BR"}
              onClick={() => i18n.changeLanguage("pt-BR")}
            >
              PT
            </button>
            <span className="seg-sep" />
            <button
              className="seg-btn"
              disabled={i18n.resolvedLanguage === "en"}
              onClick={() => i18n.changeLanguage("en")}
            >
              EN
            </button>
          </div>
        </div>
      </header>
      <main className="app-main">
        {tab === "corpus" && <CorpusPage />}
        {tab === "codebook" && <CodebookEditor />}
        {tab === "runs" && <RunsPage />}
      </main>
    </>
  );
}

export default App;
```

**Before this step**, re-read the current `frontend/src/App.tsx` — another session may have changed its header/nav shape since this plan was written (it already added a language toggle after this plan's spec was drafted). If the live file differs from what's shown above, adapt this change to add only the `runs` tab button and the `{tab === "runs" && <RunsPage />}` branch, preserving whatever else is there — don't blindly overwrite an unrelated change.

- [ ] **Step 2: Verify it type-checks and builds**

From `frontend/`: `npm run build`
Expected: no TypeScript errors, `frontend/dist/` written

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: wire Runs tab into App.tsx"
```

---

## Task 13: manual end-to-end verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend test suite**

Run: `pytest -v`
Expected: all pass

- [ ] **Step 2: Start both servers**

Run: `scripts/dev.sh` (or `powershell -File scripts/dev.ps1`) — use non-default ports if 8000/5173 are occupied by another session's servers (check first: `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/corpora`; a `200` means something's already there).

- [ ] **Step 3: Create a codebook and a corpus to run against, if none exist**

Via the Corpus and Codebook tabs in the browser, or reuse existing ones already in the shared `codifica.sqlite` if another session left some — check the Corpus tab's "Existing corpora" list first rather than assuming it's empty.

- [ ] **Step 4: Create a run in CLI mode**

On the Runs tab, click "+ New run", pick the corpus and codebook, leave the model field as-is or set it, choose "CLI" as the provider, and enter a real installed CLI command (`claude -p`, confirmed working in Slice 1/2; or `agy -p` with prompt mode "arg" if available — confirm with `which agy` first). Submit.

Expected: the run appears in the list with status `pending`/`running`, a progress bar appears and advances every ~2 seconds, and once all documents are processed the view switches to the results table automatically.

- [ ] **Step 5: Exercise the Results table**

Confirm: the category filter dropdown shows the codebook's real labels (not just labels seen in the results so far); selecting one filters the table; clicking "Edit" on a row switches its category/justification to editable inputs; "Save" persists the change (confirm by reloading the run from the list — the edit should still be there); the three export links each download a file that opens/parses correctly (CSV in a text editor or spreadsheet app, XLSX in a spreadsheet app, JSON in a text editor).

- [ ] **Step 6: Check the browser console**

No errors during any of the above (use the same check as Slice 2: `read_console_messages` with `onlyErrors: true` if driving this via the Claude Browser pane).

- [ ] **Step 7: Confirm the language toggle still covers the new screen**

Switch to PT and back to EN on the Runs tab specifically — every label should translate (this is what Task 7's locale keys are for).

---

## Task 14: close out the slice — `TODO.md`, `NEWS.md`

**Files:**
- Modify: `TODO.md`
- Modify: `NEWS.md`

- [ ] **Step 1: Update `TODO.md`**

**Before editing**, re-read `TODO.md` — other sessions have been actively appending to it (per governance, always append, never edit others' entries in place). Remove the "Run + Results screens (Screens 3-4)..." line from `## Pending` (only that line — leave any other pending items other sessions have added alone), and add under `## Done`:

```markdown
- 2026-09-01 — Slice 3, Runs + Results screen: a "Runs" tab (list +
  detail: create a run in API-key or CLI mode, live progress polling,
  results table with category filter, inline categoria/justificativa
  edit, CSV/XLSX/JSON export). New backend: `GET /runs`,
  `PUT /runs/{id}/results/{id}`, `GET /runs/{id}/export`, and
  `GET /runs/{id}/results` now includes a `document_snippet`. Screen 5
  (Validation — gold labels, Cohen's kappa, disagreement review) remains
  a separate Slice 4. Design:
  `docs/superpowers/specs/2026-09-01-slice-3-runs-results-screen-design.md`.
```

Also add to `## Pending`:

```markdown
- Validation screen (Screen 5) — gold-label import, Cohen's kappa (the
  metric `agreement_report()` already computes) surfaced in the UI,
  category-level precision/recall/F1, and a disagreement-review list.
  Gets its own spec/plan per `AGENTS.md` § "Build order for the MVP".
```

- [ ] **Step 2: Update `NEWS.md`**

**Before editing**, re-read `NEWS.md` for the same reason. Add a new dated section at the top (matching the existing entries' style — check whether today's date already has entries from other sessions, and if so use the next available `(N)` suffix rather than colliding with theirs) summarizing this slice: the Runs tab, what it does, the three new/extended backend endpoints, and that Validation is next.

- [ ] **Step 3: Commit**

```bash
git add TODO.md NEWS.md
git commit -m "docs: close out Slice 3 (Runs + Results screen)"
```

---

## Self-Review Notes

- **Spec coverage**: every design-spec requirement has a task — the three
  backend endpoints and the results-endpoint extension (Tasks 2-5), the
  API client (Task 6), the one-tab list+detail IA with all three states
  (Tasks 9-11), category filter + inline edit + all three export formats
  (Task 10), locale coverage (Task 7), and manual verification including
  the language toggle (Task 13).
- **Concurrency discipline**: Task 12 explicitly calls out re-reading
  `App.tsx` before overwriting it, since another session already changed
  it once during this plan's own drafting; Task 14 calls out the same for
  `TODO.md`/`NEWS.md`, which are append-only by convention specifically
  because multiple sessions write to them.
- **Not in this plan** (explicitly Slice 4 per the design spec and
  `AGENTS.md`): the Validation screen, token-cost estimation, deleting or
  re-running a run, editing `trecho_evidencia`.
