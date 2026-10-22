# Railway deployment image for the validated 12-engine Autonomous Investor stack.
# Heavy third-party engine installation is isolated in a cacheable layer so
# normal application-code changes do not rebuild NautilusTrader from source.
FROM python:3.13-bookworm AS builder

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:/root/.cargo/bin:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      ca-certificates \
      clang \
      curl \
      git \
      patchelf \
      pkg-config \
    && rm -rf /var/lib/apt/lists/*

# NautilusTrader validated source build requires Rust 1.99.0.
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
      | sh -s -- -y --profile minimal --default-toolchain 1.99.0 \
    && rustc --version \
    && cargo --version

WORKDIR /app
RUN python -m venv "$VIRTUAL_ENV"

# Copy only files that determine the integrated dependency layer first.
# Railway/BuildKit can reuse this expensive layer when only app code changes.
COPY requirements/ /app/requirements/
COPY scripts/install_integrated_stack.py /app/scripts/install_integrated_stack.py

RUN python -m pip install --upgrade pip setuptools wheel cython \
    && python scripts/install_integrated_stack.py --source-dir /tmp/autonomous-investor-upstreams \
    && python -m pip check

# Application and bridge/orchestration code changes happen after the heavy
# dependency layer, so they should not force another Nautilus Rust rebuild.
COPY . .

RUN python scripts/verify_integrated_stack.py \
    && rm -rf /tmp/autonomous-investor-upstreams /root/.cache/pip /root/.cargo/registry /root/.cargo/git

FROM python:3.13-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PORT=8000

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app /app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/health', timeout=5).read()" || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
