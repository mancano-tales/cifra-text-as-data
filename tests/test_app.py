from fastapi.testclient import TestClient
from sqlmodel import Session

from text_as_data.app import app, get_engine_dependency, get_provider_dependency
from text_as_data.db import CodebookRecord, DocumentRecord, get_engine
from text_as_data.providers import Provider

YAML_SOURCE = """
concept: test_concept
description: "A test codebook."
categories:
  - label: yes
    definition: "Positive case."
  - label: no
    definition: "Negative case."
"""


class FakeProvider(Provider):
    def extract(self, messages, schema):
        return schema(categoria="yes", justificativa="because", trecho_evidencia="quote")


def _make_test_client():
    engine = get_engine("sqlite://")
    with Session(engine) as session:
        codebook = CodebookRecord(name="test", yaml_raw=YAML_SOURCE)
        session.add(codebook)
        session.add(DocumentRecord(corpus_id="test_corpus", text="doc 1"))
        session.commit()
        session.refresh(codebook)
        codebook_id = codebook.id

    app.dependency_overrides[get_engine_dependency] = lambda: engine
    app.dependency_overrides[get_provider_dependency] = lambda: FakeProvider()
    return TestClient(app), codebook_id


def test_post_runs_then_get_results():
    client, codebook_id = _make_test_client()

    response = client.post(
        "/runs", json={"codebook_id": codebook_id, "corpus_id": "test_corpus", "model": "fake-model"}
    )
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    status = client.get(f"/runs/{run_id}").json()
    assert status["status"] == "done"
    assert status["processed"] == 1
    assert status["total"] == 1

    results = client.get(f"/runs/{run_id}/results").json()
    assert len(results) == 1
    assert results[0]["categoria"] == "yes"


def test_post_runs_with_unknown_codebook_returns_404():
    client, _ = _make_test_client()

    response = client.post("/runs", json={"codebook_id": 999, "corpus_id": "test_corpus", "model": "fake-model"})

    assert response.status_code == 404


def test_get_results_for_unknown_run_returns_404():
    client, _ = _make_test_client()

    response = client.get("/runs/999/results")

    assert response.status_code == 404


def test_get_provider_dependency_builds_provider_for_the_requested_model(monkeypatch):
    from text_as_data.app import CreateRunRequest, get_provider_dependency

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-a-real-secret")
    request = CreateRunRequest(codebook_id=1, corpus_id="c", model="claude-haiku-4-5")

    provider = get_provider_dependency(request)

    assert provider._model == "claude-haiku-4-5"
