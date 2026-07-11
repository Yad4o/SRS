"""
Standalone load test for the ticket creation endpoint.
Not part of the pytest suite -- run manually against a running instance
to produce real throughput/latency numbers for documentation purposes.

Usage:
    uvicorn app.main:app --host 127.0.0.1 --port 8000   # in one terminal
    python load_test.py --url http://127.0.0.1:8000/tickets/ --n 150 --concurrency 10
"""
import argparse
import concurrent.futures
import json
import statistics
import time
import urllib.request

PAYLOADS = [
    {"subject": "t", "message": "I cannot login to my account"},
    {"subject": "t", "message": "My payment was charged twice"},
    {"subject": "t", "message": "Please add a dark mode feature"},
    {"subject": "t", "message": "The app keeps crashing"},
    {"subject": "t", "message": "How do I upgrade my plan"},
]


def hit(url: str, i: int):
    data = json.dumps(PAYLOADS[i % len(PAYLOADS)]).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
            ok = resp.status in (200, 201)
    except Exception:
        ok = False
    return (time.perf_counter() - start) * 1000, ok


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000/tickets/")
    parser.add_argument("--n", type=int, default=150)
    parser.add_argument("--concurrency", type=int, default=10)
    args = parser.parse_args()

    latencies = []
    oks = 0
    t0 = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = [ex.submit(hit, args.url, i) for i in range(args.n)]
        for f in concurrent.futures.as_completed(futures):
            lat, ok = f.result()
            latencies.append(lat)
            oks += int(ok)
    total_time = time.perf_counter() - t0

    latencies.sort()
    p50 = statistics.median(latencies)
    p95 = latencies[int(len(latencies) * 0.95) - 1]
    p99 = latencies[int(len(latencies) * 0.99) - 1]

    print(f"Requests: {args.n}, concurrency: {args.concurrency}, success: {oks}/{args.n}")
    print(f"Total wall time: {total_time:.2f}s -> {args.n / total_time:.1f} req/s")
    print(
        f"Latency p50: {p50:.1f} ms, p95: {p95:.1f} ms, p99: {p99:.1f} ms, "
        f"mean: {statistics.mean(latencies):.1f} ms"
    )


if __name__ == "__main__":
    main()
