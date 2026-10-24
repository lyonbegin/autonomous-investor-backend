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

The initial GitHub Actions run confirms 12 projects, 30 modules, **117 engine/orchestration per-function POST endpoints**, and 30 passing tests.

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


## Extension: native workflow graphs + 20 actual source service API operations

The engine inventory is now **12 engines + 6 orchestration modules + 2 service modules**:
- 88 existing app/lab bridge functions for the 12 engines
- 29 existing orchestration functions
- 10 TradingView-service HTTP operations
- 10 Quant Lab HTTP operations
- **137 individual function endpoints, 32 modules** in total

These are existing module/API **boundaries**, not wholesale wrappers around every upstream Python internal.

TradingView service source locations:
- tradingview-service: app/api/tradingview_routes.py
- tradingview-service: app/core/tradingview.py

Quant Lab source:
- quant-lab-control: app/api/quant_routes.py

Exact service examples:
- /modules/tradingview/service/api/script_catalog/execute
- /modules/tradingview/service/api/script_source/execute
- /modules/tradingview/service/api/agent_plan/execute
- /modules/tradingview/service/api/market_stored/execute
- /modules/quantlab/service/api/quant_market_history/execute
- /modules/quantlab/service/api/quant_experiment_results/execute
- /modules/quantlab/service/api/quant_experiment_run/execute

TradingView script catalogs use script_type="strategies" (plural); source lookup requires the **script_id_part** identifier returned by the catalog. Do not use script_id interchangeably.

Backend-only environment:
- ALPHA_TRADINGVIEW_BASE=https://... (defaults to existing TradingView Railway service)
- ALPHA_QUANT_BASE=https://... (defaults to existing Quant Lab Railway service)
- ALPHA_TRADINGVIEW_TOKEN and ALPHA_QUANT_TOKEN (optional internal bearer tokens)
- ALPHA_ALLOW_QUANT_WRITES=true enables the two Quant Lab experiment mutation endpoints (default disabled)
- ALPHA_GRAPH_DB_PATH=/path/to/alpha-graph.sqlite3 (default /tmp/autonomous_alpha_graph.sqlite3)

Only HTTPS service base URLs are supported, other than loopback HTTP for isolated local tests. URL routes are fixed by the known server code; callers cannot supply arbitrary upstream URLs. The container requires network access to those two actual running services for real results.

### Visual AlphaForge node palette endpoints

- GET /api/v1/alpha/palette
- GET /api/v1/alpha/palette?role=execution
- GET /api/v1/alpha/palette?engine=tradingview
- GET /api/v1/alpha/palette/{operation_id}
- GET /api/v1/alpha/graphs/templates

The palette returns each **actual function** with a label, engine group, node inputs (required/default/type), output ports, source path, HTTP execution URL, and a safety gate status. "Not blocked" is not a claim of library/data availability.

### Execute connected graphs with real function I/O

- POST /api/v1/alpha/graphs/validate : validate dependencies, cycles, referenced nodes, known operation IDs, and dangerous-call guards; NEVER runs functions
- POST /api/v1/alpha/graphs/run : execute DAG steps in valid topological order (background by default)
- GET /api/v1/alpha/graphs/runs : list executed graph runs
- GET /api/v1/alpha/graphs/runs/{run_id} : every node status, redacted input snapshot, result, and errors
- GET /api/v1/alpha/graphs/runs/{run_id}/nodes/{node_id} : inspect one node

Example: select TradingView strategy from existing catalog and fetch original Pine source.

~~~json
{
  "name": "TradingView strategy → original Pine",
  "background": true,
  "nodes": [
    {
      "id": "catalog",
      "operation_id": "tradingview.service.api.script_catalog",
      "arguments": {
        "limit": 1, "offset": 0, "script_type": "strategies"
      }
    },
    {
      "id": "source",
      "operation_id": "tradingview.service.api.script_source",
      "arguments": {
        "script_id_part": {
          "$node": "catalog",
          "path": "result.items.0.script_id_part"
        }
      }
    }
  ]
}
~~~

The returned run includes a unique run_id. Background requests initially return queued and a poll endpoint; inline requests with background=false return full results. Node failures stop downstream execution. A cycle, missing operation or forbidden order operation is rejected before execution begins. 

Node linking format: {"$node":"previous-node-id","path":"result.some_key.0"}; the path is an exact JSON key traversal, not arbitrary Python code. References to native object handles are automatically normalized to {"$handle":"..."}.

**Limitations:** SQLite persists the run audit but native Python objects and in-flight jobs remain process-local; after a server restart in-flight runs become interrupted and handles are no longer usable. This prototype assumes one application worker; production must add durable queue + object artifact store, job worker isolation, per-module rate limits and recoverable execution before scaling to multiple workers. This feature does NOT itself generate Python from Pine or submit broker orders.

### Scope of automated validation

CI tests exercise FastAPI route generation, native plan_rebalance, vectorbt object handoff (native library mocked to isolate adapter logic), service contract routing (external HTTP mocked to isolate client mapping), cyclic/missing dependency detection, graph result persistence, auth and order execution blocks. They do **not** assert working production TradingView/Quant endpoints, trading broker credentials, real native training/model APIs, or backtest vs TradingView strategy tester parity.
