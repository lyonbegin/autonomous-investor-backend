"""Bridge to Ray RLlib native AlgorithmConfig lifecycle."""

from __future__ import annotations

from typing import Any


class RLlibBridge:
    @staticmethod
    def ppo_config(
        env: Any,
        *,
        num_env_runners: int = 0,
        training: dict[str, Any] | None = None,
        **config_overrides: Any,
    ) -> Any:
        from ray.rllib.algorithms.ppo import PPOConfig

        config = PPOConfig().environment(env).env_runners(num_env_runners=num_env_runners)
        if training:
            config = config.training(**training)
        if config_overrides:
            config = config.update_from_dict(config_overrides)
        return config

    @staticmethod
    def build(config: Any) -> Any:
        return config.build()

    @staticmethod
    def train(algorithm: Any) -> dict[str, Any]:
        return algorithm.train()

    @staticmethod
    def forward_inference(algorithm: Any, batch: Any, *, module_id: str | None = None) -> Any:
        """Use RLlib 2.59's native RLModule inference path.

        Algorithm.compute_single_action() is deprecated in this upstream version.
        """
        module = algorithm.get_module(module_id) if module_id is not None else algorithm.get_module()
        return module.forward_inference(batch)
