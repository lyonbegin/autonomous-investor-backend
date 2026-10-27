# Upstream integration policy

Each upstream project remains independent. We do not merge their source trees.

## Source revisions

- TradingAgents: e8f5503e9b86d5c2710b0c76b1f686703968c9df
- FinRobot V2 / finrobot_desktop: 2717499b8e30f242640af08c4ad9afd1113c2d45
- RD-Agent: 484776c211e4fbbeef03e0ec00d6bbee7362a4f4
- Qlib: 54355232463878d2eebb91fe0ee5fa7fa1f5976c
- Chronos: 1224fafa91e1ecd6674f5204066b159e40b5e4a1
- Stable-Baselines3: b2878f4b83e21f16a53c54a62def628e05fd2e96
- Ray/RLlib installed release: 2.59.0; inspected source revision: 69403c35688bb93f4cf195af4721744bd87a8489
- vectorbt: dd8eb3a3fe9ed918b1cdaf177455759ae4ac68cb
- FinRL-Trading: 4409abe925c904e570be78ebfb5e77ac3491dff8
- Riskfolio-Lib: 7b1b26ac9760974c12ecefe290a9d3bd37b66b7a
- PyPortfolioOpt: a6638d2e06dae6f444fd022cfd4b3c528902a85b
- NautilusTrader installed release: 2.0.0rc7; inspected develop revision: e88439b64dfe818e395401b8baef7a79b874ca68

## Compatibility patches

Only packaging metadata is patched.

1. RD-Agent pins pydantic-ai-slim 1.66.0 while FinRobot V2 accepts pydantic-ai >=1.70.
   The lab proved both codebases import successfully with pydantic-ai and pydantic-ai-slim 1.70.0.
2. FinRL-Trading declares a non-existent PyPI dependency named finnhub (finnhub>=2.4.19).
   Its source does not import that package at this revision. The packaging line is removed during install.

No upstream functional Python source is merged or edited.
