import csv
import io
import json

import openpyxl

from text_as_data.export import results_to_csv_bytes, results_to_json_bytes, results_to_xlsx_bytes

SAMPLE_ROWS = [
    {"document_snippet": "About 200 people occupied...", "categoria": "protest", "justificativa": "clear demand"},
    {"document_snippet": "A music festival happened...", "categoria": "not_protest", "justificativa": "no claim"},
]


def test_results_to_csv_bytes_round_trips():
    content = results_to_csv_bytes(SAMPLE_ROWS)

    reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
    rows = list(reader)

    assert rows == SAMPLE_ROWS


def test_results_to_csv_bytes_handles_empty_list():
    assert results_to_csv_bytes([]) == b""


def test_results_to_xlsx_bytes_round_trips():
    content = results_to_xlsx_bytes(SAMPLE_ROWS)

    workbook = openpyxl.load_workbook(io.BytesIO(content))
    sheet = workbook.active
    rows_iter = sheet.iter_rows(values_only=True)
    header = next(rows_iter)
    rows = [dict(zip(header, values)) for values in rows_iter]

    assert rows == SAMPLE_ROWS


def test_results_to_json_bytes_round_trips():
    content = results_to_json_bytes(SAMPLE_ROWS)

    assert json.loads(content.decode("utf-8")) == SAMPLE_ROWS
