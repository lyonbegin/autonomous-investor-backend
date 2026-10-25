"""Ten *synthetic* operational scenarios with durable step/event audit.

No upstream engines, live prices, broker orders or n8n instance are invoked.
Use this only to prove orchestration state, routing, and operator UI behavior.
n8n can start a scenario by HTTP; the UI can start it directly as well.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException

FLOWS = {
    "F01": "전략 상시 수집", "F02": "전략 적격성 심사",
    "F03": "에이전트 자동 할당", "F04": "에이전트 반복 거래",
    "F05": "독립 감사", "F06": "병렬 검증",
    "F07": "전략 거버넌스", "F08": "전략 개선·배포",
    "F09": "공통 계좌 위험", "F10": "복구·운영 감시",
}

# Steps are an explicit, immutable simulated test script, not engine execution.
# Each node exposes the exact conceptual I/O that a production event will carry.
def step(flow: str, node: str, action: str, details: str, *,
         inputs: dict[str, Any] | None = None,
         outputs: dict[str, Any] | None = None,
         checks: list[str] | None = None,
         next_flows: list[str] | None = None) -> dict[str, Any]:
    return {
        "flow": flow, "node": node, "action": action, "details": details,
        "inputs": inputs or {}, "outputs": outputs or {},
        "checks": checks or [], "next_flows": next_flows or [],
    }

S = step
SCENARIOS: dict[str, dict[str, Any]] = {
    "01-new-strategy": {
        "title": "신규 전략 발견과 유휴 에이전트 할당",
        "purpose": "검증되지 않은 전략이 에이전트에 할당되지 않는지 확인",
        "steps": [
            S("F01","discover","StrategyVersionCreated","S103/v1 수집",outputs={"strategy":"S103/v1"},next_flows=["F02"]),
            S("F02","eligibility","EligibilityPending","컴파일 및 적격성 점검",inputs={"strategy":"S103/v1"},outputs={"status":"EVALUATING"},next_flows=["F06"]),
            S("F06","queue","ValidationJobQueued","백테스트 작업 J001 접수",outputs={"job":"J001","status":"queued"}),
            S("F06","worker","ValidationCompleted","독립 검증 작업 통과",inputs={"job":"J001"},outputs={"status":"PASS"},next_flows=["F02"]),
            S("F02","publish","StrategyAvailable","합격 전략을 풀에 등록",outputs={"strategy":"S103/v1","status":"AVAILABLE"},next_flows=["F03"]),
            S("F03","claim","StrategyAssigned","유휴 Agent C가 원자적 할당",inputs={"agent":"C","strategy":"S103/v1"},outputs={"assignment":"AC-S103","lease_epoch":1},checks=["validated_before_claim","exclusive_assignment"],next_flows=["F04"]),
            S("F04","start","AgentActivated","Agent C paper 세션 활성화",outputs={"agent":"C","mode":"paper","strategy":"S103/v1"}),
        ],
    },
    "02-version-update": {
        "title": "거래 중 새 전략 버전 발견",
        "purpose": "기존 버전은 새 버전 검증·배포 승인 전까지 유지",
        "steps": [
            S("F01","update","StrategyVersionCreated","S100/v3 원본 갱신 발견",outputs={"strategy":"S100/v3"},next_flows=["F02"]),
            S("F02","eligibility","EligibilityPending","새 버전 등록",outputs={"strategy":"S100/v3"},next_flows=["F06"]),
            S("F04","keep","AgentContinues","Agent A는 기존 v2로 계속 거래",outputs={"agent":"A","strategy":"S100/v2"},checks=["version_pinned"]),
            S("F06","verify","ValidationCompleted","v3 별도 검증 완료",outputs={"strategy":"S100/v3","status":"PASS"},next_flows=["F08"]),
            S("F08","approve","ReleaseApproved","검증된 v3 배포 승인",outputs={"strategy":"S100/v3","approved":True},next_flows=["F10"]),
            S("F10","reconcile","AccountReconciled","이전 주문·포지션 대조",outputs={"consistent":True},next_flows=["F08"]),
            S("F08","promote","AgentMigrationApproved","Agent A의 실행 버전 변경",outputs={"agent":"A","from":"S100/v2","to":"S100/v3"},checks=["release_after_validation"],next_flows=["F04"]),
            S("F04","restart","AgentActivated","Agent A가 v3로 재개",outputs={"agent":"A","strategy":"S100/v3"}),
        ],
    },
    "03-capital-race": {
        "title": "두 에이전트가 동시에 계좌 현금을 초과해 매수",
        "purpose": "공통 위험 관리자만 원자적으로 현금 예약",
        "steps": [
            S("F04","intent-a","OrderIntent","A가 가상 800만원 주문",outputs={"agent":"A","notional":8000000},next_flows=["F09"]),
            S("F04","intent-b","OrderIntent","B가 가상 800만원 주문",outputs={"agent":"B","notional":8000000},next_flows=["F09"]),
            S("F09","reserve-a","RiskApproved","A 주문 800만원 예약",inputs={"cash":10000000,"request":8000000},outputs={"reserved":8000000,"available":2000000},checks=["no_overreservation"]),
            S("F09","reject-b","RiskRejected","잔여 200만원으로 B 주문 거절",inputs={"available":2000000,"request":8000000},outputs={"agent":"B","decision":"REJECT"},checks=["insufficient_cash_rejected"],next_flows=["F05"]),
            S("F05","audit","AuditFindingCreated","경쟁 요청과 거절 근거 기록",outputs={"severity":"INFO","agent":"B"}),
        ],
    },
    "04-partial-fill": {
        "title": "100주 주문 중 60주 부분체결 후 재매수 신호",
        "purpose": "미체결 40주를 다음 거래에서 고려하고 중복 주문을 금지",
        "steps": [
            S("F04","order","OrderIntent","가상 BUY 100주",outputs={"qty":100,"price":10000},next_flows=["F09"]),
            S("F09","reserve","CapitalReserved","100만원 예약",outputs={"reserved":1000000}),
            S("F04","fill","OrderPartiallyFilled","가상 60주 체결",outputs={"filled":60,"remaining":40},next_flows=["F05","F09"]),
            S("F09","settle","CapitalSettled","현금 60만원 정산·40만원 예약",outputs={"cash":9400000,"reserved":400000}),
            S("F05","audit","FillVerified","체결 수량 및 주문 상태 감사",outputs={"match":True}),
            S("F04","next-signal","SignalGenerated","두 번째 가상 BUY 100 신호",outputs={"qty":100}),
            S("F04","suppress","DuplicateOrderPrevented","미체결 40주 조회 후 추가 주문 차단",inputs={"position":60,"open_qty":40},outputs={"new_orders":0},checks=["no_duplicate_submit"]),
        ],
    },
    "05-long-backtest": {
        "title": "세 가지 장시간 검증 중 거래·감사 계속",
        "purpose": "검증 작업의 완료를 기다리지 않고 거래 이벤트 진행",
        "steps": [
            S("F06","queue-1","ValidationQueued","Nautilus J001 접수",outputs={"job":"J001","engine":"nautilus"}),
            S("F06","queue-2","ValidationQueued","Qlib J002 접수",outputs={"job":"J002","engine":"qlib"}),
            S("F06","queue-3","ValidationQueued","RLlib J003 접수",outputs={"job":"J003","engine":"rllib"}),
            S("F04","trade","OrderFilled","검증 중 Agent A의 가상 10주 체결",outputs={"agent":"A","filled":10},next_flows=["F05","F09"]),
            S("F09","settle","CapitalSettled","체결 금액 정산",outputs={"account_consistent":True}),
            S("F05","audit","FillVerified","독립 감사 정상",outputs={"status":"OK"}),
            S("F06","complete-2","ValidationCompleted","Qlib J002 결과 도착",outputs={"job":"J002","status":"PASS"}),
            S("F04","market","MarketEventProcessed","Agent B 다음 봉 처리",outputs={"agent":"B"}),
            S("F06","complete-3","ValidationCompleted","RLlib J003 결과 도착",outputs={"job":"J003","status":"PASS"}),
            S("F06","complete-1","ValidationCompleted","Nautilus J001 최종 결과 도착",outputs={"job":"J001","status":"PASS"},checks=["trading_continued_during_validation"]),
        ],
    },
    "06-strategy-drift": {
        "title": "실거래 성과 악화로 전략 정지와 v2 개선",
        "purpose": "감사 판단·정지·재검증·신버전 가용성을 분리",
        "steps": [
            S("F05","finding","DriftDetected","S101/v1 성과 이상",outputs={"severity":"WARNING"},next_flows=["F07"]),
            S("F07","review","GovernanceReview","REVIEW 판정",outputs={"decision":"REVIEW"},next_flows=["F06"]),
            S("F06","recheck","ValidationCompleted","재검증 실패",outputs={"strategy":"S101/v1","status":"FAIL"},next_flows=["F05"]),
            S("F05","critical","AuditFindingCreated","위험도 CRITICAL 상승",outputs={"severity":"CRITICAL"},next_flows=["F09","F07"]),
            S("F09","halt","TradingSuspended","v1 신규 주문 금지",outputs={"strategy":"S101/v1","allow_new_orders":False}),
            S("F07","suspend","GovernanceDecision","v1 SUSPEND",outputs={"decision":"SUSPEND"},next_flows=["F08"]),
            S("F08","revise","RevisionRequested","S101/v2 개선 요청",outputs={"strategy":"S101/v2"},next_flows=["F01"]),
            S("F01","version","StrategyVersionCreated","v2 후보 저장",outputs={"strategy":"S101/v2"},next_flows=["F02"]),
            S("F02","candidate","EligibilityPending","v2 재심사",outputs={"status":"EVALUATING"},next_flows=["F06"]),
            S("F06","pass","ValidationCompleted","v2 검증 PASS",outputs={"strategy":"S101/v2","status":"PASS"}),
            S("F02","available","StrategyAvailable","v2 후보 AVAILABLE; 자동 운영 교체 안 함",outputs={"strategy":"S101/v2","deployed":False},checks=["no_auto_rollout","suspended_version_blocked"]),
        ],
    },
    "07-broker-timeout": {
        "title": "브로커 주문 응답 타임아웃과 접수 여부 불명",
        "purpose": "확정 전 동일 주문 재제출 금지 및 ID로 대조",
        "steps": [
            S("F04","send","OrderSubmitted","가상 50주 매수 요청 O001",outputs={"client_order_id":"O001","qty":50},next_flows=["F09"]),
            S("F09","reserve","CapitalReserved","50만원 예약",outputs={"reserved":500000}),
            S("F04","timeout","OrderStateUnknown","브로커 응답 타임아웃",outputs={"order":"O001","state":"UNKNOWN"},next_flows=["F05","F10"]),
            S("F05","finding","ExecutionAuditFinding","주문 상태 미확정 조사",outputs={"severity":"WARNING"}),
            S("F04","suppress","DuplicateOrderPrevented","동일 주문 재제출 차단",outputs={"new_orders":0},checks=["no_duplicate_submit"]),
            S("F10","lookup","BrokerOrderReconciled","기존 client_order_id로 접수 확인",inputs={"order":"O001"},outputs={"state":"ACKED"},checks=["unknown_order_reconciled"],next_flows=["F04"]),
            S("F04","restore","OrderStateRestored","원래 주문으로 상태 추적 계속",outputs={"order":"O001","state":"ACKED"}),
        ],
    },
    "08-agent-crash": {
        "title": "Agent A 장애 후 Agent C로 안전한 이전",
        "purpose": "낡은 Lease/토큰 차단 후 계좌 대조 및 원자적 재할당",
        "steps": [
            S("F10","detect","AgentHeartbeatLost","A 연결 해제 감지",outputs={"agent":"A"},next_flows=["F09"]),
            S("F09","fence","AgentFenced","A epoch=1 차단",outputs={"agent":"A","blocked_epoch":1}),
            S("F04","reject-old","OrderRejected","이전 Worker A 주문 거부",outputs={"agent":"A","decision":"REJECT"},checks=["stale_worker_rejected"]),
            S("F10","reconcile","AccountReconciled","주문·포지션 브로커 기준 대조",outputs={"consistent":True},next_flows=["F03"]),
            S("F03","reassign","StrategyAssigned","Agent C가 S100/v2를 epoch=2로 승계",outputs={"agent":"C","strategy":"S100/v2","epoch":2},checks=["exclusive_assignment"],next_flows=["F04"]),
            S("F04","activate","AgentActivated","C 새 거래 루프 시작",outputs={"agent":"C","epoch":2},next_flows=["F05"]),
            S("F05","audit","RecoveryAudited","복구 후 배정 이력 감사",outputs={"status":"OK"}),
        ],
    },
    "09-unsupported-pine": {
        "title": "최신 Pine 코드 변환 불가, 이전 승인 버전 유지",
        "purpose": "지원하지 않는 전략은 풀 격리하고 기존 운용은 유지",
        "steps": [
            S("F01","update","StrategyVersionCreated","S100/v3 발견",outputs={"strategy":"S100/v3"},next_flows=["F02"]),
            S("F02","parse","PineCompatibilityRejected","지원하지 않는 Pine 문법",outputs={"strategy":"S100/v3","status":"REJECTED"}),
            S("F03","deny","AssignmentDenied","C의 미검증 v3 할당 거부",outputs={"agent":"C","allowed":False},checks=["rejected_not_assigned"]),
            S("F04","keep","AgentContinues","A는 승인된 v2 운용 계속",outputs={"agent":"A","strategy":"S100/v2"},checks=["version_pinned"]),
            S("F09","risk","RiskApproved","기존 v2 가상 주문 위험 검사",outputs={"approved":True}),
            S("F05","audit","TradeAudited","기존 버전 신호 일치 감사",outputs={"status":"OK"}),
        ],
    },
    "10-strategy-retire": {
        "title": "전략 폐기 결정 후 기존 포지션 정리와 에이전트 해제",
        "purpose": "전략 폐기가 오픈 포지션 삭제나 즉시 재배정으로 이어지지 않음",
        "steps": [
            S("F05","drift","AuditFindingCreated","S101/v1 누적 악화",outputs={"severity":"WARNING"},next_flows=["F07"]),
            S("F07","review","GovernanceReview","재검증 요구",outputs={"decision":"REVIEW"},next_flows=["F06"]),
            S("F06","fail","ValidationCompleted","기간외 검증 FAIL",outputs={"status":"FAIL"},next_flows=["F07"]),
            S("F07","retire","StrategyRetired","S101/v1 신규 할당 금지",outputs={"strategy":"S101/v1","decision":"RETIRE"},next_flows=["F04","F03"]),
            S("F04","drain","AgentDraining","Agent B 포지션 정리 모드",outputs={"agent":"B","state":"DRAINING"}),
            S("F09","risk","ExitRiskChecked","기존 가상 20주 청산 정책 검증",outputs={"exit_allowed":True}),
            S("F04","sell","PaperOrderFilled","가상 PAPER 20주 청산",outputs={"filled":20,"mode":"paper"},next_flows=["F05","F09"]),
            S("F05","audit","ExitAudited","정리 거래와 전략 상태 감사",outputs={"status":"OK"}),
            S("F09","settle","CashSettled","가상 현금 20만원 정산",outputs={"cash":10200000}),
            S("F10","reconcile","PositionReconciled","잔여 보유 0주 확인",outputs={"position":0},next_flows=["F03"]),
            S("F03","release","AgentReleased","Agent B IDLE 복귀",outputs={"agent":"B","state":"IDLE"},checks=["no_release_before_flat"]),
        ],
    },
}

_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="scenario-simulation")
_LOCK = threading.RLock()
_INITIALIZED: set[str] = set()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _connect() -> sqlite3.Connection:
    path = str(Path(os.environ.get("SCENARIO_DB_PATH", "/tmp/autonomous_scenario_runs.sqlite3")).resolve())
    Path(path).parent.mkdir(exist_ok=True, parents=True)
    with _LOCK:
        db = sqlite3.connect(path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA busy_timeout=30000")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS scenario_runs(
          id TEXT PRIMARY KEY, scenario_id TEXT NOT NULL, state TEXT NOT NULL,
          total_steps INTEGER NOT NULL, completed_steps INTEGER NOT NULL,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL, error TEXT);
        CREATE TABLE IF NOT EXISTS scenario_events(
          id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
          step_index INTEGER NOT NULL, flow_id TEXT NOT NULL,
          node_id TEXT NOT NULL, action TEXT NOT NULL, state TEXT NOT NULL,
          event_json TEXT NOT NULL, recorded_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_scenario_events_run ON scenario_events(run_id,id);
        """)
        if path not in _INITIALIZED:
            db.execute("UPDATE scenario_runs SET state='interrupted',updated_at=? WHERE state IN ('queued','running')", (_now(),))
            _INITIALIZED.add(path)
        db.commit()
    return db


