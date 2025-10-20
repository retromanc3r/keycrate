from flask import Flask, request, jsonify
import concurrent.futures as cf
import time, os, threading
from ops import OPS # dict: op_name -> callable(iters, payload) -> dict

app = Flask(__name__)
_device_lock = threading.Lock() # use if your device access isn't thread-safe

def run_op(op: str, iters: int, payload: dict) -> dict:
    if op not in OPS:
        raise ValueError(f"Unknown operation: {op}")
    
    # If your ATECC access must be serialized, wrap the call with _device_lock
    fn = OPS[op]
    return fn(iters, payload)

@app.post("/sha256_cpu")

def sha256_cpu():
    """
    Request JSON:
      {
        "op": "op_sha256_cpu",             # operation name
        "iters": 100000,            # total iterations for this worker
        "concurrency": 4,           # threads on this worker
        "payload": {...}            # optional op-specific inputs
      }
    Response JSON:
      {
        "ok": true, "op": "...", "iters": 100000,
        "duration_sec": 1.23, "throughput_ops_per_sec": 81234.0,
        "errors": 0, "hostname": "pi5-a", "details": {...}
      }
    """

    data = request.get_json(force=True) or {}
    op = str(data.get("op", "sha256_cpu"))
    total_iters = int(data.get("iters", 1_000_000))
    concurrency = max(1, int(data.get("concurrency", 1)))
    payload = data.get("payload", {}) or {}

    base = total_iters // concurrency
    shards = [base] * concurrency
    shards[-1] += total_iters - base * concurrency # distribute remainder

    start = time.perf_counter()
    errors = 0
    results = []

    def task(n):
        nonlocal errors
        try:
            r = run_op(op, n, payload)  # expected {"done": n, ...optional...}
            return r
        except Exception as e:
            errors += 1
            return {"done": 0, "error": str(e)}

    with cf.ThreadPoolExecutor(max_workers=concurrency) as ex:
        for res in cf.as_completed([ex.submit(task, n) for n in shards]):
            results.append(res.result())

    dur = time.perf_counter() - start
    done = sum(r.get("done", 0) for r in results)
    detail_merge = {"shards": len(shards)}

    return jsonify({
        "ok": True,
        "op": op,
        "iters": total_iters,
        "concurrency": concurrency,
        "duration_sec": dur,
        "throughput_ops_per_sec": (done / dur) if dur > 0 else None,
        "errors": errors,
        "hostname": os.uname().nodename,
        "details": detail_merge,
    })

@app.get("/health")
def health():
    return jsonify({"ok": True, "hostname": os.uname().nodename})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("KEYCRATE_PORT", "5000")))