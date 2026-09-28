# 前端设计

工作台前端是一套浅色、信息密度中等的个人操作界面。视觉语言保持现有 ink / panel / cyan 色板，不另起一套主题；交互控件统一走 shadcn-vue（Reka UI），页面骨架、表格、卡片、侧栏编辑器继续用工作台自己的 CSS。

本文是界面与交互的完整说明。工程约定见仓库根目录 [AGENTS.md](../AGENTS.md)。

## 1. 产品表面

平台壳负责登录、导航、命令面板、随手记对话框、Pulse 助手和系统设置。功能模块以独立目录接入，自行声明路由、菜单和 Store，首页只消费模块投影，不直连业务 Store。

| 表面 | 路由 | 作用 |
| --- | --- | --- |
| 登录 | `/login` | 账号密码；桌面端额外填写服务器地址 |
| 工作台首页 | `/` | 快记、待处理、最近动态、模块入口 |
| 随手记 | `/captures` | 原文记录、搜索、置顶、归档 |
| 进度总览 | `/progress` | 健康度、进行中任务、风险 |
| 任务视图 | `/progress/tasks` | 列表 / 看板 / 日历 / 甘特 |
| 项目管理 | `/progress/projects` | 项目卡片与状态 |
| 成员管理 | `/progress/members` | 成员卡片与完成度 |
| 知识库 | `/knowledge` | 文档 / 条目 / 标签；画布 |
| 平台设置 | `/settings` | 模型连接、工具注册、设备、MCP |

右侧 Pulse 与侧栏编辑器叠在壳上，不属于独立路由。

## 2. 设计原则

1. **沿用工作台外观，不重做视觉。** 色板、卡片圆角、侧栏宽度、编辑器抽屉都已有 CSS。引入组件库只替换控件实现，不换成另一套间距或阴影。
2. **操作面与展示面分开。** 按钮、输入、选择、对话框、命令面板用 shadcn。表格行、看板卡片、任务行、封面色块、分段 Tab 仍用页面级 class。
3. **编辑发生在侧栏，不发生在全屏 Dialog。** 任务 / 成员 / 项目 / 文档 / 条目 / 标签打开右侧 `editor-panel`。Dialog 只用于快记和系统级确认。
4. **AI 只有一个入口。** Pulse 负责对话、工具排队和确认写入。模块不要再做对话框或 `/ai/run`。
5. **写操作可确认、可同步。** 危险删除走 `confirmDialog`。任意端写入后走 SSE，前端静默刷新，桌面端不依赖刷新按钮。
6. **中文界面、英文 eyebrow 可隐藏。** `.eyebrow` 默认 `display: none`，页面标题与说明用中文。

## 3. 色板与 Token

品牌色定义在 `frontend/src/style.css` 的 `@theme`，并映射到 shadcn 语义变量，组件才能吃到同一套颜色。

| Token | 值 | 用途 |
| --- | --- | --- |
| `--color-ink` | `#f6f7f9` | 页面底、侧栏底 |
| `--color-panel` | `#ffffff` | 卡片、弹出层、编辑器 |
| `--color-panel-2` | `#f1f4f8` | 次级块、hover |
| `--color-line` | `#e4e7ec` | 分割线、边框 |
| `--color-cyan` | `#2563eb` | 主操作、强调、进度 |
| `--color-text` | `#202939` | 正文 |
| `--color-text-secondary` | `#475467` | 标签、次要说明 |
| `--muted-foreground` | `#667085` | 辅助文字（原 `text-muted` 已废弃） |
| `--color-success` | `#16794b` | 成功 |
| `--color-warning` | `#946200` | 风险、逾期 |
| `--color-danger` | `#c43232` | 删除、错误 |

shadcn 映射：`--primary` ← cyan，`--background` ← ink，`--card` / `--popover` ← panel，`--destructive` ← danger，`--border` / `--input` ← line / `#cbd2dc`，`--ring` ← cyan。圆角 `--radius: 0.5rem`。

**禁止**再使用 `text-muted`。Tailwind v4 会把它解析成 `--color-muted`（一块背景色）。辅助文字一律 `text-muted-foreground`。

## 4. 字体、密度、布局常量

