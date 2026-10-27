"""Ten traceable and isolated investment-system scenario definitions.

Every step is a synthetic BUSINESS EVENT, not a live-native engine invocation.
The same immutable step IDs are consumed by self-hosted n8n workflows or by
the explicitly labeled Python internal test runner.
"""
from __future__ import annotations

from typing import Any

FLOW_NAMES = {
    "F01": "전략 상시 수집", "F02": "전략 적격성 심사",
    "F03": "에이전트 자동 할당", "F04": "에이전트 반복 거래",
    "F05": "독립 거래 감사", "F06": "장시간 병렬 검증",
    "F07": "전략 거버넌스", "F08": "전략 개선·배포",
    "F09": "계좌 위험·자본 관리", "F10": "장애 복구·대조",
}


def step(key: str, flow: str, label: str, action: str, **params: Any) -> dict:
    assert flow in FLOW_NAMES
    return {"id": key, "flow": flow, "label": label,
            "action": action, "params": params}


SCENARIOS: dict[int, dict] = {
    1: {
        "title": "신규 Pine 전략 발견 → 검증 → 유휴 에이전트 할당",
        "why": "검증 완료 전에 전략이 할당되지 않고 거래 중인 기존 에이전트는 영향받지 않아야 합니다.",
        "steps": [
            step("discover", "F01", "S103/v1 신규 원본 수집", "discover", strategy="S103/v1"),
            step("screen", "F02", "Pine 호환성 심사", "screen", strategy="S103/v1", supported=True),
            step("queue", "F06", "별도 백테스트 작업 등록", "job_queue", job="J1", strategy="S103/v1"),
            step("worker", "F06", "백테스트 워커 시작", "job_start", job="J1"),
            step("result", "F06", "전략 검증 완료 PASS", "job_done", job="J1", result="PASS", eligible=True),
            step("claim", "F03", "유휴 Agent C 독점 할당", "claim", agent="C", strategy="S103/v1"),
            step("runtime", "F04", "Agent C Paper Runtime 기동", "runtime_start", agent="C"),
        ],
    },
    2: {
        "title": "원본 전략 v3 등장 중 Agent A는 v2 유지",
        "why": "새 버전이 발견되어도 실행 중인 버전이 덮어쓰이지 않아야 합니다.",
        "steps": [
            step("new_version", "F01", "S100/v3 소스 변경 발견", "discover", strategy="S100/v3"),
            step("compatibility", "F02", "v3 별도 호환성 검사", "screen", strategy="S100/v3", supported=True),
            step("queue", "F06", "v3 검증 큐 등록", "job_queue", job="J2", strategy="S100/v3"),
            step("start", "F06", "v3 검증 작업 시작", "job_start", job="J2"),
            step("v2_still_on", "F04", "검증 중 Agent A는 v2 유지", "pinned", agent="A", strategy="S100/v2"),
            step("complete", "F06", "v3 검증 PASS", "job_done", job="J2", result="PASS", eligible=True),
            step("approve", "F08", "v3 배포 승인 기록", "release", strategy="S100/v3"),
            step("reconcile", "F10", "기존 주문·포지션 상태 대조", "reconcile", agent="A"),
            step("switch", "F08", "Agent A 안전하게 v3 전환", "migrate", agent="A", strategy="S100/v3"),
            step("resume", "F04", "v3 버전 고정 실행 재개", "pinned", agent="A", strategy="S100/v3"),
        ],
    },
    3: {
        "title": "두 에이전트가 같은 현금을 동시에 요구",
        "why": "공통 계좌의 원자적 자금 예약이 중복 주문 초과를 막아야 합니다.",
        "steps": [
            step("signal_a", "F04", "Agent A 800만원 매수 의도", "signal", agent="A", qty=80, price=100000),
            step("reserve_a", "F09", "A 주문 O1 자금 800만원 예약", "reserve", agent="A", order="O1", qty=80, price=100000),
            step("signal_b", "F04", "Agent B 800만원 매수 의도", "signal", agent="B", qty=80, price=100000),
            step("reject_b", "F09", "B 주문 자금 부족으로 차단", "reject_capital", agent="B", qty=80, price=100000),
            step("audit_b", "F05", "B 위험 거절 감사 기록", "audit", kind="capital_rejected"),
        ],
    },
    4: {
        "title": "100주 주문 중 60주 부분체결 → 중복 매수 방지",
        "why": "부분체결·미체결 수량을 다음 거래 신호에 반영해야 합니다.",
        "steps": [
            step("buy", "F04", "100주 매수 신호 생성", "signal", agent="A", qty=100, price=10000),
            step("reserve", "F09", "주문 O1 생성·현금 예약", "reserve", agent="A", order="O1", qty=100, price=10000),
            step("partial", "F04", "O1 중 60주 체결", "fill", order="O1", qty=60),
            step("settle", "F09", "체결 현금·잔여 40주 정산", "verify_capital"),
            step("audit", "F05", "부분체결과 전략 수량 대조", "audit", kind="partial_fill"),
            step("next_signal", "F04", "같은 100주 매수 신호 재발생", "signal", agent="A", qty=100, price=10000),
            step("duplicate", "F04", "미체결 40주 확인 → 중복 생성 차단", "prevent_duplicate", agent="A"),
        ],
    },
    5: {
        "title": "장시간 검증 3개가 실행되는 동안 거래와 감사 지속",
        "why": "검증 Job들이 서로 다른 시각에 끝나더라도 Agent Runtime과 감사는 멈추지 않습니다.",
        "steps": [
            step("j1", "F06", "Nautilus 장기 검증 J1 대기열 등록", "job_queue", job="J1", strategy="S100/v2", kind="Nautilus"),
            step("j2", "F06", "Qlib 검증 J2 대기열 등록", "job_queue", job="J2", strategy="S101/v1", kind="Qlib"),
            step("j3", "F06", "RLlib 검증 J3 대기열 등록", "job_queue", job="J3", strategy="S100/v2", kind="RLlib"),
            step("start1", "F06", "Nautilus Worker 시작", "job_start", job="J1"),
            step("start2", "F06", "Qlib Worker 시작", "job_start", job="J2"),
            step("start3", "F06", "RLlib Worker 시작", "job_start", job="J3"),
            step("trade", "F04", "검증 중 Agent A 10주 매수", "reserve", agent="A", order="O1", qty=10, price=10000),
            step("trade_fill", "F04", "Agent A 10주 체결", "fill", order="O1", qty=10),
            step("audit_tick", "F05", "검증 중 거래 감사 독립 진행", "audit", kind="trade_during_validation"),
            step("qlib_finish", "F06", "Qlib J2 완료", "job_done", job="J2", result="PASS"),
            step("rl_finish", "F06", "RLlib J3 완료", "job_done", job="J3", result="PASS"),
            step("nautilus_finish", "F06", "Nautilus J1 마지막 완료", "job_done", job="J1", result="PASS"),
        ],
    },
    6: {
        "title": "감사 성과 악화 → 기존 전략 차단, 새 버전 개선",
        "why": "감사와 전략 거버넌스·재검증·배포는 분리되어야 합니다.",
        "steps": [
            step("warning", "F05", "S101/v1 감사 WARNING", "audit", kind="performance_drift", severity="WARNING"),
            step("review", "F07", "전략 재심사 결정", "governance", strategy="S101/v1", decision="REVIEW"),
            step("job", "F06", "기간외 검증 작업 등록", "job_queue", job="J1", strategy="S101/v1"),
            step("running", "F06", "검증 워커 실행", "job_start", job="J1"),
            step("failure", "F06", "기간외 검증 FAIL", "job_done", job="J1", result="FAIL"),
            step("freeze", "F09", "S101/v1 신규 주문 차단", "block", strategy="S101/v1"),
            step("suspend", "F07", "S101/v1 상태 SUSPENDED", "governance", strategy="S101/v1", decision="SUSPEND"),
            step("revise", "F08", "개선 후보 S101/v2 요청", "revision_request", strategy="S101/v2"),
            step("source", "F01", "개선된 S101/v2 전략 등록", "discover", strategy="S101/v2"),
            step("eligible", "F02", "S101/v2 변환 가능 검사", "screen", strategy="S101/v2", supported=True),
            step("newjob", "F06", "S101/v2 검증 준비", "job_queue", job="J2", strategy="S101/v2"),
            step("newstart", "F06", "S101/v2 검증 시작", "job_start", job="J2"),
            step("pass", "F06", "새 버전 검증 PASS·미게시 유지", "job_done", job="J2", result="PASS", eligible=True),
            step("reject_old", "F04", "정지된 기존 버전 주문 차단 확인", "prevent_blocked", agent="B"),
        ],
    },
    7: {
        "title": "주문 응답 TIMEOUT → 미확정 주문 대조",
        "why": "TIMEOUT은 주문 거절이 아니므로 같은 주문을 재제출하면 안 됩니다.",
        "steps": [
            step("signal", "F04", "Agent A 50주 BUY", "signal", agent="A", qty=50, price=10000),
            step("order", "F09", "O1 주문·자금 예약", "reserve", agent="A", order="O1", qty=50, price=10000),
            step("timeout", "F04", "O1 응답 누락 UNKNOWN", "timeout", order="O1"),
            step("finding", "F05", "주문 무결성 추가 검사", "audit", kind="unknown_broker_state"),
            step("duplicate", "F04", "동일 주문 재전송 방지", "prevent_duplicate", agent="A"),
            step("query", "F10", "브로커 가상 상태 대조", "reconcile", agent="A"),
            step("ack", "F04", "동일 주문 ID 접수 확인", "ack", order="O1"),
        ],
    },
    8: {
        "title": "에이전트 Worker 장애 → fencing 후 재할당",
        "why": "새 Worker가 살아나도 기존 Worker의 늦은 주문을 차단해야 합니다.",
        "steps": [
            step("heartbeat", "F10", "Agent A Heartbeat 소실", "heartbeat_lost", agent="A"),
            step("fence", "F09", "기존 Agent A epoch 차단", "fence", agent="A"),
            step("old_signal", "F04", "구 Agent A의 매수 요청 차단", "prevent_blocked", agent="A"),
            step("compare", "F10", "기존 주문·포지션 대조", "reconcile", agent="A"),
            step("release", "F03", "이전 할당 Lease 해제", "release_agent", agent="A"),
            step("claim", "F03", "Agent C 새 fencing epoch로 할당", "claim", agent="C", strategy="S100/v2"),
            step("runtime", "F04", "Agent C v2 거래 재개", "runtime_start", agent="C"),
            step("audit", "F05", "구·신 에이전트 실행 격리 감사", "audit", kind="fenced_worker"),
        ],
    },
    9: {
        "title": "새 Pine 전략 버전에 미지원 문법 존재",
        "why": "v3가 파싱되지 않더라도 이미 검증된 v2 에이전트는 계속 작동합니다.",
        "steps": [
            step("discover", "F01", "S100/v3 새 소스 도착", "discover", strategy="S100/v3"),
            step("reject", "F02", "미지원 Pine 구문 거절", "screen", strategy="S100/v3", supported=False),
            step("no_claim", "F03", "Agent C는 거절 전략 Claim 불가", "claim_reject", agent="C", strategy="S100/v3"),
            step("v2", "F04", "Agent A는 S100/v2 그대로 운용", "pinned", agent="A", strategy="S100/v2"),
            step("order", "F09", "v2 정상 주문만 승인", "reserve", agent="A", order="O1", qty=5, price=10000),
            step("audit", "F05", "기존 v2 주문과 버전 대조", "audit", kind="pinned_v2_trading"),
        ],
    },
    10: {
        "title": "전략 폐기 결정 → 포지션 정리 후 에이전트 해제",
        "why": "전략 RETIRE는 기록 삭제가 아니라 신규 진입 금지 및 안전한 청산 과정입니다.",
        "steps": [
            step("position", "F04", "Agent B 기존 20주 포지션 확인", "seed_position", agent="B", qty=20),
            step("warning", "F05", "전략 성과 누적 이탈", "audit", kind="retirement_review", severity="WARNING"),
            step("review", "F07", "성과 재심사로 전환", "governance", strategy="S101/v1", decision="REVIEW"),
            step("job", "F06", "폐기 검증 Job 등록", "job_queue", job="J1", strategy="S101/v1"),
            step("start", "F06", "백테스트 재검증 시작", "job_start", job="J1"),
            step("failed", "F06", "재검증 결과 FAIL", "job_done", job="J1", result="FAIL"),
            step("retire", "F07", "S101/v1 RETIRED 확정", "governance", strategy="S101/v1", decision="RETIRE"),
            step("draining", "F04", "Agent B DRAINING", "drain", agent="B"),
            step("close_policy", "F09", "Paper 청산 승인·신규 주문 차단", "block", strategy="S101/v1"),
            step("sell", "F04", "기존 20주 가상 Paper 매도 체결", "liquidate", agent="B", qty=20, price=10000),
            step("audit", "F05", "폐기 주문 체결 감사", "audit", kind="retirement_fill"),
            step("reconcile", "F10", "포지션 0·미체결 0 확인", "reconcile", agent="B"),
            step("free", "F03", "에이전트 B 재사용 가능 상태", "release_agent", agent="B"),
        ],
    },
}

assert len(SCENARIOS) == 10
for _id, _scenario in SCENARIOS.items():
    _ids = [s["id"] for s in _scenario["steps"]]
    assert len(_ids) == len(set(_ids)), _id
    assert all(s["flow"] in FLOW_NAMES for s in _scenario["steps"])


def catalog() -> dict:
    """Immutable, declarative scenario topology shared by UI/n8n/API."""
    rows = []
    for scenario_id, spec in SCENARIOS.items():
        steps = spec["steps"]
        rows.append({
            "scenario_id": scenario_id, "title": spec["title"],
            "why": spec["why"], "count": len(steps),
            "flows": sorted({node["flow"] for node in steps}),
            "nodes": [{**node, "index": i, "next": [steps[i + 1]["id"]] if i + 1 < len(steps) else []}
                      for i, node in enumerate(steps)],
            "edges": [{"from": a["id"], "to": b["id"]}
                      for a, b in zip(steps, steps[1:])],
        })
    return {"count": len(rows), "flows": FLOW_NAMES, "scenarios": rows,
            "source": "synthetic investment architecture test catalogue",
            "native_engine_calls": False, "live_broker_calls": False}
