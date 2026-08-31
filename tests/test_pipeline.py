import sys
from pathlib import Path

import pandas as pd
import pytest
from pydantic import BaseModel

from text_as_data import Codebook, agreement_report, extract

sys.path.insert(0, str(Path(__file__).parent.parent / "examples" / "toy_example"))


class Label(BaseModel):
    category: str


class FakeChatCompletions:
    def __init__(self, answers: dict[str, str]):
        self.answers = answers

    def create(self, model, response_model, messages):
        text = messages[-1]["content"]
        return response_model(category=self.answers[text])


class FakeClient:
    def __init__(self, answers: dict[str, str]):
        self.chat = type("Chat", (), {"completions": FakeChatCompletions(answers)})()


@pytest.fixture
def toy_codebook_module():
    import codebook as toy_module

    return toy_module


def test_extract_returns_one_row_per_text():
    texts = pd.DataFrame({"id": [1, 2], "text": ["a", "b"]})
    fake = FakeClient({"a": "x", "b": "y"})
    codebook = Codebook(schema=Label, instructions="irrelevant for this test")

    result = extract(texts, codebook, fake, model="fake-model")

    assert list(result["id"]) == [1, 2]
    assert list(result["category"]) == ["x", "y"]


def test_agreement_report_flags_mismatches():
    predicted = pd.DataFrame({"id": [1, 2, 3], "category": ["x", "y", "x"]})
    gold = pd.DataFrame({"id": [1, 2, 3], "category": ["x", "x", "x"]})

    report = agreement_report(predicted, gold)

    assert report["per_column"]["category"]["accuracy"] == pytest.approx(2 / 3)
    assert len(report["mismatches"]) == 1
    assert report["mismatches"][0]["id"] == 2


def test_toy_example_codebook_builds_messages(toy_codebook_module):
    codebook = toy_codebook_module.toy_codebook

    messages = codebook.build_messages("Some new statement about the policy.")

    assert messages[0]["role"] == "system"
    assert "supportive" in messages[0]["content"]
    assert messages[-1]["content"] == "Some new statement about the policy."
