from pydantic import BaseModel

from text_as_data.providers import ApiKeyProvider


class Label(BaseModel):
    categoria: str


class FakeChatCompletions:
    def __init__(self):
        self.calls = 0

    def create(self, model, response_model, messages, max_retries):
        self.calls += 1
        return response_model(categoria="protest")


class FakeInstructorClient:
    def __init__(self):
        self.chat = type("Chat", (), {"completions": FakeChatCompletions()})()


def test_api_key_provider_delegates_to_instructor_client():
    fake_client = FakeInstructorClient()
    provider = ApiKeyProvider(client=fake_client, model="fake-model")

    result = provider.extract(messages=[{"role": "user", "content": "x"}], schema=Label)

    assert result.categoria == "protest"
    assert fake_client.chat.completions.calls == 1


import subprocess

import pytest

from text_as_data.providers import CliProvider


def _fake_runner(stdout: str, returncode: int = 0):
    def runner(command, input, capture_output, text, timeout):
        return subprocess.CompletedProcess(args=command, returncode=returncode, stdout=stdout, stderr="")

    return runner


def test_cli_provider_parses_json_from_stdout():
    runner = _fake_runner('Here is the answer:\n{"categoria": "protest"}\nDone.')
    provider = CliProvider(command=["fake-cli", "-p"], runner=runner)

    result = provider.extract(messages=[{"role": "user", "content": "x"}], schema=Label)

    assert result.categoria == "protest"


def test_cli_provider_raises_on_nonzero_exit():
    runner = _fake_runner("boom", returncode=1)
    provider = CliProvider(command=["fake-cli"], runner=runner)

    with pytest.raises(RuntimeError, match="CLI command failed"):
        provider.extract(messages=[{"role": "user", "content": "x"}], schema=Label)


def test_cli_provider_raises_on_missing_json():
    runner = _fake_runner("no json here")
    provider = CliProvider(command=["fake-cli"], runner=runner)

    with pytest.raises(ValueError, match="no JSON object found"):
        provider.extract(messages=[{"role": "user", "content": "x"}], schema=Label)


def test_cli_provider_skips_non_matching_json_fragment_before_the_answer():
    # Realistic "best-effort" CLI output: an earlier JSON-shaped fragment
    # (e.g. the CLI thinking out loud about the schema) precedes the real
    # answer. A naive first-`{`-to-last-`}` regex would splice these two
    # fragments into one invalid blob and raise a confusing
    # pydantic.ValidationError instead of finding the real answer.
    runner = _fake_runner(
        'Let me check the schema first: {"note": "checking the schema"}\n\n'
        'Here is my answer:\n{"categoria": "protest"}'
    )
    provider = CliProvider(command=["fake-cli"], runner=runner)

    result = provider.extract(messages=[{"role": "user", "content": "x"}], schema=Label)

    assert result.categoria == "protest"


def test_cli_provider_handles_unmatched_brace_inside_json_string_value():
    # Adversarial but realistic: a free-text field (e.g. a quoted source
    # excerpt) contains a stray unmatched `}` inside the JSON string
    # itself. A hand-rolled brace-depth counter treats that in-string `}`
    # as closing the top-level object, producing a truncated, invalid
    # candidate and never resuming — even though the JSON is perfectly
    # valid. Preceded by an unrelated decoy fragment to also confirm
    # schema-validated selection still skips past it.
    runner = _fake_runner(
        'Let me check the schema first: {"note": "checking the schema"}\n\n'
        'Here is my answer:\n'
        '{"justificativa": "cost > 100} threshold exceeded", "categoria": "protest"}'
    )
    provider = CliProvider(command=["fake-cli"], runner=runner)

    result = provider.extract(messages=[{"role": "user", "content": "x"}], schema=Label)

    assert result.categoria == "protest"


def test_cli_provider_prefers_top_level_object_over_nested_sub_object():
    # A CLI that wraps its answer in a named key (e.g. `{"result": {...}}`,
    # or here a `wrapper` key containing a nested object that itself
    # happens to validate against the schema) must not have that inner
    # object mistaken for the real, top-level answer. Trying
    # `raw_decode` at every `{` position -- including ones nested inside
    # an already-parsed object -- would find the inner object first and
    # return it instead of the real top-level answer that follows.
    runner = _fake_runner(
        '{"wrapper": {"justificativa": "inner one", "categoria": "inner_match"}, '
        '"outer_note": "irrelevant"}\n'
        '{"justificativa": "outer one", "categoria": "outer_match"}'
    )
    provider = CliProvider(command=["fake-cli"], runner=runner)

    result = provider.extract(messages=[{"role": "user", "content": "x"}], schema=Label)

    assert result.categoria == "outer_match"
