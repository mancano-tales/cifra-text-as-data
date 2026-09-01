from sqlmodel import Session

from text_as_data.db import CodebookRecord, DocumentRecord, ExtractionRecord, RunRecord, get_engine


def test_round_trip_through_all_four_tables():
    engine = get_engine("sqlite://")

    with Session(engine, expire_on_commit=False) as session:
        codebook = CodebookRecord(name="h1_a", yaml_raw="concept: x")
        session.add(codebook)
        session.commit()
        session.refresh(codebook)

        document = DocumentRecord(corpus_id="v7_pilot", text="some evidence text")
        session.add(document)
        session.commit()
        session.refresh(document)

        run = RunRecord(codebook_id=codebook.id, corpus_id="v7_pilot", model="claude-sonnet-5")
        session.add(run)
        session.commit()
        session.refresh(run)

        extraction = ExtractionRecord(
            run_id=run.id,
            document_id=document.id,
            categoria="quase_certa",
            justificativa="because...",
            trecho_evidencia="the quoted span",
        )
        session.add(extraction)
        session.commit()
        session.refresh(extraction)

    with Session(engine, expire_on_commit=False) as session:
        loaded = session.get(ExtractionRecord, extraction.id)
        assert loaded.categoria == "quase_certa"
        assert loaded.run_id == run.id
        assert loaded.document_id == document.id

    with Session(engine, expire_on_commit=False) as session:
        loaded_run = session.get(RunRecord, run.id)
        assert loaded_run.status == "pending"
        assert loaded_run.codebook_id == codebook.id
