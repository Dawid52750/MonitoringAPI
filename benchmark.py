import csv
import json
import statistics
import time
import urllib.error
import urllib.request


BASE_URL = "http://127.0.0.1:5000"
API_KEY = "dev-secret-key-2026"


def send_request(path, method="GET", payload=None, api_key=None):
    url = f"{BASE_URL.rstrip('/')}{path}"
    headers = {}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if api_key:
        headers["X-API-Key"] = api_key

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            body = json.loads(resp.read().decode("utf-8"))
            return resp.status, elapsed_ms, body
    except urllib.error.HTTPError as err:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        raw = err.read().decode("utf-8")
        body = json.loads(raw) if raw else {}
        return err.code, elapsed_ms, body


def run_latency_benchmark(samples=20, delay_seconds=0.5):
    rows = []
    latencies = []
    for i in range(1, samples + 1):
        code, elapsed_ms, body = send_request("/health")
        latencies.append(elapsed_ms)
        rows.append(
            {
                "probe": i,
                "http_code": code,
                "status": body.get("status", "UNKNOWN"),
                "total_latency_ms": elapsed_ms,
                "server_time_ms": body.get("response_time_ms", 0),
                "cpu_usage": body.get("cpu_usage", ""),
                "ram_usage": body.get("ram_usage", ""),
            }
        )
        time.sleep(delay_seconds)

    with open("wyniki_latencji.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    sorted_lat = sorted(latencies)
    p95_index = max(0, int(len(sorted_lat) * 0.95) - 1)
    print("=== WYNIKI TESTU LATENCJI ===")
    print(f"Liczba probek: {len(latencies)}")
    print(f"Srednia: {round(statistics.mean(latencies), 2)} ms")
    print(f"Mediana: {round(statistics.median(latencies), 2)} ms")
    print(f"Min / Max: {min(latencies)} ms / {max(latencies)} ms")
    print(f"Percentyl P95: {sorted_lat[p95_index]} ms")
    print("Zapisano: wyniki_latencji.csv\n")


def run_incident_benchmark(cycles=3, poll_interval=2.0, outage_wait=4.0):
    results = []
    for cycle in range(1, cycles + 1):
        break_time = time.perf_counter()
        send_request(
            "/break",
            method="POST",
            payload={"reason": f"Test badawczy cykl #{cycle}"},
            api_key=API_KEY,
        )

        mttd = None
        while mttd is None:
            time.sleep(poll_interval)
            code, _, _ = send_request("/health")
            if code == 500:
                mttd = round(time.perf_counter() - break_time, 2)

        time.sleep(outage_wait)
        send_request("/fix", method="POST", payload={}, api_key=API_KEY)

        mttr = None
        while mttr is None:
            code, _, _ = send_request("/health")
            if code == 200:
                mttr = round(time.perf_counter() - break_time, 2)
            else:
                time.sleep(poll_interval)

        results.append(
            {
                "cycle": cycle,
                "poll_interval_s": poll_interval,
                "mttd_seconds": mttd,
                "mttr_seconds": mttr,
            }
        )
        print(f"Cykl #{cycle}: MTTD = {mttd} s | MTTR = {mttr} s")

    with open("wyniki_incydentow.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    avg_mttd = round(statistics.mean(r["mttd_seconds"] for r in results), 2)
    avg_mttr = round(statistics.mean(r["mttr_seconds"] for r in results), 2)
    print(f"\nSrednie MTTD: {avg_mttd} s | Srednie MTTR: {avg_mttr} s")
    print("Zapisano: wyniki_incydentow.csv")


if __name__ == "__main__":
    run_latency_benchmark(samples=20, delay_seconds=0.5)
    run_incident_benchmark(cycles=3, poll_interval=2.0, outage_wait=4.0)