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
import csv
import io
from datetime import datetime, timezone
import json
import os
import re
import sys
from pathlib import Path
from pynecore_bridge import ParityInputError, read_reference, run_compiled_pynecore


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
    # Generate a real PyneCore plot CSV, *not* a second TV reference copied
    # under another name. The original input supplies only shared OHLCV.
    parsed_bars, _ = read_reference(reference_file.read_text(encoding="utf-8-sig"))
    if len(parsed_bars) != len(result["series"]):
        raise ParityInputError("RESULT_BAR_COUNT_MISMATCH")
    buffer = io.StringIO()
    reference_labels = list(payload["plot_mapping"].values())
    if len(reference_labels) != len(set(reference_labels)) or not reference_labels:
        raise ParityInputError("DUPLICATE_OR_MISSING_REFERENCE_PLOTS")
    if any(x in ("time", "open", "high", "low", "close", "volume") for x in reference_labels):
        raise ParityInputError("PLOT_MAPPING_OVERWRITES_OHLC")
    columns = ["time", "open", "high", "low", "close", "volume"] + reference_labels
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    for bar, series in zip(parsed_bars, result["series"]):
        if series["time_ms"] != bar["timestamp"]:
            raise ParityInputError("PYNECORE_SERIES_TIMESTAMP_MISMATCH")
        line = {
            "time": datetime.fromtimestamp(bar["timestamp"] / 1000, timezone.utc).isoformat(),
            **{k: bar[k] for k in ("open", "high", "low", "close", "volume")},
        }
        for plot, label in payload["plot_mapping"].items():
            value = series["plots"].get(plot)
            line[label] = "" if value is None else value
        writer.writerow(line)
    result["pynecore_csv_source"] = "ACTUAL_PYNECORE_SCRIPT_RUNNER"
    result["order_signal_parity_verified"] = False
    result["tradingview_reference_authenticated"] = False
    result["job_id"] = job_id
    result["input_reference"] = str(reference_file)
    result["compiler_reference"] = payload.get("compiler_reference")
    output_root = os.getenv("INVESTMENT_PYNECORE_RESULT_ROOT")
    if not output_root:
        raise ParityInputError("RESULT_ROOT_NOT_CONFIGURED")
    folder = Path(output_root).resolve(strict=True)
    csv_output = folder / (job_id + ".pynecore.csv")
    # A successful result must be immutable. Do not silently overwrite a
    # previous CSV on retry with the same Job ID.
    with csv_output.open("x", encoding="utf-8", newline="") as out:
        out.write(buffer.getvalue())
    result["pynecore_csv_path"] = str(csv_output)
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
