# cc-catalog-svc image.
#
# syntax=docker/dockerfile:1.4
# Two layers worth of intent:
#
#   1. A small Python runtime (python:3.12-slim) running a single uvicorn
#      process. APScheduler runs in-process via the FastAPI lifespan so
#      there is no second container (no Celery, no Redis).
#   2. A pinned `crane` binary (Google's go-containerregistry CLI) for the
#      mirror engine. crane is a couple of MB, statically linked, and is
#      the de-facto tool for OCI image copy. We pin a specific version so
#      builds are reproducible.
#
# Air-gap git mirrors:
#   CI has outbound git access; the running container may not. When
#   BAKE_GIT_MIRRORS=true (default in CI), the git-bake stage clones bare
#   mirrors into /opt/cc-catalog/git — outside the /data volume so a PVC
#   mount does not hide baked repos. Deploy with git.data_dir=/opt/cc-catalog/git
#   and git.runtime_sync=false (see config-examples/config.airgap.yaml).
#
# Read-only-rootfs friendly: the only writable path the service needs is
# /data (SQLite DB + crane's auth cache). Mount a volume there in k8s.

ARG PYTHON_VERSION=3.12-slim
ARG CRANE_VERSION=v0.20.2
ARG BAKE_GIT_MIRRORS=true
ARG BAKE_CONFIG=config-examples/config.bake.yaml

# -----------------------------------------------------------------------------
# Stage 1: fetch crane. Doing this in a tiny scratch-ish stage keeps the
# final image free of curl / ca-certificates churn.
# -----------------------------------------------------------------------------
FROM debian:bookworm-slim AS crane
ARG CRANE_VERSION
ARG TARGETARCH
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*
RUN set -eux; \
    case "${TARGETARCH:-amd64}" in \
        amd64) crane_arch=x86_64 ;; \
        arm64) crane_arch=arm64 ;; \
        *)     echo "unsupported arch ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    curl -fsSL -o /tmp/crane.tgz \
        "https://github.com/google/go-containerregistry/releases/download/${CRANE_VERSION}/go-containerregistry_Linux_${crane_arch}.tar.gz"; \
    tar -xzf /tmp/crane.tgz -C /usr/local/bin crane; \
    rm /tmp/crane.tgz; \
    /usr/local/bin/crane version

# -----------------------------------------------------------------------------
# Stage 2: bake git mirrors (CI only — needs outbound network).
# -----------------------------------------------------------------------------
FROM python:${PYTHON_VERSION} AS git-bake
ARG BAKE_GIT_MIRRORS
ARG BAKE_CONFIG
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY pyproject.toml README.md ./
COPY app ./app
COPY scripts ./scripts
COPY config-examples/config.bake.yaml ./config-examples/config.bake.yaml
RUN pip install --no-cache-dir .
RUN mkdir -p /opt/cc-catalog/git
RUN --mount=type=secret,id=github_token \
    if [ "${BAKE_GIT_MIRRORS}" = "true" ]; then \
      export GITHUB_TOKEN="$(cat /run/secrets/github_token 2>/dev/null || true)"; \
      python scripts/bake_git_mirrors.py \
        --config "${BAKE_CONFIG}" \
        --dest /opt/cc-catalog/git; \
    else \
      echo "BAKE_GIT_MIRRORS=false; skipping git mirror bake"; \
    fi

# -----------------------------------------------------------------------------
# Stage 3: runtime image.
# -----------------------------------------------------------------------------
FROM python:${PYTHON_VERSION} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Non-root user. UID 1000 matches the existing cc-registry-v2 manifests so
# operator instinct carries over.
RUN groupadd --system --gid 1000 catalog \
 && useradd --system --uid 1000 --gid 1000 --home /home/catalog --create-home catalog \
 && mkdir -p /app /data /data/git /opt/cc-catalog/git \
 && chown -R catalog:catalog /app /data /opt/cc-catalog

COPY --from=crane /usr/local/bin/crane /usr/local/bin/crane
COPY --from=git-bake /opt/cc-catalog/git /opt/cc-catalog/git

# git binary kept for optional runtime_sync in connected environments.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/* \
 && chown -R catalog:catalog /opt/cc-catalog/git

WORKDIR /app
# README.md is referenced from pyproject.toml's `readme = "README.md"`, so
# setuptools needs it at install time. Keep it copied alongside pyproject.
COPY pyproject.toml README.md ./
COPY app ./app

# Install in editable-ish mode. We don't ship optional[postgres] in the
# default image to keep it slim; supply DATABASE_URL pointing at sqlite by
# default. To run against Postgres in k8s, build with `--build-arg
# EXTRA_DEPS=postgres` or pip-install psycopg2-binary on top.
ARG EXTRA_DEPS=""
RUN pip install --upgrade pip \
 && if [ -n "$EXTRA_DEPS" ]; then \
        pip install ".[${EXTRA_DEPS}]"; \
    else \
        pip install .; \
    fi

USER catalog
EXPOSE 8080
VOLUME ["/data"]

# Healthcheck targets /readyz (DB-touching) by default. /healthz is the
# lighter-weight liveness probe used by k8s.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/readyz', timeout=3).status==200 else 1)"

ENV CC_CATALOG_CONFIG_FILE=/app/config.yaml \
    CC_CATALOG_DB_URL=sqlite:////data/catalog.db

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
