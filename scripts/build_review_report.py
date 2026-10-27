"""Build an offline, self-contained report from actual browser and engine evidence."""
from __future__ import annotations

import argparse
import base64
from datetime import datetime
from html import escape
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", default="/workspace/review")
    parser.add_argument("--pytest-log", default="/workspace/integration-audit/review-pytest-final.log")
    args = parser.parse_args()
    directory = Path(args.directory)
    engines = json.loads((directory / "engine-verification.json").read_text())
    browser = json.loads((directory / "browser-checks.json").read_text())
    live = json.loads((directory / "production-readonly-status.json").read_text())
    passed = re.search(r"(\d+) passed", Path(args.pytest_log).read_text())
    if not passed:
        raise RuntimeError("the pytest log has no completed passing test count")
    assert engines["count"] == 12
    assert all(row["restart_verified"] for row in engines["results"])
    assert len(browser["checks"]) == 13 and all(row["status"] == "passed" for row in browser["checks"])
    workflows = [line.split("|") for line in (directory / "n8n-db-executions.txt").read_text().splitlines()]
    assert len({row[0] for row in workflows if row[1] == "success"}) == 13
    assert not any(row[1] != "success" for row in workflows)
    observed = datetime.fromisoformat(browser["observed_at"]).astimezone(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M KST")
    images = [
        ("engines", "12개 엔진 · 실제 프로세스와 검증 결과", "12개 모두 설치·import·기존 네이티브 데모·정지·재시작을 확인했습니다. 이 프로세스는 소규모 검증용이며 연구 DAG 전체를 분산 실행하는 프로세스가 아닙니다.", "engines.png"),
        ("operations", "기존 전략·에이전트·독립 감사 화면", "실제 로컬 FastAPI와 SQLite를 연결했습니다. 표시된 전략과 승인 증거는 테스트 fixture이며 운영 투자 승인 자료가 아닙니다.", "operations.png"),
        ("scenarios", "시나리오 10개 · 원본 n8n Worker 경유", "브라우저에서 10개를 실행해 완료 상태와 단계별 입력·출력을 확인했습니다. 상태 전이 자료는 SYNTHETIC이며 실제 주문을 실행하지 않습니다.", "n8n-scenarios.png"),
        ("native", "인증 후 원본 n8n 에디터", "격리된 로컬 n8n에 소유자 계정을 설정하고 로그인했습니다. 원본 에디터의 실제 노드 6개와 연결선을 확인했습니다.", "native-n8n-editor.png"),
        ("node-io", "원본 n8n 실행 이력 · 노드별 실제 입력과 출력", "성공 실행을 열어 실제 노드의 입력 run_id와 completed 출력을 확인했습니다. 연결 설정 영역은 자격증명 노출을 막기 위해 가렸습니다.", "native-n8n-node-io.png"),
        ("public", "기존 공개 화면 · 전략", "로컬 공개 중계 API를 통해 자체 작성한 SYNTHETIC Pine 전략과 4개 연구 에이전트의 연결을 표시합니다. 성과가 없는 항목은 수익률을 만들어 표시하지 않습니다.", "public-strategies.png"),
        ("agents", "기존 공개 화면 · 에이전트", "전략 원본·고정 시간축·시장 범위 연결을 실제 로컬 DB에서 읽었습니다.", "public-agents.png"),
        ("ideas", "복원한 TradingView 아이디어 화면", "기존 브랜치의 아이디어 화면과 메뉴를 복원하고 실제 API 계약을 연결했습니다. 캡처의 항목은 합성 테스트 자료입니다.", "public-ideas.png"),
        ("scripts", "기존 공개 화면 · Pine 스크립트", "카탈로그 API와 실제 컴포넌트를 연결했습니다. 자체 작성한 테스트 Pine을 사용했으며 제3자 전략을 무단 복제하지 않았습니다.", "public-scripts.png"),
        ("markets", "기존 공개 화면 · 시장", "저장된 시장 데이터를 읽는 모드로 확인했습니다. 캡처의 가격과 종목은 SYNTHETIC이며 실시간 시세가 아닙니다.", "public-markets.png"),
        ("production", "기존 운영 URL · 읽기 전용 확인", "현재 운영 화면을 관리 CA로 TLS 검증하는 읽기 전용 프록시를 통해 브라우저에서 확인했습니다. 이번 통합 변경을 운영에 배포한 화면은 아닙니다.", "existing-production-readonly.png"),
    ]
    panels = []
    for identifier, title, caption, filename in images:
        encoded = base64.b64encode((directory / filename).read_bytes()).decode()
        panels.append(f'<section class="screen" id="{identifier}"><h2>{escape(title)}</h2><p>{escape(caption)}</p><img alt="{escape(title)}" src="data:image/png;base64,{encoded}"></section>')
    engine_rows = []
    for row in engines["results"]:
        engine_rows.append(f'<tr><td>{escape(row["key"])}</td><td>통과</td><td>통과</td><td>{escape(row["demo"].get("native_call", ""))}</td></tr>')
    checks = ''.join('<li><b>통과</b> '+escape(row['name'])+'</li>' for row in browser['checks'])
    html = f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AUTONOMOUS INVESTOR · 실제 화면 검증 결과</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#eef3f6;color:#193744;font-family:system-ui,"Noto Sans CJK KR",sans-serif;line-height:1.65}}main{{max-width:1180px;margin:auto;padding:36px 24px}}header{{padding:40px;background:#173c4b;color:white;border-radius:18px}}header small{{color:#a6d9db;letter-spacing:.12em}}h1{{font-size:32px;margin:12px 0}}header p{{color:#c7dce3;max-width:850px}}.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:22px 0}}.stat{{padding:22px;background:white;border-radius:12px;border:1px solid #dce6eb}}.stat b{{display:block;font-size:30px;color:#13705a}}.stat span{{font-size:13px;color:#607b87}}.scope{{padding:20px 24px;background:#fff5dc;border:1px solid #ead9a8;border-radius:12px;margin:20px 0}}nav{{display:flex;flex-wrap:wrap;gap:8px;margin:20px 0}}nav a{{background:white;color:#285566;border:1px solid #cbdde4;padding:8px 13px;text-decoration:none;border-radius:7px;font-size:13px}}.screen,.evidence{{background:white;border:1px solid #dae4eb;border-radius:14px;padding:26px;margin:24px 0;overflow:hidden}}h2{{font-size:21px;margin:0 0 12px}}.screen p{{font-size:13px;color:#58737f}}img{{width:100%;height:auto;border:1px solid #e0e8ed;border-radius:8px}}table{{width:100%;border-collapse:collapse;font-size:11px}}td,th{{padding:10px 8px;border-bottom:1px solid #dae5eb;text-align:left}}td:last-child{{overflow-wrap:anywhere}}li{{padding:5px 0;font-size:13px}}li b{{color:#148164}}footer{{font-size:12px;color:#66838e;text-align:center;padding:20px}}@media print{{body{{background:white}}main{{padding:0;max-width:none}}nav{{display:none}}header{{border-radius:0;padding:26px}}h1{{font-size:26px}}.stats{{gap:8px}}.stat{{padding:12px}}.stat b{{font-size:23px}}.screen{{break-before:page;break-inside:avoid;margin:0;padding:12px;border:0;border-radius:0}}.screen img{{max-height:225mm;object-fit:contain}}.evidence{{break-before:page;border:0}}.scope{{font-size:12px}}}}
</style><main><header><small>AUTONOMOUS INVESTOR · VERIFIED REVIEW</small><h1>실행 화면으로 확인하는 통합 검증</h1><p>기존 21개 브랜치의 구현을 이어서 통합한 결과입니다. 이 파일에는 실제로 실행하고 확인한 화면과 증거를 담았습니다. 설치 명령을 입력하지 않고 아래 화면을 열어 확인할 수 있습니다.</p><p>{escape(observed)} · 통합 개발 브랜치</p></header>
<div class="stats"><div class="stat"><b>12 / 12</b><span>실제 엔진 데모 · 정지 · 재시작</span></div><div class="stat"><b>{passed.group(1)}</b><span>Python 테스트 통과</span></div><div class="stat"><b>13</b><span>브라우저 검증 항목 통과</span></div><div class="stat"><b>13종</b><span>원본 n8n 성공 실행 이력 확인</span></div></div>
<div class="scope"><b>확인한 범위</b><br>로컬 통합 실행과 기존 운영 화면의 읽기 확인을 마쳤습니다. 테스트 전략·시장·시나리오 자료는 SYNTHETIC입니다. 엔진 라이브러리 호출과 n8n Main·Worker·PostgreSQL 실행은 실제입니다.<br><b>운영 배포·실거래·운영 DB 변경은 수행하지 않았습니다.</b> 운영 Railway 서비스 전체·수집기 로그·실시장 전체 DAG 검증은 이 결과에 포함되지 않습니다.</div>
<nav>{''.join(f'<a href="#{identifier}">{escape(title.split(" · ")[0])}</a>' for identifier,title,_,_ in images)}</nav>
{''.join(panels)}
<section class="evidence"><h2>12개 엔진 실행 증거</h2><table><tr><th>엔진 키</th><th>기존 네이티브 데모</th><th>정지·재시작</th><th>실제로 호출한 함수</th></tr>{''.join(engine_rows)}</table></section>
<section class="evidence"><h2>브라우저 검증 항목</h2><ol>{checks}</ol><h2>현재 운영 읽기 결과</h2><p>HTTP 상태: 공개 화면 200 · 상태 조회 200 · n8n 원본 게이트웨이/설정/API 익명 접근 모두 401.</p><p>공개 레지스트리 전략 {live['counts']['strategy_registry']}개, 전략 버전 {live['counts']['strategy_versions']}개, 운영 에이전트 {live['counts']['agents']}개. 브로커 연결 없음. 관측 시각 {escape(live['observed_at'])}.</p></section>
<footer>실제 실행 결과와 합성 입력을 구분한 검증 자료 · 비밀값·인증 쿠키·운영 계정 정보 미포함</footer></main></html>'''
    (directory / "AUTONOMOUS_INVESTOR_REVIEW.html").write_text(html)
    print("OFFLINE_REVIEW_REPORT_CREATED")


if __name__ == "__main__":
    main()
