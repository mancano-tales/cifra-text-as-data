from __future__ import annotations

from typing import Any

import pandas as pd

from .codebook import Codebook


def extract(
    texts: pd.DataFrame,
    codebook: Codebook,
    client: Any,
    model: str,
    id_col: str = "id",
    text_col: str = "text",
) -> pd.DataFrame:
    """Classify each row of `texts` against `codebook` using an instructor client.

    `client` is an `instructor`-patched LLM client (any provider instructor
    supports). One request is made per row; each response is validated
    against `codebook.schema` before being flattened into the output table.
    """
    rows = []
    for _, row in texts.iterrows():
        result = client.chat.completions.create(
            model=model,
            response_model=codebook.schema,
            messages=codebook.build_messages(row[text_col]),
        )
        rows.append({id_col: row[id_col], **result.model_dump()})
    return pd.DataFrame(rows)
