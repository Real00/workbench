# 打包流程

项目有两条独立的打包路径：

| 路径 | 产物 | 用途 |
| --- | --- | --- |
| Docker 镜像 | 单进程服务（API + 前端静态资源 + Mongo） | 服务器部署、打包验证 |
| Tauri 桌面端 | `Workbench.app` / `.dmg`（仅前端壳） | macOS 桌面客户端 |

## 打包前质量检查

```bash
cd backend && uv run ruff check . && uv run mypy app.py workbench api identity progress knowledge subscription ai_settings system shared pulse && uv run pytest
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

### 应用图标

Dock / `.app` / 托盘图标来自 `frontend/src-tauri/icons/`（含 `icon.icns`），**不会**跟着 `frontend/public/work-mark.png` 自动更新。换品牌后：

1. 准备方形源图（建议 1024×1024）写入 `frontend/src-tauri/app-icon.png`
2. 在 `frontend` 执行：`pnpm exec tauri icon src-tauri/app-icon.png`
3. 再跑 `pnpm tauri build`

若重装后 Dock 仍显示旧图，可删掉旧 `.app` 后重装，或注销 / 重启以刷新图标缓存。

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
| `WORKBENCH_UPDATE_AGENT_TOKEN` | 与宿主机 Update Agent 共享的 HMAC 密钥；未配置则设置页不能一键更新 |
| `WORKBENCH_UPDATE_CONTROL_DIR` | 容器内控制目录（GHCR compose 示例为 `/app/data/update-control`） |
| `WORKBENCH_UPDATE_GITHUB_REPO` / `WORKBENCH_UPDATE_GITHUB_REF` | 检查更新时对比的仓库与分支（默认 `real00/workbench` @ `main`） |
| `WORKBENCH_UPDATE_GITHUB_TOKEN` | 私有仓调用 GitHub API 检查更新时需要 |

数据持久化在三个 named volume：`mongo-data`（数据库）、`app-uploads`（上传文件）、`app-knowledge`（知识库 Markdown 文件），`docker compose down` 不会丢失，加 `-v` 才会。

镜像构建时写入 `WORKBENCH_GIT_SHA` / `WORKBENCH_BUILT_AT`（CI 自动传入），设置页「版本更新」据此展示当前版本。

### 生产：从 GHCR 拉取

仓库根目录的 [`compose.ghcr.yaml`](../compose.ghcr.yaml) 使用预构建镜像，不再在服务器 `build`。

**推荐：一键脚本**（自动沿用已有 Compose 项目名与 `mongo-data` 卷，**绝不** `down -v` / `volume rm`）：

```bash
# 方式 A：完整仓库
sudo ./deploy/install-server.sh

# 方式 B：精简目录（例如 /data/workbench），同目录放入：
#   compose.ghcr.yaml
#   install-server.sh
#   deploy/update-agent/agent.py
#   .env（已有生产配置）
cd /data/workbench
sudo ./install-server.sh

# 私有 GHCR 先 docker login ghcr.io
# 项目名必须使「项目名_mongo-data」等于现有卷；一般脚本会自动探测
sudo COMPOSE_PROJECT_NAME=workbench ./install-server.sh
```

手动步骤：

```bash
cp .env.example .env   # 填入 JWT / 管理员密码 / ENCRYPTION_KEY / UPDATE_AGENT_TOKEN 等
mkdir -p update-control
docker login ghcr.io   # 私有包需要
docker compose -f compose.ghcr.yaml up -d
```

日常发版后在服务器执行：

```bash
docker compose -f compose.ghcr.yaml pull app
docker compose -f compose.ghcr.yaml up -d app
```

或使用下方 Update Agent，在系统设置里点「更新到最新」。

### 一键更新（宿主机 Update Agent）

**不要**把 `/var/run/docker.sock` 挂进工作台容器。应用只向共享目录写 `request.json`；宿主机 Agent 校验 HMAC 后执行固定的 `docker compose pull/up`。

1. 服务器部署目录放好 `compose.ghcr.yaml`、`.env`，并创建 `update-control/`（已在 compose 中 bind mount）。
2. 复制 Agent 与 systemd 单元（路径按实际修改）：

```bash
# 假设部署目录为 /opt/workbench，内含 compose.ghcr.yaml 与 deploy/update-agent/
sudo cp /opt/workbench/deploy/update-agent/update-agent.env.example /opt/workbench/update-agent.env
# 编辑 update-agent.env：UPDATE_AGENT_TOKEN 与 .env 里 WORKBENCH_UPDATE_AGENT_TOKEN 一致
sudo cp /opt/workbench/deploy/update-agent/workbench-update-agent.service /etc/systemd/system/
# 按需编辑单元中的 WorkingDirectory / Environment 路径
sudo systemctl daemon-reload
sudo systemctl enable --now workbench-update-agent
```

3. 重启 app 容器使 `WORKBENCH_UPDATE_*` 生效后，打开系统设置 →「版本更新」：检查更新 / 更新到最新。

Agent 只接受协议内的请求文件，不执行客户端传入的任意命令。更新期间 API 会短暂不可用，页面会轮询直到新 `git_sha` 出现或超时。

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

重建管理员（清空 `users`）后，导入数据里绑定了旧用户 ID 的操作者成员（如「管理员」）无法被 `ensure_operator` 认领，会因 `members.name` 唯一索引冲突导致启动报 `DuplicateKeyError`。需手动重绑：

```bash
docker compose exec mongo mongosh workbench --eval '
db.members.updateOne({ name: "管理员" }, { $set: { user_id: db.users.findOne().id, active: true } })'
```