def catalog() -> dict:
    items = []
    for scenario_id, info in SCENARIOS.items():
        used = list(dict.fromkeys(s["flow"] for s in info["steps"]))
        items.append({"id":scenario_id,"title":info["title"],"purpose":info["purpose"],
                      "steps":len(info["steps"]),"flows":used, "mode":"SYNTHETIC_SIMULATION"})
    return {"count":len(items),"flows":FLOWS,"scenarios":items,
            "disclaimer":"All events, decisions, cash and fills are synthetic; no original engine, market feed or broker is called."}


def detail(scenario_id: str) -> dict:
    info = SCENARIOS.get(scenario_id)
    if info is None:
        raise HTTPException(status_code=404,detail="Unknown scenario")
    return {"id":scenario_id,**info,"mode":"SYNTHETIC_SIMULATION"}


def start(scenario_id: str, *, interval_ms: int = 160) -> dict:
    if scenario_id not in SCENARIOS:
        raise HTTPException(status_code=404,detail="Unknown scenario")
    if not 0 <= interval_ms <= 1500:
        raise HTTPException(status_code=422,detail="interval_ms must be 0..1500")
    run_id=uuid.uuid4().hex
    now=_now()
    with _connect() as db:
        db.execute("INSERT INTO scenario_runs VALUES(?,?,?,?,?,?,?,NULL)",
                   (run_id,scenario_id,"queued",len(SCENARIOS[scenario_id]["steps"]),0,now,now))
    _POOL.submit(_run,run_id,interval_ms)
    return {"run_id":run_id,"scenario_id":scenario_id,"state":"queued",
            "poll":f"/api/v1/alpha/scenarios/runs/{run_id}",
            "events":f"/api/v1/alpha/scenarios/runs/{run_id}/events?after=0"}


