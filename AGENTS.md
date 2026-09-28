# AGENTS.md

给在本仓库改代码的 Agent 用。人读的上手说明仍是 [README.md](README.md)；界面细节见 [docs/frontend-design.md](docs/frontend-design.md)；打包见 [docs/packaging.md](docs/packaging.md)。

## 这是什么

可持续扩展的个人工作台。平台提供应用壳、登录、系统设置和 Pulse（统一 AI）。功能以独立模块接入：当前有首页聚合、随手记、进度管理、知识库。

不要把工作台做成单体页面堆。新能力优先开新模块，不要塞进已有模块的 Store / 领域模型。

## 技术栈

- 后端：Python 3.12、aiohttp、PyMongo Async、DDD；入口 `backend/workbench`
- 前端：Vue 3 `<script setup>`、TypeScript、Vite、Tailwind v4、Pinia、shadcn-vue（Reka UI）、Lucide
- 数据库：MongoDB
- 交付：Docker 单进程（API + `backend/static`）；可选 Tauri 桌面壳（只含前端）

## 日常命令

```bash
./start_dev                          # 本机 Vite :5173 + 后端热重载；免登录
cd backend && uv run ruff check . && uv run mypy app.py workbench api identity progress ai_settings system shared && uv run pytest
cd frontend && pnpm typecheck && pnpm test && pnpm build
```

Docker `compose up --build` 只用于接近生产的验证，改代码不要靠重建镜像。若 8080 被占用：`WORKBENCH_DEV_API_PORT=8081 ./start_dev`。

环境变量前缀 `WORKBENCH_`。生产至少要有 `WORKBENCH_JWT_SECRET`、`WORKBENCH_ADMIN_PASSWORD`、`WORKBENCH_MONGO_URI`；密钥加密用 `WORKBENCH_ENCRYPTION_KEY`。

## 目录与边界

```text
frontend/src/
  app/           模块表、路由
  shell/         登录后布局
  shared/        HTTP、SSE、Pulse、命令面板、确认框、通用封装
  components/ui  shadcn 控件（拷入仓库）
  modules/<id>   功能模块：路由、页面、api、types、store
backend/
  api/           中间件、SSE、CORS
  pulse/         平台 Agent、确认写入、工具路由
  identity/      账号
  ai_settings/   模型与 Jev 配置
  capture|progress|knowledge/  功能限界上下文
  mcp/           外部 MCP（写入立即生效）
  shared/        配置、模块协议、时钟、安全
```

- 平台代码不能反向依赖某个功能模块的页面或领域类型。
- 模块之间不共享 Pinia Store 或领域模型。
- API 命名空间：`/api/v1/<feature>/*`。
- 前端模块登记在 `frontend/src/app/modules.ts`；后端模块在 `backend/app.py` 的 `modules` 元组里 `register`。

## 后端：DDD

HTTP Route → ApplicationService → DomainService → Repository。领域对象用 dataclass 充血模型（校验、工厂、状态变化放在实体 / DomainService，不要写成贫血 dict 满天飞）。

| 层 | 放什么 | 不放什么 |
| --- | --- | --- |
| `routes.py` | Pydantic 入参、鉴权后调 ApplicationService、`response()` | 业务规则、Mongo |
| `application.py` | 用例编排、DTO `asdict`、文件存储等副作用 | 跨对象不变量 |
| `domain.py` | 实体、不变量、`validate_*` / `create` / `update` | aiohttp、Mongo 驱动细节 |
| `repository.py` | 持久化、索引、文档 ↔ 实体 | HTTP、AI |

模块 `module.py` 的 `register` 负责装配依赖、写入 `app[WEB_KEY]`、把 AI 贡献 append 到 `context.ai_contributions`、注册路由、`on_startup` 初始化。测试用 `context.overrides` 注入 fake repository，不要连真 Mongo。

异常约定（`api/http.py`）：`ValidationError` → 422，`ValueError` → 400，`LookupError` → 404，`PermissionError` / 坏 JWT → 401。

写操作成功后由 `mutation_events_middleware` 按路径广播 SSE（`progress` / `knowledge` / `capture` / `ai-settings` / `all`）。`/mcp` 不走该中间件，必须在写成功后自己 `EVENT_BUS.publish`。

## 前端：模块

每个功能模块导出 `WorkbenchModule`（见 `app/module-types.ts`）：

