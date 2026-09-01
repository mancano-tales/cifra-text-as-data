from __future__ import annotations

import csv
import io

import openpyxl


def parse_csv_rows(content: bytes) -> list[dict]:
    """Parse CSV bytes into row dicts keyed by the file's own header row.

    Decodes with `utf-8-sig` so a file exported from Excel with a leading
    byte-order mark doesn't corrupt the first header name into
    `'\\ufefftitle'`.
    """
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def parse_xlsx_rows(content: bytes) -> list[dict]:
    """Parse XLSX bytes into row dicts keyed by the active sheet's header
    row (its first row). Skips rows whose first cell is empty -- the same
    trailing-blank-row guard `scripts/import_v7_pilot.py` uses.
    """
    workbook = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    worksheet = workbook.active
    rows_iter = worksheet.iter_rows(values_only=True)
    header = next(rows_iter)
    rows = []
    for values in rows_iter:
        row = dict(zip(header, values))
        if row.get(header[0]) is None:
            continue
        rows.append(row)
    return rows
