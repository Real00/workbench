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

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    STATIC_DIR=/app/backend/static \
    WORKBENCH_UPLOAD_DIR=/app/data/uploads

WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/ ./
COPY --from=frontend-build /build/frontend/dist ./static/
RUN uv sync --frozen --no-dev

EXPOSE 8080
CMD ["uv", "run", "--no-sync", "python", "-m", "workbench"]
