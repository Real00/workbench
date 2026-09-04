from aiohttp import web

from knowledge.ai_tools import knowledge_ai_contribution
from knowledge.application import KnowledgeApplicationService
from knowledge.corpus import FilesystemKnowledgeCorpus
from knowledge.domain import KnowledgeDomainService
from knowledge.repository import MongoDocumentRepository, MongoEntryRepository, MongoTagRepository
from knowledge.routes import register_routes
from shared.module import ModuleContext
from shared.web_keys import KNOWLEDGE


class KnowledgeModule:
    def register(self, app: web.Application, context: ModuleContext) -> None:
        tags = context.overrides.get("knowledge_tag_repository") or MongoTagRepository(
            context.mongo, context.settings.mongo_database
        )
        entries = context.overrides.get("knowledge_entry_repository") or MongoEntryRepository(
            context.mongo, context.settings.mongo_database
        )
        documents = context.overrides.get(
            "knowledge_document_repository"
        ) or MongoDocumentRepository(context.mongo, context.settings.mongo_database)
        corpus = context.overrides.get("knowledge_corpus") or FilesystemKnowledgeCorpus(
            context.settings.knowledge_dir
        )
        service = KnowledgeApplicationService(
            KnowledgeDomainService(tags, entries, documents), corpus
        )
        app[KNOWLEDGE] = service
        context.ai_contributions.append(knowledge_ai_contribution())

        async def startup(_: web.Application) -> None:
            await service.initialize()

        app.on_startup.append(startup)
        register_routes(app)
