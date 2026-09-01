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