- 字体：系统 UI 栈（SF / PingFang / YaHei）。展示标题用 `--font-display`，等宽编号用 `--font-mono`。
- 页面：`.page-wrap` 最大 1500px，内边距 `32px 32px 88px`（底部给 Pulse 触发器留空）。
- 侧栏：展开 236px，收起 64px；主区 `padding-left` 同步。Pulse 打开时主区 `padding-right: 472px`，加宽后 `752px`。
- 卡片：12px 圆角、1px `line` 边框、白底、20px 内边距。
- 控件高度：输入 / 选择 40px（`Input` 默认 `h-10`，`AppSelect` trigger 同高）。主按钮沿用 shadcn `h-8`，空状态和页头主操作可 visually 偏紧，不要再叠一套 `.btn-primary`。
- 图标：`@lucide/vue`，导航 18px，按钮内 15–16px，芯片内 10–13px。

## 5. 应用壳

`WorkbenchShell` 是登录后的唯一布局：

```
┌──────────┬──────────────────────────────────────┐
│ 品牌     │                                      │
│ 随手记   │           RouterView 页面             │
│ 首页     │                                      │
│ 模块导航 │     Pulse（收起为右下触发器）          │
│ 平台设置 │     快记 Dialog / 命令面板 / 确认框    │
│ 收起/退出│                                      │
└──────────┴──────────────────────────────────────┘
```

- 侧栏导航是 `RouterLink.nav-link`；随手记、收起、退出是 `Button` + `.nav-link`。
- 小于 `lg` 用遮罩抽屉导航，左上角汉堡按钮 `Button variant="outline" size="icon"`。
- 快记是 `Dialog`，标题「快速记录」，内容复用 `CaptureComposer`。
- `ConfirmDialog` 与 `CommandPalette` 挂在壳上，全局一份。

`App.vue` 只包 `TooltipProvider` + `RouterView` + `Toaster`（`position="top-center"`）。

## 6. 组件分层

### 6.1 必须用的 shadcn 控件

源码在 `frontend/src/components/ui/`，按 [components.json](../frontend/components.json) 的 new-york 风格拷入仓库，不要运行时依赖 registry。

| 场景 | 组件 | 说明 |
| --- | --- | --- |
| 主操作 / 次操作 / 图标 / 文字链 | `Button` | `default` / `outline` / `ghost` / `destructive` / `link` |
| 单行输入 | `Input` | 允许 `string \| number \| null`；日期、数字、只读密钥都走它 |
| 多行输入 | `Textarea` | 随手记、标签解释 |
| 表单下拉 | `AppSelect` | 内部是 `Select`；空值哨兵 `__empty__` |
| 行内状态/负责人芯片 | `ChipSelect` | 去掉 SelectTrigger 铬，保留芯片外观 |
| 模态 | `Dialog` | 目前仅快记 |
| 危险确认 | `confirmDialog()` → `AlertDialog` | 不要自己写 `window.confirm` |
| 命令面板 | `CommandDialog` + `CommandPaletteList` | `⌘/Ctrl+K` |
| 简短说明 | `Tooltip` | 画布缩放等图标按钮 |
| 轻提示 | `Toaster`（vue-sonner） | 已挂载，新增瞬时反馈优先用它 |

新增同类控件时先扩这些封装，不要每个页面再包一层。

### 6.2 应用封装

- **`AppSelect`**：`defineModel<T \| null>()`，选项 `{ value, label, hint? }`。空字符串 option 编码为 `__empty__`，因为 Reka Select 不允许 `value=""`。
- **`ChipSelect`**：同上，trigger 使用既有 `priority` / `status-chip` / `project-status` / `assignee-chip` class。列表、看板里改状态必须停掉行点击（`@click.stop`）。
- **`confirmDialog({ title, message, confirmText, danger? })`**：默认按危险操作（警示图标 + destructive 按钮）。返回 `Promise<boolean>`。
- **`CommandPalette`**：打开时补初始化未加载的 Store，并拉最近 50 条随手记。空搜索只挂 `default` 命令；输入后挂全部条目，交给 Command 过滤。`keywords` 放在 `sr-only` 里参与匹配。

### 6.3 不要用组件库替换的东西

