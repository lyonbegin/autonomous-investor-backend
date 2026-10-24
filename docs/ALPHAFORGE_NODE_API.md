# AlphaForge module API — existing twelve engine bridges

This implementation exposes the **actual callable methods** in existing Python wrappers. It does not claim to wrap every internal function in the twelve original upstream repositories.

## Source of truth
- 12 existing app/integrations/{engine}.py files
- 12 existing lab/bridges/{engine}_bridge.py files
- 6 existing app/orchestration/{module}.py files
- Exact upstream repositories and pinned revisions: lab/upstreams.toml
- Discovery: app/alpha_nodes/inventory.py (Python AST, no costly native imports)
- Execution: app/alpha_nodes/runtime.py (actual native wrapper calls, no simulated result)
- Endpoint registration: app/alpha_nodes/api.py

The initial GitHub Actions run confirms 12 projects, 30 modules, **117 per-function POST endpoints**, and 30 passing tests.

## API routes
All routes are under /api/v1/alpha on the existing FastAPI app.

- GET /projects — 12 project identities, origins, module/function counts
- GET /modules?engine=nautilus — modules with input/output fields and their function URLs
- GET /operations — all discovered methods, source lines, parameter signatures and guards
- GET /operations/{operation_id} — exact input/output contract of one method
- POST /modules/{engine}/{source}/{module}/{function}/execute — invoke one existing native wrapper callable
- GET /handles/{handle} — stateful Python object reference
- GET /jobs/{job_id} — long-running execution result
- POST /contracts/{model}/validate — validate existing Pydantic contracts

The source path component is app, lab, or orchestration.

## Project-specific callable examples

- TradingAgents: /modules/tradingagents/app/bridge/run/execute
- FinRobot V2: /modules/finrobot/app/bridge/research/execute
- RD-Agent: /modules/rdagent/app/bridge/run/execute
- Qlib: /modules/qlib/app/bridge/predict/execute
- Chronos: /modules/chronos/app/bridge/predict_df/execute
- Stable-Baselines3: /modules/sb3/app/bridge/learn/execute
- Ray RLlib: /modules/rllib/app/bridge/forward_inference/execute
- vectorbt: /modules/vectorbt/app/bridge/from_signals/execute
- FinRL-Trading: /modules/finrl/app/bridge/generate_weights/execute
- Riskfolio-Lib: /modules/riskfolio/app/bridge/optimize/execute
- PyPortfolioOpt: /modules/pypfopt/app/bridge/efficient_frontier/execute
- NautilusTrader: /modules/nautilus/app/bridge/backtest_engine_config/execute

Every function has its own path. This is not one generic "run engine" endpoint.

## Authentication and deployment

Set ALPHA_NODE_API_KEY to a private bearer-token value on the backend. All Alpha endpoints require Authorization: Bearer TOKEN. With no token configured, the API returns 503; with an incorrect token, 401. NEVER expose this key in a browser-side frontend.

Start with python -m uvicorn app.main:app --port 8080 after installing the dependencies. See /docs for OpenAPI.

The existing twelve native engines require their validated installed environment. For absent engines and invalid arguments the API returns explicit errors instead of fake data.

## Calling a function with native inputs

POST /api/v1/alpha/modules/orchestration/orchestration/runtime/plan_rebalance/execute

JSON:
{
  "arguments": {
    "target": {
      "$contract": "TargetPortfolio",
      "strategy_id": "PINE-001",
      "as_of": "2026-10-25T00:00:00Z",
      "weights": [{"instrument": "AAPL", "weight": 0.5}]
    },
    "equity": 1000,
    "prices": {"AAPL": 100},
    "current_quantities": {"AAPL": 1}
  }
}

This invokes the existing Python plan_rebalance function, returning native OrderIntent data. It does NOT submit trades.

Native objects such as trained models and vectorbt portfolios may be returned as {"$handle":"id"} and used as a parameter to the next node: {"arguments": {"portfolio": {"$handle": "id"}}}.

Input conversions include "$dataframe" to pandas.DataFrame, "$series" to pandas.Series, and "$contract" to existing Pydantic models. Longer jobs can be submitted with "background":true and polled at /jobs/{job_id}.

## Critical guardrails

- All native Nautilus order submit operations are exposed in metadata but return 403 pending a real risk/approval gateway.
- Costly AI research and model training require explicit backend flags ALPHA_ALLOW_RESEARCH and ALPHA_ALLOW_TRAINING.
- Handles/jobs are process-local and expire: this prototype must use one pinned runtime worker. Durable distributed queues, crash recovery, and durable artifacts are NOT implemented.
- The 117 endpoints cover existing project wrappers and orchestration. Full Pine-to-Python code generation, identical TradingView simulator semantics, fully configured Nautilus backtest datasets, broker adapters, and live-trade accounting are NOT falsely reported as completed.

## Tests

.github/workflows/alpha-node-api-tests.yml runs the actual FastAPI route tests, real plan_rebalance input/output, chained vectorbt object handles (native dependency isolated by a test double), authentication gates, and missing-dependency errors. The separate original integration-lab workflow validates co-installation of the twelve native libraries.
