# Autonomous Investor Integration Lab Status

Python baseline: **3.13**

This file records only combinations that were actually exercised in clean GitHub-hosted Python 3.13 environments. Production `main` is not modified by these integration experiments.

## Validated cumulative stack

The following twelve engines coexist in one Python 3.13 environment and passed `pip check` plus native import/smoke execution.

1. TradingAgents — `e8f5503e9b86d5c2710b0c76b1f686703968c9df`
2. FinRobot V2 — `2717499b8e30f242640af08c4ad9afd1113c2d45`
3. RD-Agent — `484776c211e4fbbeef03e0ec00d6bbee7362a4f4`
4. Qlib — `54355232463878d2eebb91fe0ee5fa7fa1f5976c`
5. Chronos — `1224fafa91e1ecd6674f5204066b159e40b5e4a1`
6. Stable-Baselines3 — `b2878f4b83e21f16a53c54a62def628e05fd2e96`
7. Ray/RLlib — `ray-2.59.0`
8. vectorbt — `v1.2.0`
9. FinRL-Trading — `4409abe925c904e570be78ebfb5e77ac3491dff8`
10. Riskfolio-Lib — `7b1b26ac9760974c12ecefe290a9d3bd37b66b7a`
11. PyPortfolioOpt — `a6638d2e06dae6f444fd022cfd4b3c528902a85b`
12. NautilusTrader — `69aa8a283c8735cee4a536084078e3b19ac9a1be` / `2.0.0rc8.dev20261022+19732`

Cumulative eleven-engine evidence:
- Workflow run: `39770419578`
- Result: success
- `NINE_OK`: FinRL equal-weight StrategyResult executed.
- `TEN_OK`: Riskfolio 7.4.0 Portfolio optimization executed.
- `ELEVEN_OK`: PyPortfolioOpt 1.6.0 min-volatility optimization executed.
- `ALL_ELEVEN_IMPORTS_OK`: all eleven native surfaces imported together.
- Final `pip check`: passed.

Earlier execution evidence:
- SB3 cumulative run `39766266933`: PPO learn + predict succeeded.
- RLlib cumulative run `39767304140`: Ray 2.59.0 PPOConfig -> build -> train succeeded with training_iteration=1.
- vectorbt cumulative run `39768580275`: Portfolio.from_signals executed in the cumulative environment.

## Compatibility overlays

Upstream runtime source is not merged or rewritten. Only packaging metadata required for a shared environment is overlaid.

### RD-Agent
Upstream:
`pydantic-ai-slim[mcp,openai,prefect]==1.66.0`

Validated shared version:
`pydantic-ai-slim[mcp,openai,prefect]==1.70.0`

### FinRL-Trading
Upstream requirement name:
`finnhub>=2.4.19`

Validated package distribution name:
`finnhub-python>=2.4.19`

The FinRL strategy code remains unchanged.

## Shared compatibility constraints currently validated

- `pydantic-ai==1.70.0`
- `pydantic-ai-slim==1.70.0`
- `pandas==3.0.6`
- `numpy>=2.4.6,<3`
- `mlflow<3.13`
- `filelock>=3.16,<3.30`
- `packaging>=25,<26`
- `torch>=2.8,<3`
- `gymnasium==1.2.2`
- `ray==2.59.0`

Observed successful cumulative versions include NumPy 2.5.4 and Torch 2.14.1.

## Integration boundary rule

Upstream projects retain their native main/runtime flow. Our code only supplies thin bridge modules under `lab/bridges/`.

- TradingAgents -> `TradingAgentsGraph.propagate()`
- FinRobot V2 -> public `FinRobot` async SDK
- RD-Agent -> `QuantRDLoop`
- Qlib -> `qlib.init()` / native backtest
- Chronos -> native pipeline classes
- SB3 -> native algorithm lifecycle
- RLlib -> `AlgorithmConfig -> Algorithm`
- vectorbt -> `Portfolio` constructors
- FinRL-Trading -> `BaseStrategy.generate_weights() -> StrategyResult`
- Riskfolio -> `Portfolio.optimization()`
- PyPortfolioOpt -> `EfficientFrontier`
- NautilusTrader -> native PyO3 facade; pending final validation

## NautilusTrader

Validated source/wheel identity:
- Source commit: `69aa8a283c8735cee4a536084078e3b19ac9a1be`
- Validated wheel version: `2.0.0rc8.dev20261022+19732`
- Wheel SHA-256: `e77ef52d9c5593e1c420c60cc1bb4e7c1af13c7515729475064a679e46bbab50`
- Python: `>=3.13,<3.15`
- Rust/PyO3 facade validated.

Final twelve-engine evidence:
- Workflow run: `39773808554`
- Result: success
- Eleven-engine stack installed under shared constraints.
- Exact validated Nautilus wheel installed as the twelfth engine.
- All twelve native surfaces imported together.
- Thin bridge layer smoke tests passed.
- Final `pip check`: passed.

Reproducibility evidence:
- Workflow run: `39779527155`
- Result: success
- Repository installer recreated the eleven-engine environment.
- Exact validated Nautilus wheel was added.
- Repository integration verifier passed.
- Exact Python 3.13 Linux integration lock was honored.

## Cross-engine orchestration

Validated thin coordinators now connect the native engine boundaries without
reimplementing upstream internals:

1. Research: TradingAgents native graph -> ResearchBundle -> optional FinRobot native pipeline.
2. Autonomous R&D: ResearchBundle -> RD-Agent native ExperimentPlan.user_instruction -> QuantRDLoop.
3. Quant: Qlib Model.predict, Chronos predict_df, SB3 model.predict, RLlib RLModule.forward_inference.
4. Allocation: FinRL StrategyResult, Riskfolio Portfolio.optimization, PyPortfolioOpt EfficientFrontier -> TargetPortfolio.
5. Runtime: TargetPortfolio -> OrderIntent -> explicit symbol-to-Nautilus InstrumentId map -> native Nautilus order factory / submit_order.

Backend boundary unit tests after these coordinators: **19 passed**.
Nautilus venue identifiers are never guessed; execution accepts an explicit instrument mapping.
