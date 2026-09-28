# 订阅解析插件编写规范

给人和 AI 写订阅源解析插件用。平台负责 HTTP 拉取；插件只解析响应正文。

## 运行模型

1. 平台按订阅源 URL 发起 GET（可选 `config.headers`）。
2. 将 `{url, body, config}` 经 stdin 传给子进程。
3. 子进程加载你的脚本，找到唯一的 `SubscriptionParser` 子类，调用 `parse`。
4. 插件把文章列表写成 JSON 打到 stdout：`{"articles":[...]}`。
5. 平台按 `(source_id, external_id)` 幂等入库。

**不要在插件里发 HTTP、读写文件、访问网络。** 需要额外请求属于二期能力。

## 必须实现的基类

```python
from subscription.plugin_runtime.base import ParsePayload, ParsedArticle, SubscriptionParser

class MyParser(SubscriptionParser):
    def parse(self, payload: ParsePayload) -> list[ParsedArticle]:
        ...
```

- 脚本里只能有 **一个** 非抽象的 `SubscriptionParser` 子类。
- 可用标准库；子进程环境不保证第三方包。

## ParsedArticle 字段

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `external_id` | 是 | 源内稳定 ID（guid / 链接 / 哈希） |
| `title` | 是 | 标题；空则平台显示「(无标题)」 |
| `content` | 否 | 正文 |
| `content_format` | 否 | `html`（默认）或 `markdown` |
| `published_at` | 否 | ISO8601 或 RFC2822 可解析字符串 |
| `author` | 否 | 作者 |
| `cover_url` | 否 | 封面图 http(s) URL |
| `url` | 否 | 原文链接 http(s) URL |

前端按 `content_format` 消毒后展示：Markdown 走 GFM；HTML 走白名单消毒。

## stdin / stdout

stdin：

```json
{
  "url": "https://example.com/feed.xml",
  "body": "...raw response text...",
  "config": {}
}
```

stdout（成功，exit 0）：

```json
{
  "articles": [
    {
      "external_id": "https://example.com/posts/1",
      "title": "Hello",
      "content": "<p>world</p>",
      "content_format": "html",
      "published_at": "2026-01-02T03:04:05+00:00",
      "author": "Ada",
      "cover_url": null,
      "url": "https://example.com/posts/1"
    }
  ]
}
```

失败时非 0 退出，错误信息写 stderr；平台记入订阅源 `last_error`。

## 最小示例（Markdown 列表）

```python
from subscription.plugin_runtime.base import ParsePayload, ParsedArticle, SubscriptionParser

class LineParser(SubscriptionParser):
    def parse(self, payload: ParsePayload) -> list[ParsedArticle]:
        articles = []
        for index, line in enumerate(payload.body.splitlines()):
            text = line.strip()
            if not text:
                continue
            articles.append(
                ParsedArticle(
                    external_id=f"line-{index}",
                    title=text[:80],
                    content=text,
                    content_format="markdown",
                )
            )
        return articles
```

仓库内置插件「RSS / Atom」可在控制台复制改造。站内「试跑」可用样例 body 验证脚本。

## 常见错误

- 未继承 `SubscriptionParser`，或定义了多个子类。
- 返回非 list / 缺 `external_id`。
- `content_format` 写成别的值（只允许 `markdown` / `html`）。
- 在插件里 `urllib.request` 拉详情页（会被规范拒绝；当前运行时也不提供密钥）。
- stdout 打印调试信息破坏 JSON（调试请用 stderr）。

## 给 AI 的实现清单

1. 从用户描述的源格式选择解析策略（RSS/Atom/JSON/自定义 HTML）。
2. 写出完整可粘贴脚本：一个 `SubscriptionParser` 子类 + `parse`。
3. 映射稳定 `external_id`，声明正确的 `content_format`。
4. 用短样例 body 自检字段；提醒用户在「试跑」里验证后再挂到订阅源。
