import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.services.model_client import ModelClientError


def run_pressure_test(client, prompt, concurrency, total_requests=None, duration_seconds=None, request_body=None):
    started = time.perf_counter()
    if duration_seconds is not None:
        results = _run_duration_mode(client, prompt, concurrency, duration_seconds, request_body)
        mode = "duration"
    else:
        results = _run_request_count_mode(client, prompt, concurrency, total_requests, request_body)
        mode = "requests"

    elapsed_seconds = round(time.perf_counter() - started, 4)
    return _summarize_results(results, elapsed_seconds, mode, total_requests, duration_seconds)


def _run_request_count_mode(client, prompt, concurrency, total_requests, request_body):
    results = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(_call_once, client, prompt, request_body) for _ in range(total_requests)]
        for future in as_completed(futures):
            results.append(future.result())
    return results


def _run_duration_mode(client, prompt, concurrency, duration_seconds, request_body):
    deadline = time.perf_counter() + duration_seconds
    results = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(_duration_worker, client, prompt, request_body, deadline) for _ in range(concurrency)]
        for future in as_completed(futures):
            results.extend(future.result())
    return results


def _duration_worker(client, prompt, request_body, deadline):
    results = []
    while time.perf_counter() < deadline:
        results.append(_call_once(client, prompt, request_body))
    return results


def _summarize_results(results, duration_seconds, mode, configured_total_requests, configured_duration_seconds):
    ok_results = [item for item in results if item["ok"]]
    failed_results = [item for item in results if not item["ok"]]
    latencies = [item["latency_ms"] for item in ok_results]
    total = len(results)

    return {
        "mode": mode,
        "configured_total_requests": configured_total_requests,
        "configured_duration_seconds": configured_duration_seconds,
        "total": total,
        "ok": len(ok_results),
        "failed": len(failed_results),
        "duration_seconds": duration_seconds,
        "qps": round(total / duration_seconds, 2) if duration_seconds else total,
        "latency_ms": {
            "avg": round(statistics.mean(latencies), 2) if latencies else None,
            "min": round(min(latencies), 2) if latencies else None,
            "max": round(max(latencies), 2) if latencies else None,
            "p95": _percentile(latencies, 95) if latencies else None,
        },
        "errors": failed_results[:10],
        "samples": ok_results[:5],
    }


def _call_once(client, prompt, request_body):
    try:
        result = client.generate(prompt, request_body=request_body)
        return {
            "ok": True,
            "latency_ms": result["latency_ms"],
            "text": result["text"],
        }
    except ModelClientError as exc:
        return {
            "ok": False,
            "error": str(exc),
        }


def _percentile(values, percentile):
    sorted_values = sorted(values)
    index = int(round((percentile / 100) * (len(sorted_values) - 1)))
    return round(sorted_values[index], 2)
