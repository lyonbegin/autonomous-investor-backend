# 12개 엔진 인벤토리

검증 시각: 2026-10-27T21:37:36+09:00. 환경: Codex Linux x86_64 / Python 3.13.16 / CPU torch 2.14.1+cpu.

출처: app/core/integrations.py의 SPECS, app/integrations/ 12개, lab/bridges/ 12개, lab/upstreams.toml, 기존 install/verify 스크립트. `validated` 필드는 과거 코드의 메타데이터이고 이번 테스트와 구분한다.

| 키 | 정확한 엔진 이름 | 원본 | pinned_ref | Python module | 설치 | import/심볼 | 기존 native demo |
|---|---|---|---|---|---|---|---|
| `tradingagents` | TradingAgents | `TauricResearch/TradingAgents` | `e8f5503e9b86d5c2710b0c76b1f686703968c9df` | `tradingagents.graph.trading_graph` | 성공 | 성공 | 성공 |
| `finrobot` | FinRobot V2 | `AI4Finance-Foundation/FinRobot` | `2717499b8e30f242640af08c4ad9afd1113c2d45` | `finrobot` | 성공 | 성공 | 성공 |
| `rdagent` | RD-Agent(Q) | `microsoft/RD-Agent` | `484776c211e4fbbeef03e0ec00d6bbee7362a4f4` | `rdagent.app.qlib_rd_loop.quant` | 성공 | 성공 | 성공 |
| `qlib` | Qlib | `microsoft/qlib` | `54355232463878d2eebb91fe0ee5fa7fa1f5976c` | `qlib.model.base` | 성공 | 성공 | 성공 |
| `chronos` | Chronos | `amazon-science/chronos-forecasting` | `1224fafa91e1ecd6674f5204066b159e40b5e4a1` | `chronos` | 성공 | 성공 | 성공 |
| `sb3` | Stable-Baselines3 | `DLR-RM/stable-baselines3` | `b2878f4b83e21f16a53c54a62def628e05fd2e96` | `stable_baselines3` | 성공 | 성공 | 성공 |
| `rllib` | Ray RLlib | `ray-project/ray` | `ray-2.59.0` | `ray.rllib.algorithms.ppo` | 성공 | 성공 | 성공 |
| `vectorbt` | vectorbt | `polakowo/vectorbt` | `v1.2.0` | `vectorbt.portfolio.base` | 성공 | 성공 | 성공 |
| `finrl` | FinRL-Trading | `AI4Finance-Foundation/FinRL-Trading` | `4409abe925c904e570be78ebfb5e77ac3491dff8` | `strategies.base_strategy` | 성공 | 성공 | 성공 |
| `riskfolio` | Riskfolio-Lib | `dcajasn/Riskfolio-Lib` | `7b1b26ac9760974c12ecefe290a9d3bd37b66b7a` | `riskfolio` | 성공 | 성공 | 성공 |
| `pyportfolioopt` | PyPortfolioOpt | `PyPortfolio/PyPortfolioOpt` | `a6638d2e06dae6f444fd022cfd4b3c528902a85b` | `pypfopt` | 성공 | 성공 | 성공 |
| `nautilus` | NautilusTrader | `nautechsystems/nautilus_trader` | `69aa8a283c8735cee4a536084078e3b19ac9a1be` | `nautilus_trader.trading` | 성공 | 성공 | 성공 |

## 실제 실행한 검증

`scripts/verify_integrated_stack.py`가 `FASTAPI_TWELVE_PROBES_OK`, `ALL_TWELVE_NATIVE_IMPORTS_OK`, `ALL_BRIDGES_OK`, `ALL_TWELVE_NATIVE_DEMOS_OK`로 종료했다. CPU torch 교체 후에도 재검증했다. 로그: `/workspace/integration-audit/engine-verify-cpu.log`.

