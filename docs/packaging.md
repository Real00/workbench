# 打包流程

项目有三条独立的打包路径：

| 路径 | 产物 | 用途 |
| --- | --- | --- |
| Docker 镜像 | 应用服务（API + 前端静态资源）及独立 Mongo | 服务器部署、打包验证 |
| Tauri 桌面端 | `Workbench.app` / `.dmg`（仅前端壳） | macOS 桌面客户端 |
| Tauri Android | debug / release APK（仅前端壳） | 安卓客户端 |

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

1. 运行时覆盖：登录页保存的 `localStorage`（`workbench_api_base`）；
2. 打包期默认值：构建时 `VITE_API_BASE_URL`（CI 默认烧入 `https://workbench.reelab.cc`）；
3. 代码兜底：Tauri 壳未配置时用 `https://workbench.reelab.cc`。

后端跨源放行无需配置：`tauri://localhost`、`http://tauri.localhost`、`https://tauri.localhost` 在 `backend/shared/config.py` 中始终放行（桌面与 Android 共用）。若另用独立网页域名访问 API，才需要配置 `WORKBENCH_CORS_ORIGINS`。

### 桌面专属功能验证

打包完成后需人工验证一次（`pnpm tauri dev` 亦可）：

- 全局快捷键 **Cmd+Alt+J** 唤起主窗口并打开速记
- 点窗口关闭应隐藏到托盘（不退出）；托盘左键或 Dock 再点可重新打开
- 托盘菜单：打开工作台 / 快速记录 / 退出（或 Cmd+Q）真正退出

Android 壳**没有**托盘、全局快捷键、DMG 客户端更新；登录页仍可配置服务器地址。

## Tauri Android

### 前置条件

- pnpm、Rust 工具链
- **JDK 17**（Gradle 当前不支持 JDK 26；可用 sdkman `17.0.x` 或 Temurin 17，并设置 `JAVA_HOME`）
- Android SDK（`ANDROID_HOME`，常见路径 `~/Library/Android/sdk`）
- Android NDK side-by-side（`NDK_HOME=$ANDROID_HOME/ndk/<version>`，推荐 27.x）
- Rust Android targets：

```bash
rustup target add aarch64-linux-android armv7-linux-androideabi i686-linux-android x86_64-linux-android
```

工程目录：`frontend/src-tauri/gen/android/`（已入库；若本地缺失可在 `frontend` 执行 `pnpm exec tauri android init`）。

### 本机命令

```bash
cd frontend
# 模拟器 / 真机调试（包名 com.workbench.desktop.debug，与 release 并存）
pnpm android:dev
# release APK（可覆盖安装；体积远小于 debug）
pnpm android:build
# 仅本地调试包
pnpm android:build:debug
```

产物大致位于：

```text
frontend/src-tauri/gen/android/app/build/outputs/apk/.../release/*.apk
```

CI 默认打 **release** APK（`Workbench-android-aarch64.apk`），包名 `com.workbench.desktop`，用仓库内 `upload.keystore` 签名；`versionCode = 1000 + github.run_number`，保证覆盖安装。

若本机曾安装过 debug 包（`com.workbench.desktop.debug`），与 release **不是同一应用**，需先卸载 debug 再装 release。

侧载签名密钥：`frontend/src-tauri/gen/android/app/upload.keystore`（密码 / alias 默认均为 `workbench`，可用环境变量 `ANDROID_KEYSTORE_PASSWORD` 等覆盖）。仅供内部分发，不是 Play 上架密钥。

启动器图标来自 `frontend/src-tauri/app-icon.png`（`pnpm exec tauri icon src-tauri/app-icon.png` 会同步到 `icons/` 与 `gen/android`）。

### 如何连后端

与桌面相同：默认已指向 `https://workbench.reelab.cc`；登录页仍可改。

| 环境 | 推荐地址 |
| --- | --- |
| 默认（云端） | `https://workbench.reelab.cc` |
| Android 模拟器访问宿主机 | `http://10.0.2.2:8080` |
| 真机访问局域网后端 | `http://<电脑局域网 IP>:8080` |

debug / release 均已允许 cleartext HTTP（`usesCleartextTraffic`），以便连本机与局域网。Android WebView Origin 为 `http://tauri.localhost`（开启 https scheme 则为 `https://tauri.localhost`），后端默认已放行。

包名：`com.workbench.desktop`（debug 为 `com.workbench.desktop.debug`），与桌面 identifier 一致。

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

运行时由独立启动器管理 aiohttp 子进程，API 和前端资源仍使用同一端口。启动器只依赖 Python 标准库，保存在镜像 `/opt/workbench/updater` 中，不随应用包更新。

