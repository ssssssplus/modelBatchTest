import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.services.model_client import ModelClientError


def run_pressure_test(client, prompt, concurrency, total_requests, request_body=None):
    started = time.perf_counter()
    results = []

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(_call_once, client, prompt, request_body) for _ in range(total_requests)]
        for future in as_completed(futures):
            results.append(future.result())

    duration_seconds = round(time.perf_counter() - started, 4)
    ok_results = [item for item in results if item["ok"]]
    failed_results = [item for item in results if not item["ok"]]
    latencies = [item["latency_ms"] for item in ok_results]

    return {
        "total": total_requests,
        "ok": len(ok_results),
        "failed": len(failed_results),
        "duration_seconds": duration_seconds,
        "qps": round(total_requests / duration_seconds, 2) if duration_seconds else total_requests,
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
