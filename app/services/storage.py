from pathlib import Path
from uuid import uuid4

from werkzeug.utils import secure_filename


ALLOWED_EXTENSIONS = {".csv", ".json", ".jsonl", ".xlsx", ".xls"}


def save_uploaded_file(file, upload_folder):
    original_name = secure_filename(file.filename)
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("only csv, json, jsonl, xlsx and xls files are allowed")

    target_dir = Path(upload_folder)
    target_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}{suffix}"
    path = target_dir / stored_name
    file.save(path)

    return {
        "original_name": original_name,
        "stored_name": stored_name,
        "path": str(path),
    }
