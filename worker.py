"""RQ worker entry point for async task processing."""

import logging

from redis import Redis
from rq import Worker

from src.core.config import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    # Connect to Redis
    redis_conn = Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
    )

    # Create worker
    logger.info("Starting RQ worker...")
    worker = Worker(["default"], connection=redis_conn)
    worker.work()
