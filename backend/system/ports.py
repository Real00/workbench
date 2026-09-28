from typing import Protocol


class GithubCommitLookup(Protocol):
    async def latest_sha(self, repo: str, ref: str, token: str) -> str: ...
