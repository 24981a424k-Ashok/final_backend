import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.scheduler.task_scheduler import run_news_cycle
from loguru import logger

async def test_cycle():
    logger.info("Manually triggering news cycle for verification...")
    await run_news_cycle()
    logger.info("Cycle completed.")

if __name__ == "__main__":
    asyncio.run(test_cycle())
