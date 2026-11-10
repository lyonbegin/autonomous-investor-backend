"""Run research hypothesis on sha-pinned CSV; metadata alone is not authenticity."""
from __future__ import annotations
import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from research.intermarket import Parameters, backtest, read_verified_csv

STRATEGY_ID = "0CVvd49h"
PINE_SHA256 = "06728ba8446771d2e45c63f2fca0d8cce378c96b445836f47c82e279285c1852"
CASE_ID = "CME-PL-GC-ILLUSTRATION"


def run(*, csv_path: Path, csv_sha256: str, provider: str, provider_url: str,
        contract_definition: str, output_root: Path, config: Parameters) -> Path:
    bars = read_verified_csv(csv_path, csv_sha256)
    code_sha = hashlib.sha256(Path(__file__).with_name("intermarket.py").read_bytes()).hexdigest()
    trace = {"strategy_id": STRATEGY_ID, "original_pine_sha256": PINE_SHA256,
             "external_case_id": CASE_ID, "generated_python_sha256": code_sha,
             "market_data_sha256": csv_sha256.lower(),
             "market_data_provider_claim": provider,
             "market_data_source_url": provider_url,
             "contracts_and_roll_assumption": contract_definition,
             "parameters": asdict(config)}
    run_id = hashlib.sha256(json.dumps(trace, sort_keys=True).encode()).hexdigest()[:24]
    result = backtest(bars, config)
    document = {"run_id": run_id, "trace": trace, "bar_count": len(bars),
                "first_bar": bars[0]["timestamp"], "last_bar": bars[-1]["timestamp"],
                "provenance_status": "USER_SUPPLIED_METADATA_NOT_INDEPENDENTLY_VERIFIED",
                "validation_status": "FUNCTIONAL_BACKTEST_ONLY_NO_MARKET_DATA_AUTHENTICATION",
                "result": result}
    folder = output_root / STRATEGY_ID
    folder.mkdir(parents=True, exist_ok=True)
    output = folder / f"{run_id}.json"
    payload = json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if output.exists() and output.read_text(encoding="utf-8") != payload:
        raise FileExistsError(f"Immutable result-ID collision: {output}")
    output.write_text(payload, encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars-csv", required=True, type=Path)
    parser.add_argument("--bars-sha256", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--provider-url", required=True)
    parser.add_argument("--contract-definition", required=True)
    parser.add_argument("--output-root", type=Path, default=Path("research/results"))
    parser.add_argument("--lookback", type=int, default=20)
    parser.add_argument("--entry-z", type=float, default=2)
    parser.add_argument("--exit-z", type=float, default=0)
    parser.add_argument("--commission-per-contract", type=float, default=0)
    parser.add_argument("--slippage-per-oz", type=float, default=0)
    args = parser.parse_args()
    cfg = Parameters(args.lookback, args.entry_z, args.exit_z,
                     args.commission_per_contract, args.slippage_per_oz)
    print(run(csv_path=args.bars_csv, csv_sha256=args.bars_sha256,
              provider=args.provider, provider_url=args.provider_url,
              contract_definition=args.contract_definition,
              output_root=args.output_root, config=cfg))


if __name__ == "__main__":
    main()
