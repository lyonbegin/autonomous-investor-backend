# 이번 실행의 선별 증거

기록: 2026-10-27T21:41:26+09:00. 원본 로그에서 성공 marker만 선별했다. 실패와 미검증 범위는 TEST_AND_DEPLOYMENT_PLAN.md 참조.

## engine-verify-cpu.log

```text
NATIVE_DEMO_OK tradingagents TradingAgents Propagator.create_initial_state
NATIVE_DEMO_OK finrobot FinRobot validate_ticker + pipeline registry
NATIVE_DEMO_OK rdagent RD-Agent import_class + HypothesisFeedback
NATIVE_DEMO_OK qlib qlib.contrib.evaluate.risk_analysis
NATIVE_DEMO_OK chronos Chronos2Pipeline._get_prob_mass_per_quantile_level
NATIVE_DEMO_OK sb3 stable_baselines3.PPO.learn + predict
NATIVE_DEMO_OK rllib ray.rllib.algorithms.ppo.PPOConfig.validate
NATIVE_DEMO_OK vectorbt vectorbt Portfolio.from_signals
NATIVE_DEMO_OK finrl FinRL EqualWeightStrategy.generate_weights
NATIVE_DEMO_OK riskfolio riskfolio.Portfolio.assets_stats + optimization
NATIVE_DEMO_OK pyportfolioopt pypfopt.EfficientFrontier.min_volatility
NATIVE_DEMO_OK nautilus Nautilus RiskEngineConfig + ExecutionEngineConfig + BacktestEngineConfig + Strategy
FASTAPI_TWELVE_PROBES_OK
ALL_TWELVE_NATIVE_IMPORTS_OK
ALL_BRIDGES_OK
ALL_TWELVE_NATIVE_DEMOS_OK
```

## n8n-e2e-cpu.log

```text
REGISTERED_N8N_WEBHOOKS=13
REAL_N8N_WEBHOOK_TO_PYTHON_SCENARIOS_COMPLETED 10
REAL_N8N_F01_UPSTREAM_HTTP_AND_REGISTRY_PASS
REAL_N8N_F03_ATOMIC_PAPER_ASSIGNMENT_PASS
REAL_N8N_F05_LEASE_AUDIT_HALT_PASS
REAL_N8N_THREE_OPERATIONS_ALL_PASS
N8N_POSTGRES_SUCCESSFUL_OPERATIONS=3
N8N_POSTGRES_SUCCESSFUL_WORKER_EXECUTIONS=10
```

## chromium-ui-final.log

```text
  4 passed (18.6s)
```

## pytest-final.log

```text
117 passed, 2 warnings in 4.83s
```

## docker-service-smoke.log

```text
tradingview health + anonymous denial + authenticated read: PASS
quant health + anonymous denial + authenticated read: PASS
```


## 설치 스크립트 재실행

`/workspace/.onboarding/autonomous-investor-backend/install-integrated.sh` exit 0. 기존 설치 상태에서 12엔진 verifier, 당시 116 tests, 두 egress 검사, 4개 UI 빌드 성공. 새 task snapshot 복원 검증은 미실행.
