import io
import json

import openpyxl
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from text_as_data.app import app, get_engine_dependency
from text_as_data.db import DocumentRecord, get_engine


def _make_test_client():
    engine = get_engine("sqlite://")
    app.dependency_overrides[get_engine_dependency] = lambda: engine
    return TestClient(app), engine


def _make_xlsx_bytes(rows: list[list]) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_paste_creates_one_document_corpus():
    client, engine = _make_test_client()

    response = client.post("/corpora/paste", json={"name": "my_notes", "text": "some pasted text"})

    assert response.status_code == 200
    assert response.json() == {"corpus_id": "my_notes", "document_count": 1}
    with Session(engine) as session:
        docs = session.exec(select(DocumentRecord).where(DocumentRecord.corpus_id == "my_notes")).all()
        assert len(docs) == 1
        assert docs[0].text == "some pasted text"


def test_paste_rejects_duplicate_corpus_name():
    client, _ = _make_test_client()
    client.post("/corpora/paste", json={"name": "dup", "text": "first"})

    response = client.post("/corpora/paste", json={"name": "dup", "text": "second"})

    assert response.status_code == 409


def test_csv_upload_creates_documents_from_text_column():
    client, engine = _make_test_client()
    csv_content = b"title,body\nA,First doc\nB,Second doc\n"

    response = client.post(
        "/corpora/csv",
        data={"name": "articles", "text_column": "body"},
        files={"file": ("articles.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 200
    assert response.json() == {"corpus_id": "articles", "document_count": 2}
    with Session(engine) as session:
        docs = session.exec(select(DocumentRecord).where(DocumentRecord.corpus_id == "articles")).all()
        assert sorted(d.text for d in docs) == ["First doc", "Second doc"]


def test_csv_upload_rejects_unknown_text_column():
    client, _ = _make_test_client()
    csv_content = b"title,body\nA,First doc\n"

    response = client.post(
        "/corpora/csv",
        data={"name": "articles", "text_column": "nope"},
        files={"file": ("articles.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 422


def test_csv_upload_with_extra_trailing_fields_reports_clean_422_not_crash():
    # csv.DictReader collects columns beyond the header count under a
    # `None` key -- an unrecognized text_column error detail that sorts
    # rows[0].keys() would otherwise raise a raw TypeError (str vs None)
    # instead of this 422.
    client, _ = _make_test_client()
    csv_content = b"title,body\nA,First doc,extra,fields\n"

    response = client.post(
        "/corpora/csv",
        data={"name": "ragged", "text_column": "nope"},
        files={"file": ("ragged.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 422
    assert "nope" in response.json()["detail"]


def test_csv_upload_keeps_rows_whose_text_column_is_numeric_zero():
    client, engine = _make_test_client()
    csv_content = b"score,body\n0,First doc\n1,Second doc\n"

    response = client.post(
        "/corpora/csv",
        data={"name": "scores", "text_column": "score"},
        files={"file": ("scores.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 200
    assert response.json()["document_count"] == 2
    with Session(engine) as session:
        docs = session.exec(select(DocumentRecord).where(DocumentRecord.corpus_id == "scores")).all()
        assert sorted(d.text for d in docs) == ["0", "1"]


def test_paste_rejects_empty_text_instead_of_creating_a_phantom_corpus():
    client, _ = _make_test_client()

    response = client.post("/corpora/paste", json={"name": "empty_notes", "text": ""})

    assert response.status_code == 400


def test_csv_upload_rejects_when_every_row_is_empty_instead_of_creating_a_phantom_corpus():
    client, _ = _make_test_client()
    csv_content = b"title,body\nA,\nB,\n"

    response = client.post(
        "/corpora/csv",
        data={"name": "all_blank", "text_column": "body"},
        files={"file": ("all_blank.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 400


def test_xlsx_upload_creates_documents_from_text_column():
    client, engine = _make_test_client()
    xlsx_content = _make_xlsx_bytes([["title", "body"], ["A", "First doc"], ["B", "Second doc"]])

    response = client.post(
        "/corpora/xlsx",
        data={"name": "spreadsheet_corpus", "text_column": "body"},
        files={
            "file": (
                "corpus.xlsx",
                xlsx_content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200
    assert response.json() == {"corpus_id": "spreadsheet_corpus", "document_count": 2}


def test_xlsx_upload_rejects_corrupt_file():
    client, _ = _make_test_client()

    response = client.post(
        "/corpora/xlsx",
        data={"name": "broken", "text_column": "body"},
        files={"file": ("broken.xlsx", b"not a real xlsx file", "application/octet-stream")},
    )

    assert response.status_code == 400


def test_list_corpora_returns_counts_ordered_by_creation():
    client, _ = _make_test_client()
    client.post("/corpora/paste", json={"name": "first", "text": "a"})
    client.post("/corpora/paste", json={"name": "second", "text": "b"})
    client.post(
        "/corpora/csv",
        data={"name": "third", "text_column": "body"},
        files={"file": ("f.csv", b"body\nx\ny\n", "text/csv")},
    )

    response = client.get("/corpora")

    assert response.status_code == 200
    assert response.json() == [
        {"corpus_id": "first", "document_count": 1},
        {"corpus_id": "second", "document_count": 1},
        {"corpus_id": "third", "document_count": 2},
    ]


def test_list_corpus_documents_paginates():
    client, _ = _make_test_client()
    csv_content = b"body\nrow0\nrow1\nrow2\n"
    client.post(
        "/corpora/csv",
        data={"name": "paged", "text_column": "body"},
        files={"file": ("f.csv", csv_content, "text/csv")},
    )

    response = client.get("/corpora/paged/documents?limit=2&offset=1")

    assert response.status_code == 200
    assert [d["text"] for d in response.json()] == ["row1", "row2"]


def test_list_corpus_documents_rejects_negative_offset():
    client, _ = _make_test_client()
    client.post("/corpora/paste", json={"name": "neg_offset", "text": "a"})

    response = client.get("/corpora/neg_offset/documents?offset=-1")

    # Previously: SQLite rejects a negative OFFSET clause with an
    # sqlite3.OperationalError, surfacing as an unhandled 500.
    assert response.status_code == 422


def test_list_corpus_documents_rejects_an_excessive_limit():
    client, _ = _make_test_client()
    client.post("/corpora/paste", json={"name": "big_limit", "text": "a"})

    response = client.get("/corpora/big_limit/documents?limit=10000000")

    assert response.status_code == 422


def test_list_corpus_documents_404_for_unknown_corpus():
    client, _ = _make_test_client()

    response = client.get("/corpora/does-not-exist/documents")

    assert response.status_code == 404


def _docx_bytes(text: str) -> bytes:
    import docx

    document = docx.Document()
    document.add_paragraph(text)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_documents_upload_accepts_a_mixed_txt_and_docx_batch():
    client, engine = _make_test_client()

    response = client.post(
        "/corpora/documents",
        data={"name": "mixed_batch"},
        files=[
            ("files", ("interview1.txt", b"Plain text interview.", "text/plain")),
            ("files", ("interview2.docx", _docx_bytes("Word interview."), "application/octet-stream")),
        ],
    )

    assert response.status_code == 200
    assert response.json()["document_count"] == 2
    with Session(engine) as session:
        docs = session.exec(select(DocumentRecord).where(DocumentRecord.corpus_id == "mixed_batch")).all()
        texts = sorted(d.text for d in docs)
        assert texts == ["Plain text interview.", "Word interview."]
        filenames = sorted(json.loads(d.metadata_json)["filename"] for d in docs)
        assert filenames == ["interview1.txt", "interview2.docx"]


def test_documents_upload_rejects_unsupported_extension():
    client, _ = _make_test_client()

    response = client.post(
        "/corpora/documents",
        data={"name": "bad_batch"},
        files=[("files", ("notes.exe", b"whatever", "application/octet-stream"))],
    )

    assert response.status_code == 422


def test_documents_upload_rejects_corrupt_docx():
    client, _ = _make_test_client()

    response = client.post(
        "/corpora/documents",
        data={"name": "broken_batch"},
        files=[("files", ("broken.docx", b"not a real docx file", "application/octet-stream"))],
    )

    assert response.status_code == 400


def test_documents_upload_409_on_duplicate_corpus_name():
    client, _ = _make_test_client()
    client.post(
        "/corpora/documents", data={"name": "dup_docs"}, files=[("files", ("a.txt", b"a", "text/plain"))]
    )

    response = client.post(
        "/corpora/documents", data={"name": "dup_docs"}, files=[("files", ("b.txt", b"b", "text/plain"))]
    )

    assert response.status_code == 409
