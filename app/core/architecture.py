ARCHITECTURE = {
    "name": "Autonomous Investor Backend",
    "orchestration": "thin-python-orchestrator",
    "frontend_contract": "REST/WebSocket through our FastAPI only",
    "layers": [
        {"id": "research-intelligence", "engines": ["TradingAgents", "FinRobot V2"], "output": "ResearchBundle"},
        {"id": "autonomous-rd", "engines": ["RD-Agent(Q)"], "input": "ResearchBundle", "output": "Hypothesis / ExperimentResult"},
        {"id": "quant-model-validation", "engines": ["Qlib", "Chronos", "Stable-Baselines3", "Ray RLlib", "vectorbt"], "native_outputs": ["ModelScore", "Forecast", "PolicyAction"], "normalized_output": "Signal"},
        {"id": "allocation", "engines": ["FinRL-Trading contract", "Riskfolio-Lib", "PyPortfolioOpt"], "output": "TargetPortfolio / RiskDecision"},
        {"id": "runtime", "engines": ["NautilusTrader"], "input": "RiskDecision", "output": "ExecutionReport", "modes": ["backtest", "paper", "live"]},
    ],
}
