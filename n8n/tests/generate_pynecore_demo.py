"""Create a reproducible, downloadable PyneCore CI comparison package.

All bars are SYNTHETIC and the PyneCore test script is hand-authored.
Do not present as TradingView-origin CSV or as an actual PyneComp conversion.
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "pine-parity"))
from test_pynecore_bridge import FIXTURE, SYMBOL, bars_csv
from pynecore_worker import execute_job
from keypoint_parity import compare_keypoints

OUT = Path(os.environ.get("INVESTMENT_DEMO_OUTPUT", "/tmp/investment-pynecore-ci-evidence")).resolve()
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    artifacts, data, results = root / "artifacts", root / "data", root / "results"
    artifacts.mkdir()
    data.mkdir()
    results.mkdir()
    source = artifacts / "synthetic_fixture.py"
    source.write_text(FIXTURE, encoding="utf-8")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    good = data / "reference.csv"
    good.write_text(bars_csv(), encoding="utf-8")
    jobfile = data / "job.json"
    jobfile.write_text(json.dumps({
        "job_id": "synthetic-pynecore-parity-20bars",
        "compiled_python": str(source),
        "python_sha256": digest,
        "reference_csv": str(good),
        "plot_mapping": {"Price": "TV Price"},
        "syminfo": SYMBOL,
        "compiler_reference": "HANDWRITTEN_PYNECORE_FIXTURE_NOT_PYNECOMP",
    }), encoding="utf-8")
    with os.scandir(root):
        env = {
            "INVESTMENT_ISOLATED_PYNECORE_WORKER": "1",
            "INVESTMENT_PYNECORE_ARTIFACT_ROOT": str(artifacts),
            "INVESTMENT_PYNECORE_DATA_ROOT": str(data),
            "INVESTMENT_PYNECORE_RESULT_ROOT": str(results),
        }
        old = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        try:
            resultfile = execute_job(jobfile)
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
    result = json.loads(resultfile.read_text(encoding="utf-8"))
    pycsv = Path(result["pynecore_csv_path"]).read_text(encoding="utf-8")
    goodcsv = good.read_text(encoding="utf-8")
    badcsv = bars_csv(corrupt_reference=True)
    match = compare_keypoints(goodcsv, pycsv)
    mismatch = compare_keypoints(badcsv, pycsv)
    assert match["aligned_bars"] == 20 and match["mismatch_total"] == 0, match
    assert mismatch["status"] == "KEYPOINTS_DIFFER" and mismatch["mismatch_total"] == 1, mismatch

    (OUT / "reference_synthetic_match.csv").write_text(goodcsv, encoding="utf-8")
    (OUT / "reference_synthetic_mismatch.csv").write_text(badcsv, encoding="utf-8")
    (OUT / "pynecore_actual_worker_output.csv").write_text(pycsv, encoding="utf-8")
    (OUT / "result.json").write_text(json.dumps({
        "source": "SYNTHETIC_TEST_FIXTURE_NOT_TRADINGVIEW",
        "pynecore": result,
        "same_data": match,
        "one_plot_divergence": mismatch,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "TEST_INSTRUCTIONS.md").write_text("""# WF-02 PyneCore 비교 수동 테스트

이 파일의 봉은 **합성 테스트 데이터**입니다. TradingView에서 가져온 실제 데이터가 아니며,
Python 테스트 스크립트는 PyneComp가 생성한 코드가 아닌 수동 작성 PyneCore 코드입니다.

1. https://investment-pine-parity-review-production.up.railway.app/ 을 엽니다.
2. 페이지 아래쪽의 **TradingView ↔ PyneCore 중요 지점 비교**에서
   'TradingView CSV' 위치에 `reference_synthetic_mismatch.csv`를 올립니다.
3. 'PyneCore CSV' 위치에 `pynecore_actual_worker_output.csv`를 올립니다.
4. 비교 버튼을 누르면 '불일치'가 나타나고 **TV Price** 플롯의 열 번째 봉 (bar index 9)
   하나가 중요 지점에 표시되어야 합니다.
5. 첫 번째 파일을 `reference_synthetic_match.csv`로 바꿔 다시 비교하면
   봉 20개가 일치하고 불일치 0개여야 합니다.
6. 주문/체결 컬럼이 없으므로 '완전 동등성 승인'이 아니라 '부분 수치 비교'로 분류됩니다.

이 패키지는 GitHub Actions의 **실제 PyneCore ScriptRunner** 실행에서 생성되었습니다.
실제 TradingView 원본 동등성 검증에는 해당 전략의 사용 권한, 동일 OHLCV,
입력값/수수료/슬리피지/진입·청산 설정 및 주문 이벤트 수집이 추가로 필요합니다.
""", encoding="utf-8")
print(json.dumps({"output": str(OUT), "files": sorted(x.name for x in OUT.iterdir()),
                  "aligned_bars": match["aligned_bars"], "mismatches": mismatch["mismatch_total"]}))
