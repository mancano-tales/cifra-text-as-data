"""Run the toy example end to end against a real LLM.

Requires an API key for whichever provider `instructor` is patching (this
example uses OpenAI; see https://python.useinstructor.com for other
providers). Not run in CI or in `pytest` — it costs money and needs
network access. `tests/test_pipeline.py` exercises the same modules with a
fake client instead.
"""

import instructor
import pandas as pd
from openai import OpenAI

from text_as_data import agreement_report, extract
from codebook import toy_codebook

if __name__ == "__main__":
    client = instructor.from_openai(OpenAI())
    texts = pd.read_csv("texts.csv")
    gold = pd.read_csv("gold.csv")

    predicted = extract(texts, toy_codebook, client, model="gpt-4o-mini")
    report = agreement_report(predicted, gold)

    print(predicted)
    print(report["per_column"])
    for mismatch in report["mismatches"]:
        print("mismatch:", mismatch)
