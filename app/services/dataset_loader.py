import csv
import json
from pathlib import Path

import openpyxl

try:
    import xlrd
except ImportError:
    xlrd = None


class DatasetLoadError(Exception):
    pass


def load_dataset(path):
    dataset_path = Path(path)
    if not dataset_path.exists():
        raise DatasetLoadError("dataset file does not exist")

    suffix = dataset_path.suffix.lower()
    if suffix == ".csv":
        records = _load_csv(dataset_path)
    elif suffix == ".json":
        records = _load_json(dataset_path)
    elif suffix == ".jsonl":
        records = _load_jsonl(dataset_path)
    elif suffix == ".xlsx":
        records = _load_xlsx(dataset_path)
    elif suffix == ".xls":
        records = _load_xls(dataset_path)
    else:
        raise DatasetLoadError("only csv, json, jsonl, xlsx and xls datasets are supported")

    normalized = [_normalize_record(record, index) for index, record in enumerate(records, 1)]
    if not normalized:
        raise DatasetLoadError("dataset is empty")
    return normalized


def _load_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _load_json(path):
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if isinstance(data, dict):
        data = data.get("items") or data.get("data") or []
    if not isinstance(data, list):
        raise DatasetLoadError("json dataset must be a list or contain items/data list")
    return data


def _load_jsonl(path):
    records = []
    with path.open("r", encoding="utf-8") as file:
        for line_no, line in enumerate(file, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise DatasetLoadError(f"invalid jsonl at line {line_no}") from exc
    return records


def _load_xlsx(path):
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheet = workbook.active
    try:
        rows = list(sheet.iter_rows(values_only=True))
    finally:
        workbook.close()
    return _tabular_rows_to_records(rows)


def _load_xls(path):
    if xlrd is None:
        raise DatasetLoadError("xls datasets require optional dependency xlrd; please convert the file to xlsx")

    workbook = xlrd.open_workbook(path)
    sheet = workbook.sheet_by_index(0)
    rows = [sheet.row_values(index) for index in range(sheet.nrows)]
    return _tabular_rows_to_records(rows)


def _tabular_rows_to_records(rows):
    if not rows:
        return []

    headers = [_normalize_header(value) for value in rows[0]]
    if not any(headers):
        raise DatasetLoadError("spreadsheet header row is empty")

    records = []
    for row in rows[1:]:
        if not row or not any(_cell_has_value(value) for value in row):
            continue
        record = {}
        for index, header in enumerate(headers):
            if not header:
                continue
            record[header] = row[index] if index < len(row) else None
        records.append(record)
    return records


def _normalize_header(value):
    if value is None:
        return ""
    return str(value).strip()


def _cell_has_value(value):
    return value is not None and str(value).strip() != ""


def _normalize_record(record, index):
    if not isinstance(record, dict):
        raise DatasetLoadError(f"record {index} must be an object")
    prompt = record.get("prompt") or record.get("input") or record.get("question")
    if not prompt:
        raise DatasetLoadError(f"record {index} missing prompt/input/question")
    return {
        "id": record.get("id") or index,
        "prompt": str(prompt),
        "expected": record.get("expected") or record.get("answer") or record.get("target"),
        "meta": {key: value for key, value in record.items() if key not in {"id", "prompt", "input", "question", "expected", "answer", "target"}},
    }