def _write(run_id: str, index: int, item: dict, state: str, *, done: bool = False) -> None:
    with _connect() as db:
        db.execute("""INSERT INTO scenario_events
          (run_id,step_index,flow_id,node_id,action,state,event_json,recorded_at)
          VALUES(?,?,?,?,?,?,?,?)""",
                   (run_id,index,item["flow"],item["node"],item["action"],state,
                    json.dumps(item,ensure_ascii=False),_now()))
        if done:
            db.execute("UPDATE scenario_runs SET completed_steps=?,updated_at=? WHERE id=?",
                       (index+1,_now(),run_id))


def _run(run_id: str, interval_ms: int) -> None:
    try:
        with _connect() as db:
            row=db.execute("SELECT * FROM scenario_runs WHERE id=?", (run_id,)).fetchone()
            if row is None or row["state"]!="queued":
                return
            db.execute("UPDATE scenario_runs SET state='running',updated_at=? WHERE id=?", (_now(),run_id))
        assert row is not None
        steps=SCENARIOS[row["scenario_id"]]["steps"]
        for index, item in enumerate(steps):
            _write(run_id,index,item,"running")
            if interval_ms:
                time.sleep(interval_ms/1000)
            # Scenarios use scripted deterministic state changes; never invoke native engines.
            _write(run_id,index,item,"success",done=True)
        with _connect() as db:
            db.execute("UPDATE scenario_runs SET state='completed',updated_at=? WHERE id=?",
                       (_now(),run_id))
    except Exception as exc:
        with _connect() as db:
            db.execute("UPDATE scenario_runs SET state='failed',error=?,updated_at=? WHERE id=?",
                       (str(exc)[:300],_now(),run_id))


