from __future__ import annotations

import json
import re
import subprocess
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


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
        json_str = self._extract_json(result.stdout)
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
    def _extract_json(text: str) -> str:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError(f"no JSON object found in CLI output: {text!r}")
        return match.group(0)
