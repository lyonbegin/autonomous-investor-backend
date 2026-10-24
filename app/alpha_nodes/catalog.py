"""AlphaForge-style node capabilities tied to actual repository module surfaces.

'connected' means an executable handler is implemented in api.py. 'contract_only'
means that the API exposes the node's typed interface but never pretends it ran.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NodeDefinition:
    key: str
    label: str
    group: str
    module: str
    native_call: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    state: str = "contract_only"
    description: str = ""
    side_effect: str = "none"


def node(key: str, label: str, group: str, module: str, native_call: str,
         inputs: str, outputs: str, *, connected: bool = False,
         side_effect: str = "none", description: str = "") -> NodeDefinition:
    return NodeDefinition(key, label, group, module, native_call,
                          tuple(x.strip() for x in inputs.split(",") if x.strip()),
                          tuple(x.strip() for x in outputs.split(",") if x.strip()),
                          "connected" if connected else "contract_only", description, side_effect)


DEFINITIONS: tuple[NodeDefinition, ...] = (
    node("tradingview.script_source", "Pine 원본 읽기", "source", "app.core.tradingview", "GET /api/v1/tradingview/scripts/{script_id}/source", "script_id", "source,source_hash,script_id", connected=True),
    node("tradingview.scripts", "공개 스크립트 목록", "source", "app.core.tradingview", "GET /api/v1/tradingview/scripts/catalog", "limit,offset,script_type", "items,count", connected=True),
    node("tradingview.market", "시장 스캐너", "source", "app.core.tradingview", "GET /api/v1/tradingview/markets/{market}", "market,limit", "items,count", connected=True),
    node("tradingview.agent", "에이전트 상세", "source", "app.core.tradingview", "GET /api/v1/tradingview/agent-plans/{agent_id}", "agent_id", "agent", connected=True),
    node("tradingview.ideas", "트레이딩 아이디어", "source", "app.core.tradingview", "GET /api/v1/tradingview/ideas/live", "page,sort", "items,count", connected=True),
    node("source_registry.list", "전략 원본 레지스트리", "source", "app.core.source_registry", "GET /api/v1/strategy-sources", "limit", "items,count", connected=True),
    node("pine.inspect", "Pine 원본 정적 검사", "pine", "app.alpha_nodes.api", "inspect_pine", "source", "source_hash,pine_version,declared_type,limitations", connected=True, description="Parsing/compilation NOT implied"),
    node("pine.compile_python", "Pine → Python", "pine", "app.core.strategy_spec", "compile_pine_to_spec + future Python codegen", "source,source_id", "python_artifact,compile_report"),
    node("pine.parity", "TradingView-Nautilus 동일성", "pine", "app.core.strategy_spec", "future parity validator", "strategy_package,reference_signals", "parity_report"),
    node("quant.handoff_status", "연구 에이전트 인수 상태", "validation", "app.core.quant_lab", "GET /api/v1/quant/handoff/status", "min_score", "status", connected=True),
    node("quant.experiment_create", "실험 등록", "validation", "app.core.quant_lab", "POST /api/v1/quant/experiments/from-agent/{agent_id}", "agent_id,symbols", "experiment", connected=True, side_effect="research"),
    node("quant.experiment_run", "기존 StrategySpec 검증 실행", "validation", "app.core.quant_lab", "POST /api/v1/quant/experiments/{id}/run", "experiment_id,max_symbols,commission_bps,slippage_bps", "experiment", connected=True, side_effect="research", description="Does not run Nautilus backtest"),
    node("quant.experiment_results", "검증 성과", "validation", "app.core.quant_lab", "GET /api/v1/quant/experiments/{id}/results", "experiment_id", "items,count", connected=True),
    node("quant.pipeline", "엔진 파이프라인 상태", "validation", "app.core.quant_lab", "GET /api/v1/quant/pipeline", "", "pipeline", connected=True),
    node("nautilus.engine_probe", "Nautilus 엔진 상태", "execution", "app.core.integrations", "GET /api/v1/integrations?probe_runtime=true", "", "installed,import_ok,version", connected=True),
    node("nautilus.plan_rebalance", "목표 비중→주문 미리보기", "execution", "app.orchestration.runtime", "plan_rebalance", "target,equity,prices,current_quantities,min_notional", "order_intents", connected=True),
    node("nautilus.backtest", "Nautilus 정밀 백테스트", "execution", "app.integrations.nautilus", "BacktestEngine", "strategy_package,data_ref,cost_model", "backtest_report"),
    node("nautilus.paper", "Nautilus 모의거래", "execution", "app.integrations.nautilus", "paper execution node", "strategy_package,account_ref,risk_approval", "order_events,positions", side_effect="paper"),
    node("nautilus.live", "Nautilus 실거래", "execution", "app.integrations.nautilus", "live execution node", "strategy_package,account_ref,risk_approval", "order_events,positions", side_effect="live"),
    node("nautilus.risk_decision", "주문 위험 승인", "execution", "app.core.contracts", "RiskDecision", "order_intents,limits,positions", "risk_decision"),
    node("nautilus.order_events", "실제 주문·체결 이벤트", "execution", "app.integrations.nautilus", "native order event lifecycle", "run_id", "orders,fills,positions"),
    node("engine.tradingagents.research", "TradingAgents 시장 연구", "research", "app.integrations.tradingagents", "TradingAgentsBridge.run", "instrument,trade_date,asset_type", "research_bundle,signal"),
    node("engine.finrobot.research", "FinRobot 기업 연구", "research", "app.integrations.finrobot", "FinRobotBridge.research", "ticker,model_config", "finrobot_result"),
    node("engine.finrobot.dcf", "FinRobot DCF", "research", "app.integrations.finrobot", "FinRobotBridge.dcf", "ticker,model_config", "valuation"),
    node("engine.finrobot.earnings", "FinRobot 실적 분석", "research", "app.integrations.finrobot", "FinRobotBridge.earnings", "ticker,model_config", "earnings"),
    node("engine.rdagent.quant_loop", "RD-Agent 연구 루프", "research", "app.integrations.rdagent", "RDAgentQuantBridge.run", "research_bundle,step_n", "research_trace"),
    node("engine.qlib.predict", "Qlib 모델 예측", "quant", "app.integrations.qlib", "QlibBridge.predict", "model_ref,dataset_ref,segment", "model_scores"),
    node("engine.qlib.backtest", "Qlib 백테스트", "quant", "app.integrations.qlib", "QlibBridge.backtest", "strategy_ref,executor_ref,exchange_ref", "metrics"),
    node("engine.qlib.risk_analysis", "Qlib 수익률 리스크", "quant", "qlib.contrib.evaluate", "risk_analysis", "returns,frequency", "metrics", connected=True),
    node("engine.chronos.forecast", "Chronos 가격 예측", "quant", "app.integrations.chronos", "ChronosBridge.predict_df", "model_ref,history,horizon", "forecast"),
    node("engine.sb3.train", "SB3 강화학습", "learning", "app.integrations.sb3", "StableBaselinesBridge.learn", "environment_ref,policy_config", "model_ref,training_report"),
    node("engine.sb3.predict", "SB3 정책 추론", "learning", "app.integrations.sb3", "StableBaselinesBridge.predict", "model_ref,observation", "policy_action"),
    node("engine.rllib.train", "RLlib 분산 학습", "learning", "app.integrations.rllib", "RLlibBridge.train", "environment_ref,algorithm_config", "model_ref,training_report"),
    node("engine.rllib.infer", "RLlib 정책 추론", "learning", "app.integrations.rllib", "RLlibBridge.forward_inference", "model_ref,batch", "policy_action"),
    node("engine.vectorbt.signals", "vectorbt 신호 백테스트", "validation", "app.integrations.vectorbt", "VectorBTBridge.from_signals", "close,entries,exits,fees,slippage", "metrics", connected=True),
    node("engine.vectorbt.orders", "vectorbt 주문 백테스트", "validation", "app.integrations.vectorbt", "VectorBTBridge.from_orders", "close,orders", "metrics"),
    node("engine.finrl.weights", "FinRL 자산 비중", "allocation", "app.integrations.finrl", "FinRLBridge.generate_weights", "strategy_ref,data_ref", "weights"),
    node("engine.finrl.equal_weight", "FinRL 균등 비중", "allocation", "app.integrations.finrl", "FinRLBridge.equal_weight + generate_weights", "instruments", "weights", connected=True),
    node("engine.riskfolio.optimize", "Riskfolio 위험 최적화", "allocation", "app.integrations.riskfolio", "RiskfolioBridge.optimize", "returns,model,rm,obj", "weights", connected=True),
    node("engine.pypfopt.optimize", "PyPortfolioOpt 최적화", "allocation", "app.integrations.pypfopt", "PyPortfolioOptBridge.efficient_frontier", "expected_returns,covariance,objective", "weights,performance", connected=True),
    node("market.history", "과거 OHLCV", "source", "app.core.market_history", "GET /api/v1/quant/market-data/history", "symbol,horizon,market,country", "bars,provider"),
    node("macro.snapshot", "거시 지표", "source", "app.core.macro_data", "GET /api/v1/quant/macro/snapshot", "", "snapshot", connected=True),
)

NODE_MAP = {item.key: item for item in DEFINITIONS}
assert len(NODE_MAP) == len(DEFINITIONS), "Duplicate Alpha node key"


def serialized(item: NodeDefinition) -> dict:
    return {
        "key": item.key, "label": item.label, "group": item.group,
        "module": item.module, "native_call": item.native_call,
        "inputs": [{"name": n, "type": "json"} for n in item.inputs],
        "outputs": [{"name": n, "type": "json"} for n in item.outputs],
        "state": item.state, "side_effect": item.side_effect,
        "description": item.description,
    }
