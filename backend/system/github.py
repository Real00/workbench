from __future__ import annotations

from aiohttp import ClientError, ClientSession, ClientTimeout


class GithubCommitClient:
    def __init__(self, *, base_url: str = "https://api.github.com") -> None:
        self.base_url = base_url.rstrip("/")

    async def latest_sha(self, repo: str, ref: str, token: str) -> str:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "workbench-update-check",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        url = f"{self.base_url}/repos/{repo}/commits/{ref}"
        timeout = ClientTimeout(total=15)
        try:
            async with ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 404:
                        raise LookupError(
                            f"未找到仓库或分支 {repo}@{ref}；"
                            "私有仓需配置 WORKBENCH_UPDATE_GITHUB_TOKEN"
                        )
                    if resp.status in {401, 403}:
                        raise ValueError(
                            "GitHub API 拒绝访问；请检查 WORKBENCH_UPDATE_GITHUB_TOKEN 权限"
                        )
                    if resp.status >= 400:
                        text = await resp.text()
                        raise ValueError(f"GitHub API 错误 {resp.status}: {text[:200]}")
                    data = await resp.json()
        except TimeoutError as exc:
            raise ValueError("检查更新超时，请稍后重试") from exc
        except ClientError as exc:
            raise ValueError(f"无法连接 GitHub：{exc}") from exc
        sha = data.get("sha") if isinstance(data, dict) else None
        if not isinstance(sha, str) or not sha:
            raise ValueError("GitHub 返回的提交信息不完整")
        return sha