### 关键配置

| 环境变量 | 说明 |
| --- | --- |
| `WORKBENCH_JWT_SECRET` | 至少 32 字符，生产必改 |
| `WORKBENCH_ENCRYPTION_KEY` | Fernet 密钥，生成：`uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `WORKBENCH_ADMIN_USERNAME` / `WORKBENCH_ADMIN_PASSWORD` | 初始管理员，生产必改 |
| `WORKBENCH_MONGO_URI` | compose 内固定为 `mongodb://mongo:27017` |
| `WORKBENCH_UPLOAD_DIR` | 容器内固定 `/app/data/uploads` |
| `WORKBENCH_CORS_ORIGINS` | 独立网页域名访问 API 时配置（桌面端来源始终放行） |
| `WORKBENCH_RELEASE_ROOT` | 版本持久化目录，镜像默认 `/app/data/releases`，Compose 挂载 `app-releases` 卷 |
| `WORKBENCH_UPDATE_GITHUB_REPO` / `WORKBENCH_UPDATE_RELEASE_TAG` | 更新仓库与发布频道（默认 `real00/workbench` / `server-latest`） |
| `WORKBENCH_UPDATE_GITHUB_TOKEN` | 私有仓调用 GitHub API 检查更新时需要 |

数据持久化在四个 named volume：`mongo-data`（数据库）、`app-uploads`（上传文件）、`app-knowledge`（知识库 Markdown 文件）、`app-releases`（已安装应用版本与更新状态），`docker compose down` 不会丢失，加 `-v` 才会。

镜像和更新包均包含 `release.json`。启动器读取实际运行版本的元信息，并传入 `WORKBENCH_GIT_SHA` / `WORKBENCH_BUILT_AT`；设置页展示应用版本，可能不同于基础镜像版本。

### 生产：从 GHCR 拉取

仓库根目录的 [`compose.ghcr.yaml`](../compose.ghcr.yaml) 使用预构建镜像，不再在服务器 `build`。

**推荐：一键脚本**（自动沿用已有 Compose 项目名与 `mongo-data` 卷，**绝不** `down -v` / `volume rm`）：

```bash
# 方式 A：完整仓库
sudo ./deploy/install-server.sh

# 方式 B：精简目录（例如 /data/workbench），同目录放入：
#   compose.ghcr.yaml
#   install-server.sh
#   .env（已有生产配置）
cd /data/workbench
sudo ./install-server.sh

# 私有 GHCR 先 docker login ghcr.io
# 项目名必须使「项目名_mongo-data」等于现有卷；一般脚本会自动探测
sudo COMPOSE_PROJECT_NAME=workbench ./install-server.sh
```

手动步骤：

```bash
cp .env.example .env   # 填入 JWT / 管理员密码 / ENCRYPTION_KEY 等
docker login ghcr.io   # 私有包需要
docker compose -f compose.ghcr.yaml up -d
```

日常更新：打开系统设置 →「版本更新」→「更新到最新」。无需安装宿主机服务或挂载 Docker socket。

### 容器内更新

1. CI 在 `main` 通过检查后，构建 Linux amd64 / arm64 的离线更新包：后端、前端静态资源、锁定的 requirements 和对应平台的 wheels。
2. 完整包先上传到不可变的 `server-<完整 SHA>` Release，再刷新 `server-latest` 中的架构清单。检查更新只查询已发布的包，不对比分支上尚未构建的提交。
3. 更新器校验 SHA-256、大小、运行环境版本，拒绝路径穿越和链接，然后在独立版本目录创建虚拟环境并离线安装依赖。准备期间旧服务持续运行。
4. 准备完成后，启动器向旧应用发送 SIGTERM（最多等待 30 秒），启动新版并检查 `/health` 的实例标识和版本。所有模块启动完成后连续三次检查通过才提交版本切换。
5. 新版启动失败或 90 秒未就绪，恢复原版本并在页面显示失败原因。重启或断电打断未提交的切换，也会恢复原版本。只保留当前版和上一版，失败包会清理。
6. 网页确认完成后自动刷新。页面关闭不会取消更新，重新进入设置会恢复进行中的状态。Tauri 客户端仍需单独更新。

程序回退不撤销数据库或文件的数据变更，新增迁移必须兼容上一应用版本。此方案面向单实例；同一版本卷不能由多个启动器共同使用。

**持久化与基础镜像**

