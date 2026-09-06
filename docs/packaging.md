# 打包流程

项目有两条独立的打包路径：

| 路径 | 产物 | 用途 |
| --- | --- | --- |
| Docker 镜像 | 单进程服务（API + 前端静态资源 + Mongo） | 服务器部署、打包验证 |
| Tauri 桌面端 | `Workbench.app` / `.dmg`（仅前端壳） | macOS 桌面客户端 |

## 打包前质量检查

```bash
cd backend && uv run ruff check . && uv run mypy app.py workbench api identity progress ai_settings shared && uv run pytest
cd frontend && pnpm typecheck && pnpm test && pnpm build
```

## Tauri 桌面端（macOS）

### 前置条件

- pnpm（仓库由根 `pnpm-workspace.yaml` 管理）
- Rust 工具链（`rustup`）
- Xcode Command Line Tools

### 打包命令

```bash
cd frontend
pnpm tauri build
```

`tauri.conf.json` 的 `beforeBuildCommand` 会自动先执行 `pnpm build`（含 `vue-tsc` 类型检查），前端产物打进包里，无需手动预构建。Rust 侧增量编译很快（无改动约 10 秒量级）；首次构建需编译全部依赖，耗时明显更长。

### 产物

```text
frontend/src-tauri/target/release/bundle/macos/Workbench.app
frontend/src-tauri/target/release/bundle/dmg/Workbench_<版本>_aarch64.dmg
```

`bundle.targets` 为 `all`，一次产出 .app 和 .dmg。改了前端代码后重跑同一条命令即可重新打包。

### 版本号

版本号在 `frontend/src-tauri/tauri.conf.json` 的 `version` 字段（当前 `0.1.0`），dmg 文件名随之变化。升级版本时改这里即可。

### 桌面端如何连后端

打包的桌面壳**只含前端，不含后端**。API 地址的确定顺序（见 `frontend/src/shared/api/client.ts`）：

1. 打包期默认值：构建时设置 `VITE_API_BASE_URL`（如 `VITE_API_BASE_URL=https://your-server pnpm tauri build`）；
2. 运行时覆盖：登录页可设置服务器地址，保存在 `localStorage`（`workbench_api_base`），优先于打包期默认值。

后端跨源放行无需配置：`tauri://localhost`、`http://tauri.localhost` 两个桌面默认来源在 `backend/shared/config.py` 中始终放行。若另用独立网页域名访问 API，才需要配置 `WORKBENCH_CORS_ORIGINS`。

### 桌面专属功能验证

打包完成后需人工验证一次（`pnpm tauri dev` 亦可）：

- 全局快捷键 **Cmd+Alt+J** 唤起主窗口并打开速记
- 托盘菜单：打开工作台 / 快速记录 / 退出

## Docker 镜像（服务端）

### 流程

```bash
cp .env.example .env    # 首次；务必修改管理员密码、JWT 密钥、加密密钥
docker compose up --build
```

访问 <http://localhost:8080>（端口由 `.env` 的 `WORKBENCH_PORT` 控制）。

只构建不启动用 `docker compose build app`。**改代码后必须重新 build**，这是打包验证/部署路径，不是日常开发方式（日常开发用 `./start_dev`）。

### 镜像结构（deploy/Dockerfile 多阶段）

1. `node:24-alpine` 阶段：以仓库根为 workspace `pnpm install --frozen-lockfile`，构建 `frontend/dist`。默认走 npmmirror（`ARG NPM_REGISTRY` 可覆盖），因 npmjs 在部分网络下拉取 optional 原生依赖不稳定。
2. `uv:python3.12-bookworm-slim` 运行时阶段：安装后端依赖，前端产物拷贝为 `backend/static`。

运行时由一个 aiohttp 进程同端口提供 API 和前端资源。

### 关键配置

| 环境变量 | 说明 |
| --- | --- |
| `WORKBENCH_JWT_SECRET` | 至少 32 字符，生产必改 |
| `WORKBENCH_ENCRYPTION_KEY` | Fernet 密钥，生成：`uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `WORKBENCH_ADMIN_USERNAME` / `WORKBENCH_ADMIN_PASSWORD` | 初始管理员，生产必改 |
| `WORKBENCH_MONGO_URI` | compose 内固定为 `mongodb://mongo:27017` |
| `WORKBENCH_UPLOAD_DIR` | 容器内固定 `/app/data/uploads` |
| `WORKBENCH_CORS_ORIGINS` | 独立网页域名访问 API 时配置（桌面端来源始终放行） |

数据持久化在三个 named volume：`mongo-data`（数据库）、`app-uploads`（上传文件）、`app-knowledge`（知识库 Markdown 文件），`docker compose down` 不会丢失，加 `-v` 才会。

## CI 自动打包（GitHub Actions）

流水线定义在 `.github/workflows/ci.yml`，三个任务串行（后两个依赖质量检查通过）：

| 任务 | 运行环境 | 内容 |
| --- | --- | --- |
| `check` | ubuntu + mongo:8 服务容器 | 后端 mypy/pytest、前端 typecheck/test/build |
| `docker` | ubuntu | 构建镜像并推送到 GHCR |
| `desktop` | macOS | `pnpm tauri build`，上传 dmg 构件 |

**触发与产物**

- push 到 `main`：质量检查 + 镜像推送 `ghcr.io/real00/workbench:latest` + dmg 存为 Actions 构件
- push tag `v*`（如 `v0.1.0`）：同上，镜像额外打 `vX.Y.Z` 版本 tag，dmg 自动创建 GitHub Release
- PR：只跑质量检查
- 手动触发（workflow_dispatch）：可填 `api_base_url`，作为 `VITE_API_BASE_URL` 烧入当次桌面包

**注意事项**

- 镜像默认私有；服务器拉取需 `docker login ghcr.io`，或在 GitHub 包设置中改为 public
- CI 构建的桌面包未做公证/签名，首次打开会被 Gatekeeper 拦截：右键 → 打开，或 `xattr -cr Workbench.app`
- 后端测试依赖 Mongo，CI 用 `mongo:8` 服务容器供在 `localhost:27017`，与 compose 一致；本机无 Mongo 时约 3 个用例会失败
- Docker 构建在 CI 中强制 `NPM_REGISTRY=https://registry.npmjs.org` 覆盖镜像内的 npmmirror 默认值（GitHub 网络访问 npmjs 更稳）
- `ruff check .` 暂未纳入 CI 闸门：仓库存量约 79 处违规（多为 `mcp/`、`tests/` 的 E501 超长行），清理完成后建议加回

### 迁移旧数据注意加密密钥

AI 设置的 API Key 用 `WORKBENCH_ENCRYPTION_KEY` 加密存储（未配置时由 `WORKBENCH_JWT_SECRET` 派生）。把别的环境导出的 Mongo 数据导入本环境时，该密钥必须与数据来源一致，否则读取 AI 设置会报 `cryptography.fernet.InvalidToken`。密钥不一致时最简单的处理：清空 `ai_settings` 集合后在系统设置里重新保存 API Key（用本环境密钥重新加密）。
