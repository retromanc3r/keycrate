```text
 _  __            ____            _       
| |/ /___ _   _  / ___|_ __ _   _| |_ ___ 
| ' // _ \ | | | | |   | '__| | | | __/ _ \
| . \  __/ |_| | | |___| |  | |_| | ||  __/
|_|\_\___|\__, |  \____|_|   \__,_|\__\___|
         |___/      Secure Distributed Crypto
```

# KeyCrate

KeyCrate orchestrates distributed cryptographic workloads across remote workers. A controller process splits a target iteration count across Flask-based worker nodes that execute operations (CPU-bound or hardware-backed) and report performance metrics back to the caller.

## Highlights
- Distributed coordination: `main.py` fans out the configured workload across as many workers as you register in `config.yaml`.
- Concurrency aware: each worker shards its portion across local threads and tracks throughput, errors, and timing.
- Pluggable operations: add new hardware exercises in `ops.py` and reuse the same request/response contract for consistent aggregation.

## Repository Layout
- `main.py` – controller entry point that loads `config.yaml`, dispatches work, and aggregates worker stats.
- `worker.py` – Flask worker accepting `/sha256_cpu` requests, spawning threads per request, and delegating to `ops.py`.
- `ops.py` – catalog of operations; return dicts shaped like `{"done": iters}` to integrate cleanly.
- `usr/` – place long-lived assets (firmware blobs, datasets, fixtures) that need version control.
- `tests/` – add fast `pytest` suites here to guard new operations or regressions.

## Getting Started
1. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
   Use `source usr/bin/venv` only for quick smoke tests when a disposable environment is sufficient.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running a Worker
Start at least one worker before launching the controller. Each worker defaults to port `5000` but you can override it:
```bash
KEYCRATE_PORT=5000 python3 worker.py
```

Verify that the worker is healthy:
```bash
curl http://localhost:5000/health
```

If your hardware driver requires serialized access, wrap the operation call in `worker.py` with `_device_lock` to avoid concurrent device access.

## Running the Controller
Update `config.yaml` with the URLs of your workers (keep private addresses private when sharing configs) and the operation you want to run. Then execute:
```bash
python3 main.py --config config.yaml
```

Override settings on the command line to probe different loads:
```bash
python3 main.py --config config.yaml --op sleep_us --iters 50000 --conc 8 --timeout 120
```

Controller output summarizes each worker followed by aggregate throughput, iteration counts, and any errors the workers reported.

## Configuration Reference (`config.yaml`)
Treat this as runtime data—edit it per deployment without changing code.

| key                      | description                                                                 |
|--------------------------|-----------------------------------------------------------------------------|
| `workers`                | List of worker base URLs (e.g., `http://192.168.1.15:5000`).                |
| `op`                     | Default operation name to request (`sha256_cpu`, `sleep_us`, or custom).    |
| `total_iters`            | Total iterations to distribute across workers.                              |
| `concurrency_per_worker` | Thread count each worker should use for a request.                          |
| `payload`                | Operation-specific inputs (e.g., microsecond delay or device parameters).   |

Environment overrides:
- `KEYCRATE_PORT` – worker listen port (`worker.py`).
- `KEYCRATE_TIMEOUT` – optional controller-side override for request timeout (fallbacks to CLI `--timeout`).

## Available Operations
- `sha256_cpu` – CPU-bound SHA-256 hashing workload that streams digests to `hashdb.bin`.
- `sleep_us` – latency simulator that sleeps for `payload["micros"]` microseconds per iteration.

## Adding a New Operation
1. Implement a function in `ops.py` that accepts `(iters: int, payload: dict)` and returns `{"done": iters}` along with any extra fields you need.
2. Register the function in the `OPS` dict with a unique name.
3. (Optional) If the operation touches non-thread-safe hardware, guard it with `_device_lock` in `worker.py`.
4. Update `config.yaml` or run `main.py --op <your_op>` so the controller requests it.
5. Add regression tests in `tests/` and document any device prerequisites.

## Testing
Run fast unit tests with:
```bash
python3 -m pytest
```

Add boundary tests for new operations and record manual verification steps (controller output snippet or `curl /health`) when incorporating external devices.

## Troubleshooting & Tips
- Workers log errors in their JSON responses; the controller aggregates error counts to help spot failing nodes.
- Ensure workers can reach any device dependencies before dialing up concurrency.
- Adjust `--timeout` if running operations that take longer than the default 500 seconds.
- When sharing configs outside your network, mask or replace private worker URLs.

## License
KeyCrate is released under the terms of the [MIT License](LICENSE).