| 表面 | 原因 |
| --- | --- |
| 任务日历（FullCalendar） | 第三方时间网格 |
| 甘特图（frappe-gantt） | 第三方时间条 |
| 知识画布（Vue Flow） | 节点拖拽画布；缩放按钮可包 Tooltip |
| `RichTextarea` / `MarkdownView` | 模块内 Markdown 编辑与预览 |
| Pulse 输入框 | 需要 autosize 和 `@` 提及，暂留原生 `textarea.input` |
| 原生 checkbox / range / color / file | 无对应封装，且不是主路径表单控件 |
| `.view-tab`、`.kind-option`、`.nav-link`、`.cover-swatch` | 分段开关、胶囊筛选、导航、色板；可用 `Button` 作根节点，但外观由这些 class 决定 |
| `.task-row`、`.resource-main`、表格行 | 列表项，不是按钮控件 |
| `.ai-trigger`、`.ai-mention-item` | Pulse 专属 |

## 7. 页面模式

所有业务页套 `.page-wrap`。

**页头** `.page-header`：左侧 eyebrow（可隐藏）+ `h1` + 一句说明；右侧 1–3 个 `Button`（主操作 `default`，次操作 `outline`）。

**工具条**：圆角边框条，左分段 Tab（`.segmented-tabs` + `.view-tab`），右 `.search-box`（放大镜 + `Input`，输入框去边框、去 focus ring）。知识库内容类型用 `.content-tabs` 下划线 Tab，不要和分段 Tab 混用。

**卡片网格**：项目 / 成员用 `.entity-grid` + `.entity-card`。整卡可点，内部 ChipSelect / 状态切换要 `@click.stop`。

**空状态** `.empty-state`：图标 + 标题 + 说明 + 一个行动按钮。搜索无结果提供「清除搜索」。

**加载**：页级用顶栏 `.loading-bar`；列表用 `.skeleton` 行，不要转圈占满整页。

**错误**：模块布局顶栏 `.error-banner` + `Button variant="link"` 重试。表单内 `.error-box` / `.success-box`。

**表单字段** `.field-label`：标签在上，控件在下。shadcn Input / Textarea / SelectTrigger 靠 `[data-slot=…] { margin-top: 8px }` 对齐。嵌套在 `relative` 容器里的输入要加 `!mt-0`。

**输入焦点**：文本类控件（`Input` / `Textarea` / `SelectTrigger` / `.search-box` / `.rich-textarea` / Pulse composer）统一为「只加深边框色」，不加外圈 `ring`，避免双层描边。按钮仍可保留键盘 `ring`。

## 8. 各页面

### 登录

左右分栏：左品牌（大标题、cyan 强调、pulse 装饰），右表单。用户名 / 服务器 / 密码为 `Input`，左侧绝对定位 Lucide 图标（`pl-8`）。「保持登录」原生 checkbox。提交 `Button` 全宽。桌面壳显示服务器地址，网页端隐藏。

### 首页

快记英雄卡 → 来源筛选 checkbox → 两列：待处理 + 最近动态；关注记录 + 模块入口。Feed 是 `RouterLink.workbench-feed`，不是 Button。首页通过 `module.workbench.load()` 拉投影，单项失败不影响其它模块。模块写成功后派发 `workbench-changed`。

### 随手记

Composer：`Textarea` + `⌘/Ctrl+Enter` 保存，不分类。列表：搜索 `Input` + 归档 checkbox；条目操作 `Button variant="ghost" size="sm"`（置顶 / 交给 Pulse / 归档）。「交给 Pulse」只把原文填进输入框，不自动跑模型。草稿按账号放 sessionStorage。

### 进度

- **总览**：四格 metric 卡 + 进行中任务行 + 风险 + 操作记录。任务行 `.task-row`。
- **任务**：默认列表。列表里优先级 / 状态 / 负责人是 `ChipSelect`。看板列同样。日历与甘特只读展示，点任务仍打开侧栏编辑器。
- **任务编辑器**：右侧抽屉。名称 `Input`，描述 `RichTextarea`（编辑 / 预览为 `.kind-option`），负责人 / 项目 / 状态 / 优先级 `AppSelect`，日期与工时 `Input`，进度原生 range。资源区文件 + 外链。删除走确认框。
- **项目 / 成员**：卡片网格；编辑器同样是右侧抽屉。成员技能是芯片 + 回车添加，不是 Select。

深度链接：`/progress/tasks?task=<id>` 由 `ProgressLayout` 打开对应任务。

### 知识库

