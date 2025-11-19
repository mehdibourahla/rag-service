#!/usr/bin/env python3
"""Start RQ worker for background job processing.

Usage:
    python scripts/start_worker.py [--burst]

Options:
    --burst: Run in burst mode (process all jobs then exit)
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import redis
from rq import Worker

from src.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def main():
    """Start the RQ worker."""
    parser = argparse.ArgumentParser(description="Start RQ worker for document processing")
    parser.add_argument(
        "--burst",
        action="store_true",
        help="Run in burst mode (process all jobs then exit)"
    )
    parser.add_argument(
        "--queue",
        type=str,
        default="default",
        help="Queue name to listen to (default: default)"
    )
    args = parser.parse_args()

    try:
        # Connect to Redis
        redis_conn = redis.from_url(settings.redis_url, decode_responses=False)

        logger.info(f"Connecting to Redis: {settings.redis_url}")
        logger.info(f"Worker listening on queue: {args.queue}")
        logger.info(f"Burst mode: {args.burst}")

        # Create and run worker
        worker = Worker(
            queues=[args.queue],
            connection=redis_conn,
            name=f"worker-{args.queue}",
        )

        logger.info("Starting RQ worker...")
        worker.work(burst=args.burst)

    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
    except Exception as e:
        logger.error(f"Worker error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
