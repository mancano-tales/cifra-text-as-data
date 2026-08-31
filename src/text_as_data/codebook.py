from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel


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
