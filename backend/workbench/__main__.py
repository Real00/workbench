from aiohttp import web

from app import create_app
from shared.config import get_settings


def main() -> None:
    settings = get_settings()
    host = "127.0.0.1" if settings.dev_auth_bypass else "0.0.0.0"
    web.run_app(create_app(settings), host=host, port=settings.dev_api_port)


if __name__ == "__main__":
    main()