| 엔진 | 실제 demo 호출 | 검증 한계 |
|---|---|---|
| `tradingagents` | `TradingAgents Propagator.create_initial_state` | 소규모 synthetic / 구성·계산 smoke; 운영 데이터·실거래 아님 |
| `finrobot` | `FinRobot validate_ticker + pipeline registry` | 소규모 synthetic / 구성·계산 smoke; 운영 데이터·실거래 아님 |
| `rdagent` | `RD-Agent import_class + HypothesisFeedback` | 소규모 synthetic / 구성·계산 smoke; 운영 데이터·실거래 아님 |
| `qlib` | `qlib.contrib.evaluate.risk_analysis` | 소규모 synthetic / 구성·계산 smoke; 운영 데이터·실거래 아님 |
| `chronos` | `Chronos2Pipeline._get_prob_mass_per_quantile_level` | 소규모 synthetic / 구성·계산 smoke; 운영 데이터·실거래 아님 |
| `sb3` | `stable_baselines3.PPO.learn + predict` | 소규모 synthetic / 구성·계산 smoke; 운영 데이터·실거래 아님 |
| `rllib` | `ray.rllib.algorithms.ppo.PPOConfig.validate` | 소규모 synthetic / 구성·계산 smoke; 운영 데이터·실거래 아님 |
| `vectorbt` | `vectorbt Portfolio.from_signals` | 소규모 synthetic / 구성·계산 smoke; 운영 데이터·실거래 아님 |
| `finrl` | `FinRL EqualWeightStrategy.generate_weights` | 소규모 synthetic / 구성·계산 smoke; 운영 데이터·실거래 아님 |
| `riskfolio` | `riskfolio.Portfolio.assets_stats + optimization` | 소규모 synthetic / 구성·계산 smoke; 운영 데이터·실거래 아님 |
| `pyportfolioopt` | `pypfopt.EfficientFrontier.min_volatility` | 소규모 synthetic / 구성·계산 smoke; 운영 데이터·실거래 아님 |
| `nautilus` | `Nautilus RiskEngineConfig + ExecutionEngineConfig + BacktestEngineConfig + Strategy` | 소규모 synthetic / 구성·계산 smoke; 운영 데이터·실거래 아님 |

## 설치·실행 경로와 의존성

- 가상환경: `/workspace/.onboarding/autonomous-investor-backend/py313`. Python runtime은 `/workspace/.onboarding/python/`에 있다.
- 원본 10개 repo는 `/workspace/integration-audit/upstream-src/`에서 정확한 refs로 checkout했다. Ray는 `ray[rllib]==2.59.0`, Nautilus는 정확한 저장소 release wheel을 사용했다.
- Nautilus SHA-256: `e77ef52d9c5593e1c420c60cc1bb4e7c1af13c7515729475064a679e46bbab50`. 서명/TLS/체크섬 검증을 끄지 않았다.
- RD-Agent의 기존 pydantic-ai 1.70 오버레이 및 FinRL의 finnhub-python 메타데이터 보정은 기존 installer 기준이다.
- CPU 전용 개발환경으로 동일 torch release의 공식 `2.14.1+cpu` wheel을 사용한다. 더 이상 필요하지 않은 GPU 전용 패키지 18개만 의존성 역참조 검사 후 제거했다. xgboost가 요구하는 nvidia-nccl-cu13은 유지했다. pip check 통과.
- RD-Agent: ARTIFACT_SIGNING_KEY_PATH, PICKLE_CACHE_FOLDER_PATH_STR, WORKSPACE_PATH, LOG_TRACE_PATH를 workspace의 전용 개발 디렉터리로 지정한다. 서명 기능을 해제하거나 키 값을 문서에 저장하지 않는다.
- 연구: TradingAgents/FinRobot/RD-Agent, 예측: Chronos, ML: Qlib, RL: SB3/RLlib, screening: vectorbt, 전략: FinRL, 배분: Riskfolio/PyPortfolioOpt, 단일 실행 계약: Nautilus.
- API: `/api/v1/integrations`의 probe, `/api/v1/demo` 계열 native demo, 인증된 `/api/v1/alpha/modules/...` 함수 실행과 기존 DAG를 유지한다.
- 전체 학습/다운로드 모델/LLM 추론/실시장 데이터/실거래 검증은 하지 않았다. 엔진별 독립 subprocess 기동·정지/CPU·메모리 제한은 미완료이며 전체 시스템 완료로 보고하지 않는다.
