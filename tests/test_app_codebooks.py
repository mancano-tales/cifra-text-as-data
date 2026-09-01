import yaml
from fastapi.testclient import TestClient

from text_as_data.app import app, get_engine_dependency
from text_as_data.db import get_engine

VALID_SPEC = {
    "concept": "protest",
    "description": "A collective, public event.",
    "categories": [
        {
            "label": "protest",
            "definition": "An occupation, march, or strike.",
            "positive_examples": ["200 people occupied the square."],
        },
        {"label": "not_protest", "definition": "Any event that does not meet the criteria above."},
    ],
}


def _make_test_client():
    engine = get_engine("sqlite://")
    app.dependency_overrides[get_engine_dependency] = lambda: engine
    return TestClient(app)


def test_create_codebook_then_get_it_back():
    client = _make_test_client()

    create_response = client.post("/codebooks", json=VALID_SPEC)
    assert create_response.status_code == 200
    codebook_id = create_response.json()["id"]

    get_response = client.get(f"/codebooks/{codebook_id}")
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["name"] == "protest"
    assert body["spec"]["concept"] == "protest"
    assert [c["label"] for c in body["spec"]["categories"]] == ["protest", "not_protest"]
    assert yaml.safe_load(body["yaml_raw"])["concept"] == "protest"


def test_create_codebook_rejects_duplicate_labels():
    client = _make_test_client()
    bad_spec = {**VALID_SPEC, "categories": [VALID_SPEC["categories"][0], VALID_SPEC["categories"][0]]}

    response = client.post("/codebooks", json=bad_spec)

    assert response.status_code == 422


def test_list_codebooks_returns_created_ones():
    client = _make_test_client()
    client.post("/codebooks", json=VALID_SPEC)

    response = client.get("/codebooks")

    assert response.status_code == 200
    assert response.json()[0]["name"] == "protest"


def test_get_unknown_codebook_returns_404():
    client = _make_test_client()

    response = client.get("/codebooks/999")

    assert response.status_code == 404


def test_update_codebook_overwrites_spec_and_yaml():
    client = _make_test_client()
    codebook_id = client.post("/codebooks", json=VALID_SPEC).json()["id"]
    updated_spec = {**VALID_SPEC, "description": "An updated description."}

    response = client.put(f"/codebooks/{codebook_id}", json=updated_spec)

    assert response.status_code == 200
    body = client.get(f"/codebooks/{codebook_id}").json()
    assert body["spec"]["description"] == "An updated description."


def test_update_unknown_codebook_returns_404():
    client = _make_test_client()

    response = client.put("/codebooks/999", json=VALID_SPEC)

    assert response.status_code == 404
