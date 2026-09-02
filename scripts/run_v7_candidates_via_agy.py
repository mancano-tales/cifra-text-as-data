"""Run the 16 candidate V7 evidence/hypothesis-pair evaluations through the
real Cifra pipeline (codebook -> DB -> run_extraction -> CliProvider),
using Google Antigravity's `agy` CLI instead of Claude.

This replaces the earlier hand-drafted classifications (data/
v7_pilot_draft_classifications.csv) with actual LLM output from the real
extraction engine -- the point being to exercise Cifra itself, not to have
an agent eyeball each article and write down a guess.

Usage:
    python scripts/run_v7_candidates_via_agy.py
"""

from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlmodel import Session, select  # noqa: E402

from text_as_data.codebook import spec_to_yaml_string  # noqa: E402
from text_as_data.db import CodebookRecord, DocumentRecord, ExtractionRecord, RunRecord, get_engine  # noqa: E402
from text_as_data.extraction import run_extraction  # noqa: E402
from text_as_data.pilot_v7 import VERBAL_PROBABILITY_DEFINITIONS, VERBAL_PROBABILITY_LABELS  # noqa: E402
from text_as_data.providers import CliProvider  # noqa: E402

SCRATCH = Path(
    "C:/Users/Mancano/AppData/Local/Temp/claude/"
    "C--Users-Mancano-Documents-MancanoSync-text-as-data/"
    "64bf4a45-2f26-4117-8f92-ab0c1cf78c1f/scratchpad"
)

HYPOTHESES = {
    "H1": ("Conditional Partisan Expansion", "De-commodification as Redistributive Mechanism"),
    "H2": ("Strict Partisan-Primacy", "Co-production by Plural Non-Partisan Actors"),
    "H3": ("Ideological Preference for Private Provision", "Path Dependence and Fiscal Constraint"),
}

# (fk_id_ev, hypothesis_pair)
ASSIGNMENTS = [
    ("2013-08-04_FSP_0008_associacao_brasileira_de_mante", "H1"),
    ("2015-06-26_FSP_0022_associacao_brasileira_de_mante", "H1"),
    ("2016-07-16_FSP_0025_associacao_brasileira_de_mante", "H1"),
    ("2017-11-22_FSP_0327_associacao_brasileira_de_mante", "H1"),
    ("2024-02-16_FSP_0306_associacao_brasileira_de_mante", "H1"),
    ("2006-07-04_FSP_0067_eunice_durham_ministerio", "H1"),
    ("2003-12-01_FSP_0047_edson_franco_mantenedoras", "H2"),
    ("2006-05-10_FSP_0066_associacao_brasileira_de_mante", "H2"),
    ("2015-06-27_FSP_0023_associacao_brasileira_de_mante", "H2"),
    ("2022-05-01_FSP_0257_associacao_brasileira_de_mante", "H2"),
    ("2023-08-17_FSP_0262_associacao_brasileira_de_mante", "H2"),
    ("2001-07-23_FSP_0037_eunice_durham_ministerio", "H3"),
    ("2004-02-16_FSP_0055_edson_franco_mantenedoras", "H3"),
    ("2019-06-06_FSP_0274_associacao_brasileira_de_mante", "H3"),
    ("2020-12-01_FSP_0290_associacao_brasileira_de_mante", "H3"),
    ("2024-02-16_FSP_0306_associacao_brasileira_de_mante", "H3"),
]


def write_codebook_yaml(pair_code: str, side_label: str, hypothesis_name: str, other_side_name: str) -> str:
    categories = [
        {"label": label, "definition": VERBAL_PROBABILITY_DEFINITIONS[label]} for label in VERBAL_PROBABILITY_LABELS
    ]
    spec = {
        "concept": f"{pair_code}_{side_label}_probability",
        "description": (
            f"Inhabit the world of the hypothesis '{hypothesis_name}' and ask: if this "
            "hypothesis were true, how expected would this evidence be? (Fairfield & "
            f"Charman 2022.) The competing hypothesis in this pair is '{other_side_name}' "
            "-- do not evaluate that one here, only the probability of the evidence under "
            f"'{hypothesis_name}'."
        ),
        "categories": categories,
    }
    return spec_to_yaml_string(spec)


def main() -> None:
    with open(SCRATCH / "v7_candidates_full.json", encoding="utf-8") as f:
        docs = json.load(f)

    db_path = Path("data/v7_candidates.sqlite")
    if db_path.exists():
        db_path.unlink()
    engine = get_engine(f"sqlite:///{db_path}")

    provider = CliProvider(command=["agy", "-p"], prompt_mode="arg", timeout=300)

    run_ids_by_pair_side: dict[tuple[str, str], int] = {}

    with Session(engine) as session:
        for pair_code, (name_a, name_b) in HYPOTHESES.items():
            corpus_id = f"v7_candidates_{pair_code}"
            doc_ids_for_pair = []
            for fk_id_ev, pair in ASSIGNMENTS:
                if pair != pair_code:
                    continue
                d = docs[fk_id_ev]
                doc = DocumentRecord(
                    corpus_id=corpus_id,
                    text=d["complete_evidence_content"],
                    metadata_json=json.dumps({"fk_id_ev": fk_id_ev, "title": d["evidence_title"]}),
                )
                session.add(doc)
                session.flush()
                doc_ids_for_pair.append(doc.id)

            for side_label, side_name, other_name in (("a", name_a, name_b), ("b", name_b, name_a)):
                yaml_raw = write_codebook_yaml(pair_code, side_label, side_name, other_name)
                codebook = CodebookRecord(name=f"{pair_code}_{side_label}", yaml_raw=yaml_raw)
                session.add(codebook)
                session.flush()

                run = RunRecord(codebook_id=codebook.id, corpus_id=corpus_id, model="agy-gemini")
                session.add(run)
                session.flush()
                run_ids_by_pair_side[(pair_code, side_label)] = run.id

        session.commit()

    print(f"Seeded {len(ASSIGNMENTS)} documents and {len(run_ids_by_pair_side)} runs into {db_path}")

    for (pair_code, side_label), run_id in run_ids_by_pair_side.items():
        print(f"--- running {pair_code} side {side_label} (run_id={run_id}) ---", flush=True)
        t0 = time.time()
        try:
            run_extraction(engine, run_id, provider)
        except Exception as exc:  # noqa: BLE001 -- report and continue to the next run
            print(f"  run {run_id} raised: {exc}")
        print(f"  done in {time.time() - t0:.1f}s", flush=True)

    with Session(engine) as session:
        rows = []
        for (pair_code, side_label), run_id in run_ids_by_pair_side.items():
            extractions = session.exec(select(ExtractionRecord).where(ExtractionRecord.run_id == run_id)).all()
            for ext in extractions:
                doc = session.get(DocumentRecord, ext.document_id)
                meta = json.loads(doc.metadata_json)
                rows.append(
                    {
                        "fk_id_ev": meta["fk_id_ev"],
                        "title": meta["title"],
                        "hypothesis_pair": pair_code,
                        "side": side_label,
                        "agy_categoria": ext.categoria,
                        "agy_justificativa": ext.justificativa,
                        "agy_trecho_evidencia": ext.trecho_evidencia,
                    }
                )

    out_path = Path("data/v7_candidates_agy_results.csv")
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "fk_id_ev",
                "title",
                "hypothesis_pair",
                "side",
                "agy_categoria",
                "agy_justificativa",
                "agy_trecho_evidencia",
            ],
        )
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {len(rows)} results to {out_path}")


if __name__ == "__main__":
    main()
