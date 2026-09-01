from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import yaml
from pydantic import BaseModel, Field, create_model


@dataclass
class Codebook:
    """A theoretical construct operationalized as an LLM-extractable schema.

    A codebook bundles three things that must travel together: the output
    schema (what columns end up in the structured table), the instructions
    (the theoretical definition of each category — the part a domain expert
    actually authors), and a handful of worked examples (few-shot) that pin
    down edge cases the instructions alone tend to leave ambiguous.
    """

    schema: type[BaseModel]
    instructions: str
    examples: list[dict] = field(default_factory=list)

    def build_messages(self, text: str) -> list[dict]:
        system = (
            "You are a careful annotator applying a fixed coding scheme. "
            "Follow the instructions below exactly as written, even when a "
            "case looks similar to a more common or generic concept. Do not "
            "substitute your own default definition for the one given.\n\n"
            f"{self.instructions}"
        )
        messages = [{"role": "system", "content": system}]
        for example in self.examples:
            messages.append({"role": "user", "content": example["text"]})
            messages.append(
                {"role": "assistant", "content": example["output"].model_dump_json()}
                if isinstance(example["output"], BaseModel)
                else {"role": "assistant", "content": str(example["output"])}
            )
        messages.append({"role": "user", "content": text})
        return messages

    @classmethod
    def from_yaml_string(cls, source: str) -> "Codebook":
        spec = yaml.safe_load(source)
        return cls._from_spec(spec)

    @classmethod
    def from_yaml_file(cls, path: str) -> "Codebook":
        with open(path, encoding="utf-8") as f:
            return cls.from_yaml_string(f.read())

    @classmethod
    def _from_spec(cls, spec: dict) -> "Codebook":
        labels = [c["label"] for c in spec["categories"]]
        if len(set(labels)) != len(labels):
            raise ValueError(f"duplicate category label in codebook: {labels}")

        schema = create_model(
            "CodebookExtraction",
            categoria=(Literal[tuple(labels)], Field(description="One of the codebook's category labels.")),
            justificativa=(str, Field(description="Free-text rationale for the chosen category.")),
            trecho_evidencia=(str, Field(description="Verbatim quote from the document that grounds the decision.")),
        )

        lines = [f"Concept: {spec['concept']}", spec["description"].strip(), "", "Categories:"]
        for c in spec["categories"]:
            lines.append(f"- {c['label']}: {c['definition'].strip()}")
            for ex in c.get("positive_examples", []):
                lines.append(f'  Positive example: "{ex}"')
            for ex in c.get("negative_examples", []):
                lines.append(f'  Negative example: "{ex}"')
            if c.get("boundary_notes"):
                lines.append(f"  Boundary notes: {c['boundary_notes'].strip()}")
        instructions = "\n".join(lines)

        return cls(schema=schema, instructions=instructions)
