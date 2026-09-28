from aiohttp import web

from shared.module import ModuleContext
from shared.web_keys import EVENT_BUS, SUBSCRIPTION
from subscription.ai_tools import subscription_ai_contribution
from subscription.application import SubscriptionApplicationService
from subscription.domain import SubscriptionDomainService
from subscription.fetcher import HttpFetcher
from subscription.plugin_runner import PluginSubprocessRunner
from subscription.repository import (
    MongoArticleRepository,
    MongoPluginRepository,
    MongoSourceRepository,
)
from subscription.routes import register_routes
from subscription.scheduler import SubscriptionScheduler


class SubscriptionModule:
    def register(self, app: web.Application, context: ModuleContext) -> None:
        plugins = context.overrides.get("subscription_plugin_repository") or MongoPluginRepository(
            context.mongo, context.settings.mongo_database
        )
        sources = context.overrides.get("subscription_source_repository") or MongoSourceRepository(
            context.mongo, context.settings.mongo_database
        )
        articles = context.overrides.get(
            "subscription_article_repository"
        ) or MongoArticleRepository(context.mongo, context.settings.mongo_database)
        fetcher = context.overrides.get("subscription_fetcher") or HttpFetcher()
        runner = context.overrides.get("subscription_runner") or PluginSubprocessRunner()
        enable_scheduler = context.overrides.get("subscription_enable_scheduler", True)
        domain = SubscriptionDomainService(plugins, sources, articles)
        service = SubscriptionApplicationService(
            domain,
            fetcher=fetcher,
            runner=runner,
            event_bus=app[EVENT_BUS],
            enable_scheduler=bool(enable_scheduler),
        )
        app[SUBSCRIPTION] = service
        context.ai_contributions.append(subscription_ai_contribution())
        scheduler = SubscriptionScheduler(
            service.refresh_due_sources,
            enabled=service.enable_scheduler,
        )
        service.scheduler = scheduler

        async def startup(_: web.Application) -> None:
            await service.initialize()
            scheduler.start()

        async def cleanup(_: web.Application) -> None:
            await scheduler.stop()

        app.on_startup.append(startup)
        app.on_cleanup.append(cleanup)
        register_routes(app)
