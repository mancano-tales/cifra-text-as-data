<!-- 🇺🇸 English — [🇧🇷 versão em português](README.pt-BR.md) -->

# text-as-data

A small pipeline for turning unstructured text (news articles, social media
posts, statements) into a structured table via LLM classification against
an explicit *codebook* — a theoretical definition of the concept being
coded — with systematic validation against human-coded labels.

## Why

Political science (and social science more broadly) has long relied on
manually reading text and coding it into categorical/free-text columns
(is this a protest? does this statement support or oppose a given policy?).
LLMs can automate the coding step, but the real risk is not accuracy — it
is **construct validity**: does the model actually apply *your*
operationalization of the concept, or does it fall back on whatever
generic notion of the concept it picked up in training? (See Halterman &
Keith, *"Codebook LLMs: Evaluating LLMs as Measurement Tools for Political
Science Concepts"*, Political Analysis, 2025.)

This package treats validation against a human-coded sample as a
first-class step, not an afterthought.

## Architecture

```
texts.csv (id, text)
     │
     ▼
codebook   — schema (Pydantic model) + theoretical instructions + few-shot examples
     │
     ▼
extraction — calls an LLM via `instructor`, validates the response against the schema
     │
     ▼
validation — compares LLM output against human gold labels (accuracy, Cohen's kappa,
              list of mismatches for inspection)
```

`codebook` is deliberately separate from `extraction`: the codebook is what
changes between projects (a land-occupation codebook, a policy-stance
codebook, a crime-event codebook); the extraction and validation engines
stay the same.

**Out of scope for now**: scraping/collecting raw text from a specific
source (newspaper, social platform). The pipeline assumes text has already
been collected into a `texts.csv` (columns: `id`, `text`). See `TODO.md`.

## Install

```bash
pip install -e ".[dev]"
```

## Quickstart

See `examples/toy_example/` for a complete, runnable (if trivial) example:
a codebook classifying statements by stance toward a policy, a handful of
texts, and human gold labels to validate against.

```python
import instructor
import pandas as pd
from openai import OpenAI

from text_as_data import extract, agreement_report
from examples.toy_example.codebook import toy_codebook

client = instructor.from_openai(OpenAI())
texts = pd.read_csv("examples/toy_example/texts.csv")
gold = pd.read_csv("examples/toy_example/gold.csv")

predicted = extract(texts, toy_codebook, client, model="gpt-4o-mini")
report = agreement_report(predicted, gold)
```

## Writing your own codebook

A codebook is a `Codebook(schema, instructions, examples)`:

- `schema`: a `pydantic.BaseModel` — one field per output column.
- `instructions`: the theoretical definition of each category, written the
  way you would write it for a human coder. Be explicit about edge cases
  the model is likely to get wrong by falling back on a generic reading
  (see `examples/toy_example/codebook.py` for a worked instance).
- `examples`: a handful of (text, expected output) pairs — few-shot
  examples that pin down exactly the edge cases instructions alone tend to
  leave ambiguous.

## Testing

```bash
pytest
```

`tests/` exercises `extraction` and `validation` against a fake LLM client
(no API key or network access needed). `examples/toy_example/run.py` is the
one script that hits a real LLM — run it manually when you want to check
the pipeline end to end.
