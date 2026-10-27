"""Bridge to Stable-Baselines3 native algorithms."""

from __future__ import annotations

from typing import Any


class StableBaselinesBridge:
    @staticmethod
    def build(algorithm: str, policy: str, env: Any, **kwargs: Any) -> Any:
        from stable_baselines3 import A2C, DQN, PPO, SAC, TD3

        algorithms = {"A2C": A2C, "DQN": DQN, "PPO": PPO, "SAC": SAC, "TD3": TD3}
        try:
            cls = algorithms[algorithm.upper()]
        except KeyError as exc:
            raise ValueError(f"Unsupported SB3 algorithm: {algorithm}") from exc
        return cls(policy, env, **kwargs)

    @staticmethod
    def learn(model: Any, total_timesteps: int, **kwargs: Any) -> Any:
        return model.learn(total_timesteps=total_timesteps, **kwargs)

    @staticmethod
    def predict(model: Any, observation: Any, *, deterministic: bool = True) -> Any:
        """Call the native SB3 model.predict() inference boundary."""
        return model.predict(observation, deterministic=deterministic)