def snapshot(run_id: str) -> dict:
    with _connect() as db:
        run=db.execute("SELECT * FROM scenario_runs WHERE id=?", (run_id,)).fetchone()
        if run is None:
            raise HTTPException(status_code=404,detail="Unknown run")
        rows=db.execute("SELECT * FROM scenario_events WHERE run_id=? ORDER BY id",(run_id,)).fetchall()
    latest={}
    events=[]
    for row in rows:
        item=json.loads(row["event_json"])
        event={"sequence":row["id"],"index":row["step_index"],"flow":row["flow_id"],
               "node":row["node_id"],"action":row["action"],"status":row["state"],
               "at":row["recorded_at"],"details":item["details"],
               "inputs":item["inputs"],"outputs":item["outputs"],"checks":item["checks"],
               "next_flows":item["next_flows"]}
        events.append(event)
        latest[item["flow"]]=event["status"]
    return {
        "run_id":run_id,"scenario_id":run["scenario_id"],"scenario_title":SCENARIOS[run["scenario_id"]]["title"],
        "status":run["state"],"mode":"SYNTHETIC_SIMULATION",
        "total_steps":run["total_steps"],"completed_steps":run["completed_steps"],
        "progress_pct":round(run["completed_steps"]*100/run["total_steps"],1),
        "flow_states":latest,"events":events,"error":run["error"],
    }


def events_after(run_id: str, after: int = 0) -> dict:
    snap = snapshot(run_id)
    return {"run_id":run_id,"status":snap["status"],"events":
            [e for e in snap["events"] if e["sequence"]>after],
            "last_event_id":snap["events"][-1]["sequence"] if snap["events"] else after}
