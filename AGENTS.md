# Repository Guidelines

## Project Structure & Module Organization
The orchestration entry point is `main.py`, which reads `config.yaml` to split work across remote workers. Each worker runs `worker.py`, a small Flask app that dispatches operation handlers declared in `ops.py`. Keep new hardware operations in `ops.py` and expose them through the worker just like `sha256_cpu`. Shared fixtures or scripts belong in top-level modules; long-lived assets (firmware blobs, datasets) should live under `usr/` with clear naming.

## Build, Test, and Development Commands
- `python3 -m venv .venv && source .venv/bin/activate` creates an isolated environment; reuse the provided `usr/bin/venv` only for quick smoke tests.
- `pip install -r requirements.txt` installs Flask, Requests, and PyYAML.
- `python3 worker.py` launches a local worker on port 5000; add `KEYCRATE_PORT=5001` for parallel instances.
- `python3 main.py --config config.yaml` runs the controller with the default operation; override fields (e.g., `--op sleep_us --iters 50000 --conc 8`) to probe new workloads.
- `curl http://localhost:5000/health` verifies worker readiness before load tests.

## Coding Style & Naming Conventions
Target Python 3.11+ and follow PEP 8: four-space indentation, snake_case for functions, and UPPER_CASE for constants or environment keys. Place concurrency helpers next to their call sites and document non-obvious synchronization with brief comments. Operations should return dicts mirroring the existing `{"done": iters}` contract so aggregation remains consistent.

## Testing Guidelines
Add fast unit tests under `tests/` using `pytest`; mirror module names (e.g., `tests/test_ops.py`) and prefix async/concurrency scenarios with `test_threaded_...`. Run `python3 -m pytest` locally and include boundary tests for new ops plus regression coverage for failure cases. Provide manual verification notes (controller output snippet or curl health check) when introducing device-dependent logic or external services.

## Commit & Pull Request Guidelines
Use concise, present-tense commit subjects (`worker: serialize device access`) and keep bodies wrapped at 72 characters with context on load targets, payload formats, or threading changes. PRs should summarize the change, reference related issues, list test output, and call out configuration updates impacting `config.yaml` or deployment scripts. Attach logs or screenshots when touching throughput reporting so reviewers can validate before merging.

## Configuration & Security Tips
Treat `config.yaml` as user-editable runtime data; never hard-code secrets or internal IPs in code. When sharing worker URLs, mask private network details in public artifacts. Use environment variables (e.g., `KEYCRATE_PORT`, `KEYCRATE_TIMEOUT`) for host-specific overrides and document them in PRs to keep deployments reproducible.
