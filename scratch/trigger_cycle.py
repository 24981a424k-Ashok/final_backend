import asyncio
import sys
import os

# Add the root directory to sys.path
sys.path.append(os.getcwd())

from src.scheduler.task_scheduler import run_news_cycle

async def main():
    print("Triggering Manual News Cycle for Verification...")
    await run_news_cycle()
    print("Manual Cycle Completed.")

if __name__ == "__main__":
    asyncio.run(main())
