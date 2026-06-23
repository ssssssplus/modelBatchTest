from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request, send_file

from app.services.dataset_loader import DatasetLoadError, load_dataset
from app.services.excel_exporter import batch_results_filename, build_batch_results_xlsx
from app.services.model_client import ModelClient, ModelClientError
from app.services.pressure import run_pressure_test
from app.services.storage import save_uploaded_file


bp = Blueprint("main", __name__)


def _page_context(active_page):
    return {
        "active_page": active_page,
        "default_api_url": current_app.config["DEFAULT_MODEL_API_URL"],
        "default_model": current_app.config["DEFAULT_MODEL_NAME"],
        "model_presets": current_app.config["MODEL_PRESETS"],
    }


def _client_from_request(payload):
    api_url = payload.get("api_url") or current_app.config["DEFAULT_MODEL_API_URL"]
    model = payload.get("model") or current_app.config["DEFAULT_MODEL_NAME"]
    timeout = current_app.config["MODEL_API_TIMEOUT"]
    return ModelClient(api_url=api_url, model=model, timeout=timeout)


def _request_body_from_request(payload):
    request_body = payload.get("request_body")
    if request_body is None:
        return None
    if not isinstance(request_body, dict):
        raise ValueError("request_body must be a json object")
    return request_body


def _dataset_path_from_request(payload):
    dataset_name = payload.get("dataset_name") or payload.get("dataset_path")
    if not dataset_name:
        raise ValueError("dataset_name is required")

    upload_dir = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    dataset_path = (upload_dir / Path(dataset_name).name).resolve()
    if upload_dir not in dataset_path.parents:
        raise ValueError("invalid dataset name")
    return dataset_path


def _positive_int_from_request(payload, key, default):
    value = payload.get(key, default)
    if value == "":
        value = default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be an integer") from exc


@bp.get("/")
def index():
    return render_template("index.html", **_page_context("home"))


@bp.get("/single")
def single_page():
    return render_template("single.html", **_page_context("single"))


@bp.get("/batch")
def batch_page():
    return render_template("batch.html", **_page_context("batch"))


@bp.get("/pressure")
def pressure_page():
    return render_template("pressure.html", **_page_context("pressure"))


@bp.post("/api/test")
def test_model():
    payload = request.get_json(silent=True) or {}
    prompt = (payload.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "prompt is required"}), 400

    client = _client_from_request(payload)
    try:
        request_body = _request_body_from_request(payload)
        result = client.generate(prompt, request_body=request_body)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except ModelClientError as exc:
        return jsonify({"error": str(exc)}), 502

    return jsonify(result)


@bp.post("/api/datasets")
def upload_dataset():
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "file is required"}), 400

    try:
        dataset = save_uploaded_file(file, current_app.config["UPLOAD_FOLDER"])
        records = load_dataset(dataset["path"])
    except (ValueError, DatasetLoadError) as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(
        {
            "dataset": dataset,
            "count": len(records),
            "preview": records[:5],
        }
    )


@bp.post("/api/batch-test")
def batch_test():
    payload = request.get_json(silent=True) or {}
    try:
        dataset_path = _dataset_path_from_request(payload)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        records = load_dataset(dataset_path)
    except DatasetLoadError as exc:
        return jsonify({"error": str(exc)}), 400

    client = _client_from_request(payload)
    try:
        request_body = _request_body_from_request(payload)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    results = []
    for record in records:
        try:
            output = client.generate(record["prompt"], request_body=request_body)
            results.append(
                {
                    "id": record.get("id"),
                    "prompt": record["prompt"],
                    "expected": record.get("expected"),
                    "ok": True,
                    "output": output.get("text", ""),
                    "latency_ms": output.get("latency_ms"),
                }
            )
        except ModelClientError as exc:
            results.append(
                {
                    "id": record.get("id"),
                    "prompt": record["prompt"],
                    "expected": record.get("expected"),
                    "ok": False,
                    "error": str(exc),
                }
            )

    ok_count = sum(1 for item in results if item["ok"])
    return jsonify(
        {
            "total": len(results),
            "ok": ok_count,
            "failed": len(results) - ok_count,
            "results": results,
        }
    )


@bp.post("/api/export-batch-results")
def export_batch_results():
    payload = request.get_json(silent=True) or {}
    results = payload.get("results")
    if not isinstance(results, list) or not results:
        return jsonify({"error": "results must be a non-empty list"}), 400

    workbook = build_batch_results_xlsx(results)
    return send_file(
        workbook,
        as_attachment=True,
        download_name=batch_results_filename(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.post("/api/pressure-test")
def pressure_test():
    payload = request.get_json(silent=True) or {}
    prompt = (payload.get("prompt") or "Hello, please respond briefly.").strip()
    try:
        concurrency = _positive_int_from_request(payload, "concurrency", 5)
        total_requests = _positive_int_from_request(payload, "total_requests", 20)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if concurrency < 1 or total_requests < 1:
        return jsonify({"error": "concurrency and total_requests must be positive"}), 400
    if concurrency > 100 or total_requests > 5000:
        return jsonify({"error": "concurrency <= 100 and total_requests <= 5000"}), 400

    client = _client_from_request(payload)
    try:
        request_body = _request_body_from_request(payload)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    summary = run_pressure_test(
        client=client,
        prompt=prompt,
        concurrency=concurrency,
        total_requests=total_requests,
        request_body=request_body,
    )
    return jsonify(summary)