列表 / 画布切换。列表再分文档、条目、标签表。画布用 Vue Flow 展示文档节点，可拖拽落位；右下缩放按钮带 Tooltip。编辑器抽屉：文档支持 Markdown 与文件导入（`.md/.txt/.docx`），条目是键值 + 别名，标签名称 + 解释 `Textarea`。

深度链接：`?document=` / `?entry=`。

### 设置

左 `.nav-link` 分类：模型连接、AI 工具注册、绑定设备、MCP。厂商预设是 `.kind-option` 胶囊。密钥只读展示用 `Input :model-value`（不要 `:value`，受控组件不认）。MCP 页提供复制配置的 `Button variant="link"`。Jev 是可选字段集，独立密钥。

## 9. Pulse

右下触发器 `.ai-trigger`；展开为 440px 侧栏，标题栏可一键加宽到 720px（记住选择）。

- 快捷键：`⌘/Ctrl+I` 开关；`⌘/Ctrl+Enter` 确认排队变更；`Shift+Enter` 换行；`↑` 在上一条原文修改；气泡内 `Enter` 重发、`Esc` 取消。
- `@` 弹出提及列表（任务 / 成员 / 项目 / 文档 / 工具），把稳定 id 放进 `context_*`，不要让模型猜当前页对象。
- 用户气泡在原文上修改后重发（`rewind_exchanges` 丢掉其后轮次）；助手回答下方用小图标复制原文、切换原文/渲染、重试。
- 可粘贴 / 拖入 / 选择 `.md` `.txt` `.docx`。附件先上传到 `/ai/attachments`，发送时带 `attachment_ids`；空文案默认请模型阅读并在合适时存进知识库。确认卡片展示 `create_document_from_attachment`。
- 助手回答用现有 `MarkdownView`（`marked` GFM + DOMPurify）：表格、列表、代码块、删除线；用户气泡仍是原文。
- 工具调用以芯片展示；变更以预览卡片展示；确认前不写库。
- 不要做第二个 Pulse。新模块的写操作通过后端工具进入同一对话框。

## 10. 命令面板

`⌘/Ctrl+K`。默认列表：导航、新建任务、快速记录、打开 AI。输入后检索任务、成员、项目、文档、条目、随手记。执行后关闭面板并 `run()`。

## 11. 快捷键

| 键 | 范围 | 行为 |
| --- | --- | --- |
| `⌘/Ctrl+K` | 全局 | 命令面板 |
| `⌘/Ctrl+I` | 全局 | Pulse |
| `⌘/Ctrl+Shift+J` | 应用内 | 快记 Dialog |
| `⌘/Ctrl+Alt+J` | 仅桌面全局 | 唤起窗口并打开快记 |
| `⌘/Ctrl+Enter` | 快记输入 | 保存 |
| `⌘/Ctrl+Enter` | Pulse 有待确认变更 | 应用 |
| `Esc` | 对话框 / 面板 | 关闭 |

输入法合成中（`isComposing`）忽略快捷键。

## 12. 动效与状态

过渡只用 150–200ms 的颜色 / 边框 / 宽度。尊重 `prefers-reduced-motion`（已有控件 transition 关闭规则）。不要加页面级 parallax 或大入场动画。

加载用骨架或顶栏细线；保存中按钮 disabled 并改文案（「保存中…」）。SSE 刷新应无感知，不要弹 toast 刷屏。

## 13. 响应式

- `lg` 以下侧栏改抽屉；页头按钮可换行。
- 任务工具条 `flex-col` → `md:flex-row`。
- 登录左栏 `hidden lg:flex`。
- 画布、甘特、日历允许横向滚动，不要在小屏强行重排时间轴。

## 14. 实时数据

壳在挂载时订阅 `GET /api/v1/events`。300ms 合并后按 `scope` 刷新已初始化模块（`progress` / `knowledge` / `capture`），并派发 `workbench-changed`。不要在每个页面再开一条 SSE。

## 15. 反模式

- 再引入另一套 UI 库或把日历 / 甘特 / 画布改成 shadcn。
- 用 `NativeOutput` 或解析模型长文本代替工具入队。
- 模块内新建 Agent、SSE、AI 预览 JSON 对话框。
- 侧栏编辑器改成居中 Dialog（字段多、要对照列表）。
- 把 `text-muted` 当灰色字。
- 给 Select 传空字符串 value。
- 只读 Input 用 `:value` 而不是 `:model-value`。
- 在工具或前端猜测「当前任务」而不传 id。
