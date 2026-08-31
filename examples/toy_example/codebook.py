"""A deliberately trivial codebook, used only to smoke-test the pipeline
end to end. It is not a real research instrument — swap in a real codebook
(with real theoretical instructions and examples) for an actual project.
"""

from pydantic import BaseModel, Field

from text_as_data import Codebook


class StanceLabel(BaseModel):
    stance: str = Field(
        description="One of: 'supportive', 'opposed', 'neutral' — the "
        "speaker's stance toward the policy mentioned in the statement."
    )
    rationale: str = Field(description="One sentence justifying the label.")


INSTRUCTIONS = """
Classify the speaker's stance toward the policy mentioned in the statement
into exactly one of three categories:

- "supportive": the speaker explicitly endorses the policy or argues it
  should be adopted/continued.
- "opposed": the speaker explicitly argues against the policy or that it
  should be repealed/blocked.
- "neutral": the speaker describes the policy or its effects without
  taking a side, or the statement does not express a stance at all.

A statement that merely reports a fact about the policy (e.g. "the policy
was passed last year") is "neutral", not "supportive", even though passage
sounds positive. Only classify as "supportive" or "opposed" when the
speaker's own position is explicit.
"""

EXAMPLES = [
    {
        "text": "This policy is a disaster and must be reversed immediately.",
        "output": StanceLabel(stance="opposed", rationale="Explicit call to reverse the policy."),
    },
    {
        "text": "The policy took effect on January 1st.",
        "output": StanceLabel(stance="neutral", rationale="States a fact, no position taken."),
    },
]

toy_codebook = Codebook(schema=StanceLabel, instructions=INSTRUCTIONS, examples=EXAMPLES)
