from text_as_data.pilot_v7 import (
    VERBAL_PROBABILITY_LABELS,
    build_hypothesis_lookup,
    fix_mojibake,
    select_gold_rows,
)


def test_fix_mojibake_repairs_corrupted_portuguese_text():
    # Real corruption pattern from the V7 workbook: UTF-8 bytes misread as
    # Latin-1 during the original Folha scrape — a lossless round-trip, so
    # the original text is fully recoverable.
    original = "instituições públicas"
    corrupted = original.encode("utf-8").decode("latin-1")
    assert fix_mojibake(corrupted) == original


def test_build_hypothesis_lookup_from_tb1_rows():
    tb1_rows = [
        {
            "pk_hyp_pair_code": "H1a",
            "hypothesis_name": "Conditional Partisan Expansion",
            "hypothesis_group_id": 1,
        },
        {
            "pk_hyp_pair_code": "H1b",
            "hypothesis_name": "De-commodification as Redistributive Mechanism",
            "hypothesis_group_id": 1,
        },
        {
            "pk_hyp_pair_code": "H3a",
            "hypothesis_name": "Ideological Preference for Private Provision",
            "hypothesis_group_id": 3,
        },
        {
            "pk_hyp_pair_code": "H3b",
            "hypothesis_name": "Path Dependence and Fiscal Constraint",
            "hypothesis_group_id": 3,
        },
    ]

    lookup = build_hypothesis_lookup(tb1_rows)

    assert lookup["H1"] == ("Conditional Partisan Expansion", "De-commodification as Redistributive Mechanism")
    assert lookup["H3"] == ("Ideological Preference for Private Provision", "Path Dependence and Fiscal Constraint")
    assert "H_nao_partidaria" not in lookup


def test_build_hypothesis_lookup_coerces_float_group_id_from_openpyxl():
    # openpyxl often returns numeric cells as floats (e.g. 1.0 instead of
    # 1). Without coercion, f"H{group_id}" would produce "H1.0" instead of
    # "H1", silently breaking matching against tb4's plain "H1"/"H3" values.
    tb1_rows = [
        {
            "pk_hyp_pair_code": "H1a",
            "hypothesis_name": "Conditional Partisan Expansion",
            "hypothesis_group_id": 1.0,
        },
        {
            "pk_hyp_pair_code": "H1b",
            "hypothesis_name": "De-commodification as Redistributive Mechanism",
            "hypothesis_group_id": 1.0,
        },
        {
            "pk_hyp_pair_code": "H3a",
            "hypothesis_name": "Ideological Preference for Private Provision",
            "hypothesis_group_id": 3.0,
        },
        {
            "pk_hyp_pair_code": "H3b",
            "hypothesis_name": "Path Dependence and Fiscal Constraint",
            "hypothesis_group_id": 3.0,
        },
    ]

    lookup = build_hypothesis_lookup(tb1_rows)

    assert set(lookup.keys()) == {"H1", "H3"}
    assert "H1.0" not in lookup


def test_select_gold_rows_keeps_only_resolvable_pairs_with_both_probs():
    tb4_rows = [
        {"fk_id_ev": "ev1", "fk_hypothesis_group": "H1", "prob_e_dado_h1": "provavel", "prob_e_dado_h2": "improvavel"},
        {"fk_id_ev": "ev2", "fk_hypothesis_group": "H_nao_partidaria", "prob_e_dado_h1": "provavel", "prob_e_dado_h2": "provavel"},
        {"fk_id_ev": "ev3", "fk_hypothesis_group": "H3", "prob_e_dado_h1": None, "prob_e_dado_h2": "provavel"},
        {"fk_id_ev": "ev4", "fk_hypothesis_group": "H3", "prob_e_dado_h1": "quase_certa", "prob_e_dado_h2": "quase_impossivel"},
    ]
    lookup = {"H1": ("A", "B"), "H3": ("C", "D")}

    kept, skipped = select_gold_rows(tb4_rows, lookup)

    assert [r["fk_id_ev"] for r in kept] == ["ev1", "ev4"]
    assert [r["fk_id_ev"] for r in skipped] == ["ev2", "ev3"]


def test_verbal_probability_labels_has_seven_levels_in_scale_order():
    assert VERBAL_PROBABILITY_LABELS == [
        "quase_certa",
        "muito_provavel",
        "provavel",
        "cinquenta_e_cinquenta",
        "improvavel",
        "muito_improvavel",
        "quase_impossivel",
    ]
