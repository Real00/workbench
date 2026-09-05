# Workbench

可持续扩展的个人工作台。平台提供统一的应用壳、身份认证、系统设置和 AI 模型配置；具体能力以独立功能模块接入。

当前提供跨模块首页、独立随手记、进度管理和知识库。首页聚合模块贡献的待处理事项与最近动态，Pulse 作为统一 AI 操作入口；未来资讯、自动化、构建发布等模块沿用同一接入方式。

## 技术栈

- 后端：Python 3.12、aiohttp、PyMongo Async API、DDD
- 前端：Vue 3、TypeScript、Tailwind CSS、Pinia
- 数据库：MongoDB
- 交付：Docker 多阶段构建；生产环境由一个 aiohttp 进程同时提供 API 和前端资源

## 模块边界

```text
Workbench
├── Platform
│   ├── 应用壳与模块注册
│   ├── 身份认证
│   ├── 系统 AI 配置
│   └── Pulse：时钟、工具注册表、流式执行、确认后写入
└── Modules
    └── Progress
        ├── 任务与成员
        ├── 多视图进度展示
        └── ai_tools（登记给 Pulse 的工具，不自建 Agent）
```

- 前端功能模块位于 `frontend/src/modules/<module>`，模块自行声明路由、菜单和页面。
- 后端功能模块位于 `backend/<module>`，模块自行装配 DDD 依赖并注册 API。
- 平台共享能力不能反向依赖具体功能模块；模块之间不共享 Store 或领域模型。
- 新模块使用独立 API 命名空间，例如 `/api/v1/knowledge/*`。
- 模块若要给 AI 操作，抽出 `ai_tools.py` 登记到 `context.ai_contributions`，沿用平台 Pulse；不要每个模块再做一套对话和 SSE。

## Docker 启动

用于打包验证或接近生产的单进程部署，**不是日常改代码的方式**。改代码后需要重新 `build`，会很慢。

```bash
cp .env.example .env
docker compose up --build
```

访问 <http://localhost:8080>。

## 本地开发

日常调试用本机进程，不要重建镜像：

- 前端：Vite 保存即热更新
- 后端：`watchfiles` 监听 `.py` 变更并自动重启 aiohttp
- Mongo：仅数据库用 Docker 容器，改业务代码不必动它

```bash
cp .env.example .env   # 首次使用
./start_dev
```

访问 <http://localhost:5173>。Vite 会把 `/api` 请求代理到 `http://localhost:8080`。

也可分别启动：

```bash
cd backend && uv sync && uv run watchfiles --filter python --ignore-paths .venv "python -m workbench" .
cd frontend && pnpm install && pnpm dev
```

## 质量检查

```bash
cd backend && uv run ruff check . && uv run mypy app.py workbench api identity progress ai_settings shared && uv run pytest
cd frontend && pnpm typecheck && pnpm test && pnpm build
```

## AI 配置

登录后进入“系统设置”，配置 OpenAI 兼容的 Base URL、模型和 API Key。工作台通过 Pydantic AI 调用模型。当前官方 OpenAI 域名使用 Responses，其余兼容网关使用 Chat Completions。Base URL 必须填写服务商的 API 基础地址及其路径，例如 `https://api.openai.com/v1`；仅填写网站域名可能收到 HTML 页面而不是模型事件。设置页的“测试模型连接”会实际验证所选模型的流式输出。API Key 由后端加密保存，默认仅返回脱敏值，管理员主动点击查看时才单独读取明文。

进度管理模块把任务相关能力登记为工具（查看/创建/更新/记录进度），由平台 Pulse 通过 Responses API 流式调用。工具只排队变更，必须人工确认后才会写入。任务过程中的阻塞、额外处理和推进记录写在任务内的进度时间线里，不拆成独立任务。图片、文档和外链作为任务资源保存。成员不是登录账号，只作为该模块的任务分配对象；技能和项目背景用于 AI 匹配负责人。

## 新增功能模块

1. 在 `frontend/src/modules/<feature>` 内维护模块自己的路由、页面、API、类型和 Store，并注册到工作台模块表。
2. 在 `backend/<feature>` 内按 Repository、DomainService、ApplicationService、HTTP Route 分层，并由模块入口自行装配。
3. API 使用 `/api/v1/<feature>/*`，不要复用其他模块的业务路径。
4. 只复用平台提供的认证、模型配置、HTTP 和通用 UI，不直接依赖其他功能模块内部实现。
5. 需要 AI 操作时，在 `backend/<feature>/ai_tools.py` 实现工具，并 `context.ai_contributions.append(...)`。读工具查数据，写工具只入队并走领域校验，禁止模块内再起 Agent、SSE 或对话框。
6. 相对日期由平台时钟（Asia/Shanghai）解析，模块工具接收 `YYYY-MM-DD`，不要再问用户要具体日期。

## 跨模块首页与随手记

- 首页展示快速记录、关注与最近记录、待处理事项、最近动态和模块入口。
- 随手记只要求正文，保存直接调用 `/api/v1/captures`，不等待 AI，也不进入 AI 变更确认。
- 全局快捷键 `Ctrl/Cmd + Shift + J` 打开快记；输入框内 `Ctrl/Cmd + Enter` 保存。
- 记录按登录账号隔离，支持原文搜索、置顶、归档与恢复，列表每页 50 条。
- 当前标签页的草稿按账号保存在 sessionStorage；保存失败保留草稿，同一请求编号重试不会重复创建。
- “交给 Pulse”只将原文与分析请求放入 AI 输入框，用户发送后才运行；不自动转换为任务。

### 模块贡献首页内容

前端模块在 `WorkbenchModule.workbench.load` 登记异步读取函数，返回 `WorkbenchItem[]`：

- `id`：模块内稳定编号；首页使用模块 ID 与它组合去重标识。
- `kind`：`attention`（待处理）或 `activity`（动态）。
- `title`、`summary`、`occurredAt`：展示内容与时间。
- `to`：模块自己维护的详情路由，模块负责解析对象参数。

首页通过模块注册表读取这些投影，不访问业务 Store。单个模块加载失败会显示错误，其他模块仍然可用。模块操作成功后可发出 `workbench-changed` 事件刷新首页。

当前进度模块提供逾期待处理与任务最近更新时间，知识模块提供文档/条目的最近更新时间。这些是当前对象的摘要，尚非完整历史事件流；历史 blocker 不会被误当作仍未解除的待处理事项。模块筛选目前仅在本次首页停留期间生效。

本轮没有实现资讯采集、工作流调度或构建发布执行器；后续应由独立模块维护业务状态与运行记录，按上述约定接入首页，并向 Pulse 登记工具。
