#! /usr/bin/env python3
import argparse, requests, time, yaml, concurrent.futures as cf
import os

def load_config(file_path):
    # Define the allowed base directory for config files
    CONFIG_DIR = os.path.abspath(os.path.dirname(__file__))
    abs_path = os.path.abspath(file_path)
    # Ensure the resolved path is within the allowed directory
    if os.path.commonpath([abs_path, CONFIG_DIR]) != CONFIG_DIR:
        raise ValueError("Access to the specified config file is not allowed.")
    with open(abs_path, 'r') as file:
        return yaml.safe_load(file)

def call_worker(url, op, iters, concurrency, payload, timeout):
    r = requests.post(f"{url}/{op}", json={
        "op": op,
        "iters": iters,
        "concurrency": concurrency,
        "payload": payload or {}
    }, timeout=timeout)
    r.raise_for_status()
    return r.json()
    

def main():
    ap = argparse.ArgumentParser(description="KeyCrate main controller")
    ap.add_argument("-c", "--config", default="config.yaml")
    ap.add_argument("--op", default=None, help="override operation name")
    ap.add_argument("--iters", type=int, default=None, help="total iterations")
    ap.add_argument("--conc", type=int, default=None, help="thread count")
    ap.add_argument("--timeout", type=int, default=500)
    args = ap.parse_args()

    cfg = load_config(args.config)

    workers = cfg["workers"] # list of URLs, ["<url1>", "<url2>", ...]
    op = args.op or cfg.get("op", "sha256_cpu")
    total_iters = int(args.iters or cfg.get("total_iters", 2_000_000))
    conc_per = int(args.conc or cfg.get("concurrency_per_worker", 4))
    payload = cfg.get("payload", {}) or {}

    # split iterations across workers
    base = total_iters // len(workers)
    plan = [base] * len(workers)
    plan[-1] += total_iters - base * len(workers)  # distribute remainder

    print(f"[KeyCrate] op={op}, workers={len(workers)} total_iters={total_iters} conc/workers={conc_per}")
    t0 = time.perf_counter()

    results = []
    with cf.ThreadPoolExecutor(max_workers=len(workers)) as ex:
        futs = [ex.submit(call_worker, w, op, it, conc_per, payload, args.timeout)
                for w, it in zip(workers, plan)]
        for f in cf.as_completed(futs):
            try:
                results.append(f.result())
            except Exception as e:
                print(f"[KeyCrate] Error: {e}")

    elapsed = time.perf_counter() - t0

    # Summaries
    agg_throughput = sum(r.get("throughput_ops_per_sec") or 0 for r in results)
    total_errors = sum(r.get("errors", 0) for r in results)
    sum_iters = sum(r.get("iters", 0) for r in results)

    print("\nPer-worker:")
    for r in results:
        print(f"  {r['hostname']:<12} {r['op']:<12} iters={r['iters']:,} "
              f"dur={r['duration_sec']:.3f}s thr={int(r['throughput_ops_per_sec']):,}/s "
              f"errors={r['errors']}")

    print("\nAggregate:")
    print(f"  total iters: {sum_iters:,}")
    print(f"  aggregate throughput: {int(agg_throughput):,} ops/s")
    print(f"  wall time (controller): {elapsed:.3f}s")
    if total_errors:
        print(f"  errors: {total_errors}")

if __name__ == "__main__":
    main()