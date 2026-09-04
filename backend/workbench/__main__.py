from aiohttp import web

from app import create_app


def main() -> None:
    web.run_app(create_app(), host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()
