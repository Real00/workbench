# Console backend

Python 3.12 + aiohttp 的 DDD 后端。限界上下文为 `identity`、`progress`、
`ai_settings` 和 `shared`，HTTP API 前缀统一为 `/api/v1`。

```bash
cd backend
uv sync
uv run python -m workbench
```

环境变量使用 `WORKBENCH_` 前缀。生产环境至少应设置
`WORKBENCH_JWT_SECRET`、`WORKBENCH_ADMIN_PASSWORD`、`WORKBENCH_MONGO_URI`；
也可设置一个 Fernet key 到 `WORKBENCH_ENCRYPTION_KEY`。首次启动且用户集合为空时，
会创建唯一管理员。Vue 构建产物放入 `backend/static`，服务会托管静态文件并为前端路由回退到
`index.html`。