- 重启或用同一镜像重建容器，继续运行版本卷中已提交的版本。
- 部署不同 SHA 的基础镜像时，启动器改用该镜像自带版本，随后可继续页面更新。
- Python、系统库或启动协议不兼容时，更新包会要求升级基础镜像。修改运行环境时必须同时递增 `backend/updater/protocol.py` 的 `RUNTIME`。
- 升级基础镜像使用 `docker compose -f compose.ghcr.yaml pull app` 和 `docker compose -f compose.ghcr.yaml up -d app`；保留所有数据卷。
- 私有仓需在 `.env` 配置 `WORKBENCH_UPDATE_GITHUB_TOKEN`（contents:read），并重建 app 使配置生效。`docker login` 仅授权镜像仓库。

**从旧部署迁移一次**

使用新版 Compose（增加 `app-releases` 卷）和镜像，沿用原 Compose 项目名及 `.env`，运行 `deploy/install-server.sh`。脚本会停用旧 `workbench-update-agent` systemd 服务，并移除旧的更新 token / 控制目录配置；不删除业务数据。旧部署目录内的 `update-control/`、`update-agent.env`、`deploy/update-agent/` 已不再使用，可在迁移后自行删除。

**本地打包验证**

```bash
docker build -f deploy/Dockerfile --target runtime -t workbench:test .
docker buildx build -f deploy/Dockerfile --target bundle-output \
  --build-arg WORKBENCH_GIT_SHA=<40位提交SHA> \
  --output type=local,dest=/tmp/workbench-server-bundle .
```

更新运行时的测试在 `backend/tests/test_updater.py`，覆盖重复请求、下载校验、恶意归档、依赖失败、真实子进程启动/回退、中断恢复和信号转发。

### 桌面端客户端更新（DMG）

桌面端把前端打进 `.app`，**服务器镜像更新不会刷新本机 UI**。要换新界面必须装新的 DMG。

流程：

1. CI 在每次 `push` 到 `main` 时构建桌面端，并把版本写成 `tauri.conf.json` 的 `0.x.y+<短SHA>`。
2. 上传固定文件名 `Workbench-macos-aarch64.dmg` 到 GitHub 预发布 **`desktop-latest`**（覆盖原资产）。
3. 桌面端打开系统设置 →「版本更新」→ **客户端更新**：检查更新 / 下载并打开 DMG，再拖进「应用程序」后重启。

私有仓库检查与下载走服务端 `WORKBENCH_UPDATE_GITHUB_TOKEN`（需 `contents:read`），客户端经 `/api/v1/system/desktop/dmg` 代理拉取，无需在本机配置 GitHub token。

未做 Apple 公证时，首次打开仍可能被 Gatekeeper 拦截：右键 → 打开。

当前不做静默覆盖安装（需 Tauri updater 签名密钥与 Apple Developer 公证）；有证书后可再加。

## CI 自动打包（GitHub Actions）

流水线定义在 `.github/workflows/ci.yml`，质量检查通过后并行构建产物：

| 任务 | 运行环境 | 内容 |
| --- | --- | --- |
| `check` | ubuntu + mongo:8 服务容器 | 后端 mypy/pytest、前端 typecheck/test/build |
| `docker` | ubuntu | 构建镜像并推送到 GHCR |
| `server-bundle` / `server-publish` | ubuntu + Buildx | 构建双架构离线包，发布不可变版本并刷新 `server-latest` |
| `desktop` | macOS | `pnpm tauri build`，上传 dmg；main 刷新 `desktop-latest` |
| `android` | ubuntu | `pnpm tauri android build --apk`（release），上传 APK；main 刷新 `android-latest` |

**触发与产物**

- push 到 `main`：质量检查 + 镜像推送 `ghcr.io/real00/workbench:latest` + dmg / debug APK 存为 Actions 构件，并更新预发布 `desktop-latest` / `android-latest`
- push tag `v*`（如 `v0.1.0`）：同上，镜像额外打 `vX.Y.Z` 版本 tag，dmg 与 APK 写入该正式 Release
- PR：只跑质量检查
- 手动触发（workflow_dispatch）：可填 `api_base_url`，作为 `VITE_API_BASE_URL` 烧入当次桌面 / Android 包

**注意事项**

- 镜像默认私有；服务器拉取需 `docker login ghcr.io`，或在 GitHub 包设置中改为 public
- CI 构建的桌面包未做公证/签名，首次打开会被 Gatekeeper 拦截：右键 → 打开，或 `xattr -cr Workbench.app`
- Android CI 产物为 **release APK**（`com.workbench.desktop`，已签名）；debug 仅本机 `pnpm android:build:debug`。曾装 debug 包需先卸载再装 release。
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
