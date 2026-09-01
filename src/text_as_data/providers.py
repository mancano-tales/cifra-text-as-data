from __future__ import annotations

import json
import subprocess
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ValidationError


class Provider(ABC):
    """Something that can turn (messages, schema) into a validated schema instance."""

    @abstractmethod
    def extract(self, messages: list[dict], schema: type[BaseModel]) -> BaseModel:
        ...


class ApiKeyProvider(Provider):
    """The reliable path: an `instructor`-patched client that enforces the
    schema at the API level via tool/function calling."""

    def __init__(self, client: Any, model: str):
        self._client = client
        self._model = model

    def extract(self, messages: list[dict], schema: type[BaseModel]) -> BaseModel:
        return self._client.chat.completions.create(
            model=self._model,
            response_model=schema,
            messages=messages,
            max_retries=3,
        )


def make_api_key_provider(vendor: str, model: str, api_key: str | None = None) -> ApiKeyProvider:
    """Build an ApiKeyProvider for a real vendor. Not used in tests — tests
    construct ApiKeyProvider directly with a fake client."""
    import instructor

    if vendor == "anthropic":
        from anthropic import Anthropic

        client = instructor.from_anthropic(Anthropic(api_key=api_key))
    elif vendor == "openai":
        from openai import OpenAI

        client = instructor.from_openai(OpenAI(api_key=api_key))
    else:
        raise ValueError(f"unknown vendor: {vendor!r} (expected 'anthropic' or 'openai')")

    return ApiKeyProvider(client=client, model=model)


class CliProvider(Provider):
    """Best-effort path: shells out to an already-installed CLI (e.g. the
    Claude Code CLI, `claude -p`, or a Codex-style CLI) instead of a billed
    API key. No API-level schema enforcement — the schema is requested in
    the prompt, and the response is parsed as JSON. Less reliable than
    ApiKeyProvider; retry-on-malformed-output is the caller's job
    (extraction.py), not this class's."""

    def __init__(self, command: list[str], runner=subprocess.run, timeout: int = 180):
        self._command = command
        self._runner = runner
        self._timeout = timeout

    def extract(self, messages: list[dict], schema: type[BaseModel]) -> BaseModel:
        prompt = self._build_prompt(messages, schema)
        result = self._runner(
            self._command,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=self._timeout,
        )
        if result.returncode != 0:
            raise RuntimeError(f"CLI command failed (exit {result.returncode}): {result.stderr}")
        json_str = self._extract_json(result.stdout, schema)
        return schema.model_validate_json(json_str)

    @staticmethod
    def _build_prompt(messages: list[dict], schema: type[BaseModel]) -> str:
        parts = [m["content"] for m in messages]
        schema_json = json.dumps(schema.model_json_schema())
        parts.append(
            "Respond with ONLY a single JSON object matching this JSON Schema, "
            f"and no other text before or after it:\n{schema_json}"
        )
        return "\n\n".join(parts)

    @staticmethod
    def _extract_json(text: str, schema: type[BaseModel]) -> str:
        """Find the substring of `text` that is a top-level `{...}` object
        validating against `schema`, and return it verbatim.

        CLI output in "best-effort" mode often wraps the answer in prose,
        and that prose can itself contain other JSON-shaped fragments (e.g.
        a CLI "thinking out loud" about the schema before answering). A
        naive first-`{`-to-last-`}` regex would splice unrelated fragments
        together into one invalid blob. Instead, this scans for every
        top-level JSON object in the text (see `_json_candidates`) and
        returns the first one that actually validates against `schema` —
        so an unrelated JSON-shaped fragment earlier in the output is
        skipped rather than mistaken for the answer.
        """
        for candidate in CliProvider._json_candidates(text):
            try:
                schema.model_validate_json(candidate)
            except ValidationError:
                continue
            return candidate
        raise ValueError(f"no JSON object found in CLI output: {text!r}")

    @staticmethod
    def _json_candidates(text: str) -> list[str]:
        """Return every top-level `{...}` substring of `text` that is
        itself valid JSON.

        Hand-counting braces to find a candidate's span is not
        string-aware: a `{` or `}` inside a JSON string value (e.g. a
        quoted source excerpt or a stray brace in free text) would be
        mistaken for structural nesting and either truncate or extend the
        span incorrectly. Instead, this tries `json.JSONDecoder.raw_decode`
        at every `{` position — the real JSON parser, which already
        understands string boundaries, escapes, and nesting correctly —
        and keeps whichever spans parse successfully.
        """
        decoder = json.JSONDecoder()
        candidates: list[str] = []
        for i, ch in enumerate(text):
            if ch != "{":
                continue
            try:
                _, end = decoder.raw_decode(text, i)
            except json.JSONDecodeError:
                continue
            candidates.append(text[i:end])
        return candidates
