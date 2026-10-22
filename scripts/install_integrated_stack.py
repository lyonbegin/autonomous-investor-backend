from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CONSTRAINTS = ROOT / "requirements" / "integration-lock-linux-py313.txt"

UPSTREAMS = [
    ("TradingAgents", "https://github.com/TauricResearch/TradingAgents.git", "e8f5503e9b86d5c2710b0c76b1f686703968c9df", "."),
    ("FinRobot", "https://github.com/AI4Finance-Foundation/FinRobot.git", "2717499b8e30f242640af08c4ad9afd1113c2d45", "finrobot_desktop"),
    ("RD-Agent", "https://github.com/microsoft/RD-Agent.git", "484776c211e4fbbeef03e0ec00d6bbee7362a4f4", "."),
    ("Qlib", "https://github.com/microsoft/qlib.git", "54355232463878d2eebb91fe0ee5fa7fa1f5976c", "."),
    ("Chronos", "https://github.com/amazon-science/chronos-forecasting.git", "1224fafa91e1ecd6674f5204066b159e40b5e4a1", "."),
    ("Stable-Baselines3", "https://github.com/DLR-RM/stable-baselines3.git", "b2878f4b83e21f16a53c54a62def628e05fd2e96", "."),
    ("vectorbt", "https://github.com/polakowo/vectorbt.git", "v1.2.0", "."),
    ("FinRL-Trading", "https://github.com/AI4Finance-Foundation/FinRL-Trading.git", "4409abe925c904e570be78ebfb5e77ac3491dff8", "."),
    ("Riskfolio-Lib", "https://github.com/dcajasn/Riskfolio-Lib.git", "7b1b26ac9760974c12ecefe290a9d3bd37b66b7a", "."),
    ("PyPortfolioOpt", "https://github.com/PyPortfolio/PyPortfolioOpt.git", "a6638d2e06dae6f444fd022cfd4b3c528902a85b", "."),
]

NAUTILUS_REPO = "https://github.com/nautechsystems/nautilus_trader.git"
NAUTILUS_REF = "69aa8a283c8735cee4a536084078e3b19ac9a1be"
NAUTILUS_TESTED_WHEEL_VERSION = "2.0.0rc8.dev20261022+19732"


def run(*args: str, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.run(args, cwd=cwd, env=env, check=True)


def clone_exact(name: str, url: str, ref: str, base: Path) -> Path:
    dest = base / name
    if dest.exists():
        shutil.rmtree(dest)
    run("git", "clone", "--filter=blob:none", url, str(dest))
    run("git", "checkout", ref, cwd=dest)
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=dest, text=True).strip()
    if len(ref) == 40 and actual != ref:
        raise RuntimeError(f"{name}: expected {ref}, got {actual}")
    return dest


def patch_metadata(name: str, src: Path) -> None:
    if name == "RD-Agent":
        p = src / "requirements.txt"
        text = p.read_text()
        old = "pydantic-ai-slim[mcp,openai,prefect]==1.66.0"
        new = "pydantic-ai-slim[mcp,openai,prefect]==1.70.0"
        if old not in text:
            raise RuntimeError("RD-Agent dependency pin changed upstream")
        p.write_text(text.replace(old, new))
    elif name == "FinRL-Trading":
        p = src / "requirements.txt"
        text = p.read_text()
        old = "finnhub>=2.4.19"
        new = "finnhub-python>=2.4.19"
        if old not in text:
            raise RuntimeError("FinRL-Trading Finnhub dependency metadata changed upstream")
        p.write_text(text.replace(old, new))


def pip_install(*items: str, no_deps: bool = False) -> None:
    cmd = [sys.executable, "-m", "pip", "install", "-c", str(CONSTRAINTS)]
    if no_deps:
        cmd.append("--no-deps")
    cmd.extend(items)
    run(*cmd)


def install_nautilus_source(base: Path) -> None:
    src = clone_exact("NautilusTrader", NAUTILUS_REPO, NAUTILUS_REF, base)
    cargo = shutil.which("cargo")
    if not cargo:
        raise RuntimeError("Nautilus source build requires Rust 1.99.0/cargo")
    run(cargo, "--version")
    pip_install("maturin==1.15.0", "patchelf")
    env = os.environ.copy()
    env["PYO3_PYTHON"] = sys.executable
    env.setdefault("CARGO_BUILD_JOBS", "4")
    dist = src / "dist"
    dist.mkdir(exist_ok=True)
    run(
        sys.executable,
        "-m",
        "maturin",
        "build",
        "--locked",
        "--release",
        "--out",
        str(dist),
        cwd=src / "python",
        env=env,
    )
    wheels = sorted(dist.glob("nautilus_trader-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"Expected one Nautilus wheel, got {wheels}")
    pip_install(str(wheels[0]), no_deps=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", default=str(ROOT / ".upstream-src"))
    parser.add_argument("--skip-nautilus", action="store_true")
    args = parser.parse_args()

    if sys.version_info < (3, 13) or sys.version_info >= (3, 15):
        raise RuntimeError("Integrated stack requires Python >=3.13,<3.15")

    base = Path(args.source_dir).resolve()
    base.mkdir(parents=True, exist_ok=True)

    pip_install("-r", str(ROOT / "requirements" / "integration-base.txt"))

    installed: dict[str, Path] = {}
    for name, url, ref, install_path in UPSTREAMS:
        src = clone_exact(name, url, ref, base)
        patch_metadata(name, src)
        installed[name] = src / install_path

    # Install source projects under one shared constraint set.
    first_group = [
        installed["TradingAgents"],
        installed["FinRobot"],
        installed["RD-Agent"],
        installed["Qlib"],
        installed["Chronos"],
        installed["Stable-Baselines3"],
    ]
    pip_install(*(str(p) for p in first_group))
    pip_install("ray[rllib]==2.59.0")
    pip_install(str(installed["vectorbt"]))
    pip_install(str(installed["FinRL-Trading"]))
    pip_install(str(installed["Riskfolio-Lib"]))
    pip_install(str(installed["PyPortfolioOpt"]))

    if not args.skip_nautilus:
        install_nautilus_source(base)

    run(sys.executable, "-m", "pip", "check")
    print("INTEGRATED_STACK_INSTALL_OK")


if __name__ == "__main__":
    main()
