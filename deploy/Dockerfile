FROM node:24-alpine AS frontend-build

# 默认走 npmmirror：npmjs 在部分网络下不稳定，optional 原生依赖（rolldown/
# lightningcss/tauri）拉取失败会被 pnpm 静默跳过或拖到超时。可用 build-arg 覆盖。
ARG NPM_REGISTRY=https://registry.npmmirror.com
ENV NPM_CONFIG_REGISTRY=${NPM_REGISTRY}
RUN corepack enable
# 与本地一致：以仓库根为 workspace 安装（根 lockfile 是唯一事实来源）
WORKDIR /build
COPY pnpm-workspace.yaml pnpm-lock.yaml package.json ./
COPY frontend/package.json ./frontend/
# pnpm 不认 NPM_CONFIG_REGISTRY，必须写 .npmrc
RUN echo "registry=${NPM_REGISTRY}" > .npmrc
RUN pnpm install --frozen-lockfile
COPY frontend/ ./frontend/
RUN pnpm --filter frontend build

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS app-build

ARG WORKBENCH_GIT_SHA=unknown
ARG WORKBENCH_BUILT_AT=

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    WORKBENCH_UPLOAD_DIR=/app/data/uploads \
    WORKBENCH_KNOWLEDGE_DIR=/app/data/knowledge \
    WORKBENCH_RELEASE_ROOT=/app/data/releases \
    WORKBENCH_GIT_SHA=${WORKBENCH_GIT_SHA} \
    WORKBENCH_BUILT_AT=${WORKBENCH_BUILT_AT}

WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/ ./
COPY --from=frontend-build /build/frontend/dist ./static/
RUN uv sync --frozen --no-dev

# This supervisor remains in the image when application versions are replaced.
COPY backend/updater /opt/workbench/updater
COPY deploy/build-server-release.py /opt/workbench/build-server-release.py
ENV PYTHONPATH=/opt/workbench
RUN METADATA_ONLY=1 python /opt/workbench/build-server-release.py

FROM app-build AS bundle-build
RUN mkdir -p /bundle/wheels && \
    uv export --frozen --no-dev --no-emit-project --format requirements-txt \
      --output-file /bundle/requirements.txt && \
    uv tool run --python /usr/local/bin/python3 --from pip pip download \
      --only-binary=:all: --require-hashes -r /bundle/requirements.txt -d /bundle/wheels
RUN python /opt/workbench/build-server-release.py

FROM scratch AS bundle-output
COPY --from=bundle-build /output/ /

FROM app-build AS runtime
WORKDIR /opt/workbench
EXPOSE 8080
STOPSIGNAL SIGTERM
CMD ["python", "-m", "updater"]
