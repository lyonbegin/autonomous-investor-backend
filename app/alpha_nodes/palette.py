"""Node palette JSON for an AlphaForge-style visual canvas.

Every palette entry comes from a real Python function signature already
registered in app/alpha_nodes/inventory.py. It does not claim a native model is
installed or trained; 'callable' means an authenticated route exists.
"""
from __future__ import annotations

from fastapi import HTTPException

from app.alpha_nodes.inventory import OPERATIONS, OPERATION_MAP
from app.alpha_nodes.runtime import _validate_gate

LABELS = {
    "tradingagents": "TradingAgents",
    "finrobot": "FinRobot V2",
    "rdagent": "RD-Agent",
    "qlib": "Qlib",
    "chronos": "Chronos",
    "sb3": "Stable-Baselines3",
    "rllib": "Ray RLlib",
    "vectorbt": "vectorbt",
    "finrl": "FinRL-Trading",
    "riskfolio": "Riskfolio-Lib",
    "pypfopt": "PyPortfolioOpt",
    "nautilus": "NautilusTrader",
    "orchestration": "엔진 오케스트레이션",
    "tradingview": "TradingView 원본",
    "quantlab": "Quant Lab",
}

ROLES = {
    "tradingagents": "research",
    "finrobot": "research",
    "rdagent": "research",
    "qlib": "validation",
    "chronos": "forecast",
    "sb3": "learning",
    "rllib": "learning",
    "vectorbt": "validation",
    "finrl": "allocation",
    "riskfolio": "risk",
    "pypfopt": "allocation",
    "nautilus": "execution",
    "orchestration": "orchestration",
    "tradingview": "source",
    "quantlab": "validation",
}


def node_palette_entry(op: dict) -> dict:
    try:
        _validate_gate(op)
        gate = {"state": "not_blocked", "reason": None}
    except HTTPException as exc:
        gate = {"state": "blocked", "reason": str(exc.detail)}
    ports = [
        {
            "id": p["name"],
            "direction": "input",
            "required": p["required"],
            "type": p["annotation"],
            "kind": p["kind"],
            "default": p["default"],
        }
        for p in op["inputs"]
    ]
    ports.append({"id": "result", "direction": "output", "required": False,
                  "type": op["output"], "kind": "value"})
    if op["call_kind"] in ("instance", "constructor", "class"):
        ports.append({"id": "instance", "direction": "output", "required": False,
                      "type": "native Python handle", "kind": "handle"})
    ports.append({"id": "status", "direction": "output", "required": False,
                  "type": "str", "kind": "status"})
    return {
        "id": op["id"],
        "label": op["function"].replace("_", " "),
        "project_label": LABELS.get(op["engine"], op["engine"]),
        "engine": op["engine"],
        "role": ROLES.get(op["engine"], "extension"),
        "module": op["source_path"],
        "source_line": op["source_line"],
        "source_layer": op["source"],
        "function": op["function"],
        "ports": ports,
        "endpoint": op["endpoint"],
        "execution_gate": gate,
        "native_environment_verified": False,
    }


def node_palette(*, role: str | None = None, engine: str | None = None,
                 search: str | None = None) -> dict:
    ops = OPERATIONS
    if role:
        ops = [o for o in ops if ROLES.get(o["engine"], "extension") == role]
    if engine:
        ops = [o for o in ops if o["engine"] == engine]
    if search:
        needle = search.casefold()
        ops = [
            o for o in ops
            if needle in (o["id"] + " " + o["source_path"] + " " + o["function"]).casefold()
        ]
    entries = [node_palette_entry(o) for o in ops]
    return {"count": len(entries), "nodes": entries,
            "contract": "AlphaForge function ports v1",
            "note": "Execution route existence does not prove the native engine or its required data are ready."}


def template_graphs() -> dict:
    examples = [
        {
            "key": "tradingview_open_strategy_to_source",
            "label": "TradingView 공개 전략 선택 → 원본 Pine 조회",
            "description": "실제 카탈로그는 strategies 필터를 사용하고 source 조회에는 script_id_part가 필요합니다.",
            "graph": {
                "name": "TradingView 공개 전략 원본 읽기",
                "background": True,
                "nodes": [
                    {
                        "id": "strategy_catalog",
                        "operation_id": "tradingview.service.api.script_catalog",
                        "arguments": {"limit": 1, "offset": 0, "script_type": "strategies"},
                    },
                    {
                        "id": "pine_source",
                        "operation_id": "tradingview.service.api.script_source",
                        "arguments": {
                            "script_id_part": {
                                "$node": "strategy_catalog",
                                "path": "result.items.0.script_id_part",
                            }
                        },
                    },
                ],
            },
        },
        {
            "key": "vectorbt_signal_to_stats",
            "label": "vectorbt 신호 백테스트 → 실제 래퍼 성과 통계",
            "description": "네이티브 vectorbt 환경 필요. 시세·신호 배열은 설명용 샘플입니다.",
            "graph": {
                "name": "vectorbt Native Portfolio 생성과 통계",
                "background": True,
                "nodes": [
                    {
                        "id": "portfolio",
                        "operation_id": "vectorbt.app.bridge.from_signals",
                        "arguments": {
                            "close": [100.0, 102.0, 101.0, 104.0],
                            "entries": [True, False, False, False],
                            "exits": [False, False, False, True],
                        },
                    },
                    {
                        "id": "stats",
                        "operation_id": "vectorbt.lab.bridge.stats",
                        "arguments": {
                            "portfolio": {"$node": "portfolio", "path": "result"}
                        },
                    },
                ],
            },
        },
        {
            "key": "nautilus_rebalance_preview",
            "label": "목표 포트폴리오 → Nautilus 주문 의도 생성 (주문 전송 없음)",
            "description": "실제 기존 plan_rebalance() 호출. 제출되지 않는 설명용 주문 계획입니다.",
            "graph": {
                "name": "Nautilus 주문 계획 사전 계산",
                "background": False,
                "nodes": [
                    {
                        "id": "order_preview",
                        "operation_id": "orchestration.orchestration.runtime.plan_rebalance",
                        "arguments": {
                            "target": {
                                "$contract": "TargetPortfolio",
                                "strategy_id": "EXAMPLE-ONLY",
                                "as_of": "2026-10-25T00:00:00Z",
                                "weights": [{"instrument": "AAPL", "weight": 0.2}],
                            },
                            "equity": 1000,
                            "prices": {"AAPL": 100},
                            "current_quantities": {"AAPL": 0},
                        },
                    }
                ],
            },
        },
    ]
    return {"count": len(examples), "templates": examples,
            "note": "Templates are sample workflow definitions, not evidence of live-market execution."}
