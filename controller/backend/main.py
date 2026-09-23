"""Main entrypoint for IoTMesh Controller backend service."""

import argparse
import asyncio
import logging
import signal
import sys

from aiohttp import web

from backend import config, db
from backend.api import POLLER_KEY, create_app
from backend.coap_client import CoapClient
from backend.poller import PollerService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("controller")


def parse_args():
    parser = argparse.ArgumentParser(description="IoTMesh Controller Backend")
    parser.add_argument("--host", default=config.HTTP_HOST, help="HTTP server bind host")
    parser.add_argument("--port", type=int, default=config.HTTP_PORT, help="HTTP server port")
    parser.add_argument(
        "--no-cadence", action="store_true", help="Disable automated periodic polling cadence"
    )
    return parser.parse_args()


async def on_startup(app: web.Application):
    """Lifecycle startup hook: initializes DB and launches background poller."""
    logger.info("Initializing SQLite database...")
    db.init_db(config.DB_PATH)

    poller: PollerService = app[POLLER_KEY]
    if not app.get("disable_cadence", False):
        logger.info(f"Starting background poller cadence (every {config.POLL_INTERVAL_S}s)...")
        poller.start()
    else:
        logger.info("Background cadence disabled by flag")


async def on_cleanup(app: web.Application):
    """Lifecycle shutdown hook: halts background poller cleanly."""
    logger.info("Shutting down background services...")
    poller: PollerService | None = app.get(POLLER_KEY)
    if poller:
        poller.stop()


def main():
    args = parse_args()
    logger.info(f"Starting {config.DEVICE_ID} ({config.DEVICE_TYPE}) on http://{args.host}:{args.port}")

    db.init_db(config.DB_PATH)
    coap_client = CoapClient()
    poller = PollerService(db_path=config.DB_PATH, coap_client=coap_client)

    app = create_app(poller=poller)
    app["disable_cadence"] = args.no_cadence
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    web.run_app(app, host=args.host, port=args.port, print=None)


if __name__ == "__main__":
    main()
