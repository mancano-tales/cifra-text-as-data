import io

import openpyxl

from text_as_data.corpus_import import parse_csv_rows, parse_xlsx_rows


def test_parse_csv_rows_reads_header_and_rows():
    content = "title,body\nA,First doc\nB,Second doc\n".encode("utf-8")

    rows = parse_csv_rows(content)

    assert rows == [
        {"title": "A", "body": "First doc"},
        {"title": "B", "body": "Second doc"},
    ]


def test_parse_csv_rows_strips_utf8_bom_from_the_first_header():
    content = "﻿title,body\nA,First doc\n".encode("utf-8")

    rows = parse_csv_rows(content)

    assert rows == [{"title": "A", "body": "First doc"}]


def _make_xlsx_bytes(rows: list[list]) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_parse_xlsx_rows_reads_header_and_rows():
    content = _make_xlsx_bytes([["title", "body"], ["A", "First doc"], ["B", "Second doc"]])

    rows = parse_xlsx_rows(content)

    assert rows == [
        {"title": "A", "body": "First doc"},
        {"title": "B", "body": "Second doc"},
    ]


def test_parse_xlsx_rows_skips_blank_trailing_rows():
    content = _make_xlsx_bytes([["title", "body"], ["A", "First doc"], [None, None]])

    rows = parse_xlsx_rows(content)

    assert len(rows) == 1
