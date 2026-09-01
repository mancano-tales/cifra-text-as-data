import pytest

from text_as_data import Codebook

YAML_SOURCE = """
concept: protest
description: >
  A collective, public event expressing a political or social claim,
  involving at least two people.
categories:
  - label: protest
    definition: >
      An occupation, march, or strike with a declared political demand.
    positive_examples:
      - "About 200 people occupied the square in front of city hall."
    negative_examples:
      - "People gathered for a cultural event with no political claim."
    boundary_notes: >
      Does not include purely ceremonial events with no claim being made.
  - label: not_protest
    definition: "Any event that does not meet the criteria above."
"""


def test_from_yaml_string_builds_schema_with_category_enum():
    codebook = Codebook.from_yaml_string(YAML_SOURCE)

    fields = codebook.schema.model_fields
    assert set(fields) == {"categoria", "justificativa", "trecho_evidencia"}
    assert set(fields["categoria"].annotation.__args__) == {"protest", "not_protest"}


def test_from_yaml_string_instructions_include_definitions_and_boundary_notes():
    codebook = Codebook.from_yaml_string(YAML_SOURCE)

    assert "occupation, march, or strike" in codebook.instructions
    assert "Does not include purely ceremonial events" in codebook.instructions


def test_from_yaml_string_rejects_duplicate_labels():
    bad_yaml = YAML_SOURCE.replace("not_protest", "protest")
    with pytest.raises(ValueError, match="duplicate category label"):
        Codebook.from_yaml_string(bad_yaml)


def test_from_yaml_string_does_not_coerce_yes_no_labels_to_bool():
    yaml_with_bool_like_labels = """
concept: turnout
description: Whether the respondent says they will vote.
categories:
  - label: yes
    definition: The respondent affirms they will vote.
  - label: no
    definition: The respondent denies they will vote.
"""
    codebook = Codebook.from_yaml_string(yaml_with_bool_like_labels)

    fields = codebook.schema.model_fields
    assert set(fields["categoria"].annotation.__args__) == {"yes", "no"}

    instance = codebook.schema(categoria="yes", justificativa="said so", trecho_evidencia="\"yes\"")
    assert instance.categoria == "yes"


def test_from_yaml_string_rejects_empty_categories():
    empty_categories_yaml = """
concept: protest
description: A collective, public event.
categories: []
"""
    with pytest.raises(ValueError, match="at least one category"):
        Codebook.from_yaml_string(empty_categories_yaml)


def test_from_yaml_string_reports_missing_required_field_as_value_error():
    missing_concept_yaml = """
description: A collective, public event.
categories:
  - label: protest
    definition: An occupation, march, or strike.
"""
    with pytest.raises(ValueError, match="missing required field"):
        Codebook.from_yaml_string(missing_concept_yaml)


def test_from_yaml_file_loads_codebook_from_disk(tmp_path):
    path = tmp_path / "codebook.yaml"
    path.write_text(YAML_SOURCE, encoding="utf-8")

    codebook = Codebook.from_yaml_file(str(path))

    assert set(codebook.schema.model_fields["categoria"].annotation.__args__) == {
        "protest",
        "not_protest",
    }
