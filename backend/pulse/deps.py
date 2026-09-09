from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from progress.domain import ProgressDomainService
from pulse.scope import ProjectScope


class KnowledgeSearch(Protocol):
    def search(
        self,
        pattern: str,
        glob: str | None = None,
        output_mode: str = "content",
        head_limit: int = 50,
    ) -> list[Any]: ...

    def read(self, relative_path: str) -> str: ...


@dataclass
class AgentDeps:
    progress: ProgressDomainService
    knowledge: Any = None
    corpus: KnowledgeSearch | None = None
    pending: list[dict[str, Any]] = field(default_factory=list)
    context_task_id: str | None = None
    context_document_id: str | None = None
    instruction: str = ""
    scopes: list[ProjectScope] = field(default_factory=list)
    produced_messages: list[Any] = field(default_factory=list)

    @property
    def domain(self) -> ProgressDomainService:
        return self.progress
