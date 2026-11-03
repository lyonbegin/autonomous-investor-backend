"""Offline worker entrypoint for real PyneComp-generated PyneCore chart jobs.

Usage:
  INVESTMENT_ISOLATED_PYNECORE_WORKER=1 \
  INVESTMENT_PYNECORE_ARTIFACT_ROOT=/worker/artifacts \
  INVESTMENT_PYNECORE_DATA_ROOT=/worker/data \
  INVESTMENT_PYNECORE_RESULT_ROOT=/worker/results \
  python pynecore_worker.py --job /worker/data/job.json

Launcher must ensure OS/container isolation (no network/secrets, resource limits).
This module itself does NOT sandbox Python or authenticate TradingView exports.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path
from pynecore_bridge import ParityInputError, run_compiled_pynecore


def _under_root(value, environment_name):
    root = os.getenv(environment_name)
    if not root:
        raise ParityInputError("WORKER_ROOT_NOT_CONFIGURED:" + environment_name)
    resolved_root = Path(root).resolve(strict=True)
    path = Path(value).resolve(strict=True)
    if not path.is_relative_to(resolved_root) or not path.is_file():
        raise ParityInputError("WORKER_PATH_NOT_ALLOWED:" + environment_name)
    return path


def execute_job(job_path):
    if os.getenv("INVESTMENT_ISOLATED_PYNECORE_WORKER") != "1":
        raise ParityInputError("ISOLATED_PYNECORE_WORKER_REQUIRED")
    job_file = _under_root(job_path, "INVESTMENT_PYNECORE_DATA_ROOT")
    if job_file.stat().st_size > 32768:
        raise ParityInputError("JOB_FILE_TOO_LARGE")
    payload = json.loads(job_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not re.fullmatch(
        r"[A-Za-z0-9_-]{1,80}", str(payload.get("job_id", ""))
    ):
        raise ParityInputError("JOB_ID_REQUIRED")
    job_id = payload["job_id"]
    reference_file = _under_root(payload.get("reference_csv", ""),
                                 "INVESTMENT_PYNECORE_DATA_ROOT")
    if reference_file.stat().st_size > 1_000_000:
        raise ParityInputError("REFERENCE_CSV_TOO_LARGE")
    result = run_compiled_pynecore(
        payload["compiled_python"],
        payload["python_sha256"],
        reference_file.read_text(encoding="utf-8-sig"),
        payload["syminfo"],
        payload["plot_mapping"],
        inputs=payload.get("inputs"),
    )
    result["job_id"] = job_id
    result["input_reference"] = str(reference_file)
    result["compiler_reference"] = payload.get("compiler_reference")
    output_root = os.getenv("INVESTMENT_PYNECORE_RESULT_ROOT")
    if not output_root:
        raise ParityInputError("RESULT_ROOT_NOT_CONFIGURED")
    folder = Path(output_root).resolve(strict=True)
    output = folder / (job_id + ".json")
    # Never overwrite a completed job: retries require an explicit new job_id.
    with output.open("x", encoding="utf-8") as out:
        json.dump(result, out, ensure_ascii=False, allow_nan=False)
    return output


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True)
    args = parser.parse_args(argv)
    try:
        path = execute_job(args.job)
    except (ParityInputError, KeyError, ValueError, OSError) as exc:
        print(json.dumps({"status": "WORKER_FAILED",
                          "reason": str(exc)[:180]}), file=sys.stderr)
        return 2
    print(json.dumps({"status": "WORKER_RESULT_WRITTEN", "path": str(path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
