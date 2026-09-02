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


import shutil
import subprocess

import pytest

from text_as_data.providers import CliProvider


def _fake_runner(stdout: str, returncode: int = 0):
    def runner(command, input, capture_output, encoding, timeout):
        assert encoding == "utf-8"
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


def test_cli_provider_resolves_command_via_path(monkeypatch):
    # On Windows, `claude` installed via npm resolves to a `.cmd` shim, not
    # a `.exe`. subprocess.run(["claude", "-p"], shell=False) does not
    # search PATHEXT the way a real shell does, so it fails to find the
    # executable even though `claude` works fine typed directly in a
    # terminal. CliProvider must resolve the command's first element via
    # shutil.which() at construction time so the resolved absolute path is
    # what actually gets invoked.
    monkeypatch.setattr(shutil, "which", lambda name: r"C:\fake\path\claude.cmd" if name == "claude" else None)

    provider = CliProvider(command=["claude", "-p"], runner=_fake_runner("{}"))

    assert provider._command == [r"C:\fake\path\claude.cmd", "-p"]


def test_cli_provider_keeps_original_command_when_not_found_on_path(monkeypatch):
    # If shutil.which can't find the command, keep the original name rather
    # than swallowing the error -- subprocess.run will then raise its own
    # clear FileNotFoundError naming the command, which is the right
    # failure mode for a genuinely-missing CLI.
    monkeypatch.setattr(shutil, "which", lambda name: None)

    provider = CliProvider(command=["totally-missing-cli", "-p"], runner=_fake_runner("{}"))

    assert provider._command == ["totally-missing-cli", "-p"]


def test_cli_provider_passes_utf8_encoding_to_runner():
    # subprocess.run(..., text=True) with no explicit `encoding` decodes
    # stdout/stderr using the locale default encoding (cp1252 on Windows),
    # silently corrupting non-ASCII output (e.g. accented Portuguese text)
    # even though the `claude` CLI actually emits UTF-8. extract() must
    # pass encoding="utf-8" explicitly so decoding is correct regardless of
    # the host locale.
    captured_kwargs = {}

    def capturing_runner(command, input, capture_output, encoding, timeout):
        captured_kwargs["encoding"] = encoding
        return subprocess.CompletedProcess(
            args=command, returncode=0, stdout='{"categoria": "protest"}', stderr=""
        )

    provider = CliProvider(command=["fake-cli"], runner=capturing_runner)
    provider.extract(messages=[{"role": "user", "content": "x"}], schema=Label)

    assert captured_kwargs["encoding"] == "utf-8"


def test_cli_provider_passes_prompt_as_trailing_arg_when_configured(monkeypatch):
    # `agy -p "<prompt>"` (Google Antigravity CLI) errors "flag needs an
    # argument" if given no value and nothing on stdin -- unlike `claude
    # -p`, which blocks reading the prompt from stdin. prompt_mode="arg"
    # must append the prompt to the command list instead of piping it in.
    monkeypatch.setattr(shutil, "which", lambda name: None)
    captured = {}

    def capturing_runner(command, input, capture_output, encoding, timeout):
        captured["command"] = command
        captured["input"] = input
        return subprocess.CompletedProcess(args=command, returncode=0, stdout='{"categoria": "protest"}', stderr="")

    provider = CliProvider(command=["agy", "-p"], runner=capturing_runner, prompt_mode="arg")
    result = provider.extract(messages=[{"role": "user", "content": "x"}], schema=Label)

    assert result.categoria == "protest"
    assert captured["command"][:2] == ["agy", "-p"]
    assert captured["command"][2].startswith("x")
    assert captured["input"] is None


def test_cli_provider_rejects_unknown_prompt_mode():
    with pytest.raises(ValueError, match="prompt_mode"):
        CliProvider(command=["fake-cli"], runner=_fake_runner("{}"), prompt_mode="carrier-pigeon")


def test_cli_provider_decodes_non_ascii_output_correctly():
    # End-to-end sanity check that non-ASCII text (e.g. Portuguese
    # accented characters from the V7 pilot corpus) survives the round
    # trip through extract() unmangled.
    text = "instituições"
    runner = _fake_runner('{"categoria": "' + text + '"}')
    provider = CliProvider(command=["fake-cli"], runner=runner)

    result = provider.extract(messages=[{"role": "user", "content": "x"}], schema=Label)

    assert result.categoria == text
