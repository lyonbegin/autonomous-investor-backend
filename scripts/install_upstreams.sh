#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONSTRAINTS="${CONSTRAINTS:-$ROOT/requirements/integrated-constraints.txt}"
UPSTREAM_DIR="${UPSTREAM_DIR:-$ROOT/.upstreams}"

mkdir -p "$UPSTREAM_DIR"

python -m pip install -c "$CONSTRAINTS" -r "$ROOT/requirements.txt"
python -m pip install -c "$CONSTRAINTS" -r "$ROOT/requirements/upstream-sources.txt"

install_patched_repo() {
  local name="$1"
  local url="$2"
  local sha="$3"
  local patch="$4"
  local path="$UPSTREAM_DIR/$name"

  rm -rf "$path"
  git clone --filter=blob:none "$url" "$path"
  git -C "$path" checkout "$sha"
  git -C "$path" apply "$ROOT/$patch"
  python -m pip install -c "$CONSTRAINTS" "$path"
}

install_patched_repo \
  "RD-Agent" \
  "https://github.com/microsoft/RD-Agent.git" \
  "484776c211e4fbbeef03e0ec00d6bbee7362a4f4" \
  "patches/rdagent-pydantic-ai-1.70.patch"

install_patched_repo \
  "FinRL-Trading" \
  "https://github.com/AI4Finance-Foundation/FinRL-Trading.git" \
  "4409abe925c904e570be78ebfb5e77ac3491dff8" \
  "patches/finrl-remove-invalid-finnhub.patch"

python -m pip check