- `routes` + `routeScope`：`public` 或 `shell`
- `nav`：侧栏分组；`platform` 组会沉到侧栏底部
- `homeCard`：首页模块入口；随手记用 `false`（首页已内嵌 composer）
- `workbench.load()`：可选，返回 `WorkbenchItem[]`（`attention` | `activity`）。首页只读投影，不 import 业务 Store。

壳订阅 `GET /api/v1/events`，300ms 合并后刷新已初始化模块，并 `dispatchEvent('workbench-changed')`。模块保存成功也可自己派这个事件。

HTTP 只用 `frontend/src/shared/api/client.ts` 的 `api`（`/api/v1`）。桌面端 API 基址来自登录页 / `VITE_API_BASE_URL`，网页端默认同源。本地 Vite 把 `/api` 代理到后端。

侧栏编辑器用 `Teleport` + `.editor-panel`，不要改成居中 Dialog。深度链接由各模块 Layout 解析 query（如 `?task=`、`?document=`）。

## 前端：UI

完整视觉说明：[docs/frontend-design.md](docs/frontend-design.md)。改界面时遵守：

- 控件：`Button` / `Input` / `Textarea` / `AppSelect` / `ChipSelect` / `Dialog` / `confirmDialog` / `CommandPalette` / `Tooltip`。
- 色板已映射到 shadcn CSS 变量。辅助文字用 `text-muted-foreground`，禁用 `text-muted`。
- 日历、甘特、Vue Flow、Pulse 输入框、RichTextarea 不替换成 shadcn。
- Select 空值用 `__empty__` 哨兵，不要 `value=""`。
- 只读 Input 用 `:model-value`，`:value` 会被忽略。
- 危险删除：`await confirmDialog({ title, message, confirmText })`。
- 新组件优先扩 `frontend/src/components/ui` 与 `shared/` 封装，不要每个模块复制一套 Dialog。

改了可见 UI 必须按真实路径点一遍（登录、快记、命令面板、列表 ChipSelect、侧栏编辑器、设置）。没有浏览器工具时用 typecheck / 测试 / 构建，并写明未点到的路径。

## Pulse / 模块 AI 工具

平台拥有时钟（`Asia/Shanghai`）、流式运行时、确认后写入。功能模块只登记工具。

在 `backend/<feature>/ai_tools.py` 提供 `ModuleAiContribution`，并在 `module.py` 里：

```python
context.ai_contributions.append(feature_ai_contribution())
```

贡献：`id`、模块 `instructions`、工具函数。平台会拼 `PLATFORM_AI_INSTRUCTIONS` 和时钟。相对日期在工具内收 `YYYY-MM-DD`，不要再问用户要日历日期。

工具规则：

- 读工具查当前数据。
- 写工具只 `pending.append(...)`，调用 `DomainService.validate_*`，失败 `ModelRetry`。
- 禁止 NativeOutput / 解析模型长文本来改领域对象。
- 不要提供删除类工具，除非产品明确要求并另做确认。
- 工具里不写库。确认走平台 token → ApplicationService → DomainService。
- 前端不要第二个 Pulse。页面上下文把 id 放进 `context_*` / `@` 提及，不要让模型猜。

```python
# 错误
app.router.add_post("/api/v1/knowledge/ai/run", run_knowledge_ai)
```

Jev 只做工具预选，不生成参数、不执行、不替代确认流。连续超时会熔断，代码在 `backend/shared/jev.py`。

MCP 与 Pulse 不同：MCP 写操作立即生效，没有站内确认。不要把 MCP 的语义套到 Pulse 上。

## 新增模块清单

1. `frontend/src/modules/<feature>/`：`index.ts` 导出 `WorkbenchModule`，含路由、导航、可选 `workbench.load`；登记到 `app/modules.ts`。
2. `backend/<feature>/`：`domain` / `repository` / `application` / `routes` / `module`；`app.py` 加入模块元组。
3. API 只用 `/api/v1/<feature>/*`。
4. 需要 AI：`ai_tools.py` + `context.ai_contributions.append(...)`。
5. 只复用平台认证、模型配置、HTTP、SSE、通用 UI；不依赖其它功能模块内部实现。

## 质量与提交

- 后端改动跑 ruff / mypy（现有包列表）/ pytest；前端跑 `pnpm typecheck && pnpm test`，涉及 UI 再 `pnpm build` 或浏览器验证。
- 不要提交密钥、`.env`、构建产物。
- 未经用户要求不要 commit / push / 改 git config。
- 回复用中文。用户提出方案时先判断是否合理，不要恭维后直接改。
