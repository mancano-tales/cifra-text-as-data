from __future__ import annotations

import ftfy

VERBAL_PROBABILITY_LABELS = [
    "quase_certa",
    "muito_provavel",
    "provavel",
    "cinquenta_e_cinquenta",
    "improvavel",
    "muito_improvavel",
    "quase_impossivel",
]

VERBAL_PROBABILITY_DEFINITIONS = {
    "quase_certa": "Quase certamente observaríamos esta evidência se a hipótese fosse verdadeira (~0.95).",
    "muito_provavel": "Muito provavelmente observaríamos esta evidência (~0.80).",
    "provavel": "Provavelmente observaríamos esta evidência (~0.65).",
    "cinquenta_e_cinquenta": "Poderia ou não ocorrer — a evidência não discrimina entre as hipóteses (~0.50).",
    "improvavel": "Improvável, mas possível, observar esta evidência (~0.35).",
    "muito_improvavel": "Muito improvável observar esta evidência se a hipótese fosse verdadeira (~0.20).",
    "quase_impossivel": "Quase impossível observar esta evidência sob esta hipótese — hoop test (~0.05).",
}


def fix_mojibake(text: str) -> str:
    """Repair text corrupted by a wrong-codec round-trip during the original
    Folha scrape (e.g. `institui\\xe7\\xf5es` instead of `instituições`)."""
    return ftfy.fix_text(text)


def build_hypothesis_lookup(tb1_rows: list[dict]) -> dict[str, tuple[str, str]]:
    """Group tb1_hypotheses rows by `hypothesis_group_id` and return
    {pair_code: (side_a_name, side_b_name)} keyed by the pair's number
    (e.g. "H1"), sorted by pk_hyp_pair_code so side 'a' always comes first.
    Only pairs with exactly two rows are included."""
    by_group: dict[int, list[dict]] = {}
    for row in tb1_rows:
        # openpyxl often returns numeric cells as floats (e.g. 1.0 instead
        # of 1); coerce to int so f"H{group_id}" produces "H1", not "H1.0".
        by_group.setdefault(int(row["hypothesis_group_id"]), []).append(row)

    lookup: dict[str, tuple[str, str]] = {}
    for group_id, rows in by_group.items():
        if len(rows) != 2:
            continue
        rows = sorted(rows, key=lambda r: r["pk_hyp_pair_code"])
        pair_code = f"H{group_id}"
        lookup[pair_code] = (rows[0]["hypothesis_name"], rows[1]["hypothesis_name"])
    return lookup


def select_gold_rows(
    tb4_rows: list[dict], hypothesis_lookup: dict[str, tuple[str, str]]
) -> tuple[list[dict], list[dict]]:
    """Split tb4_evidence_analisys rows into (kept, skipped).

    Kept: both prob_e_dado_h1 and prob_e_dado_h2 are filled, AND
    fk_hypothesis_group resolves to a real pair definition in
    hypothesis_lookup (built from tb1_hypotheses). Skipped: everything
    else — most commonly, rows tagged with an old free-text group label
    (e.g. "H_nao_partidaria") that isn't a resolvable pair code."""
    kept, skipped = [], []
    for row in tb4_rows:
        has_both_probs = bool(row.get("prob_e_dado_h1")) and bool(row.get("prob_e_dado_h2"))
        resolvable = row.get("fk_hypothesis_group") in hypothesis_lookup
        (kept if has_both_probs and resolvable else skipped).append(row)
    return kept, skipped
