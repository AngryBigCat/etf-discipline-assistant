from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loguru import logger

from src.scheduler.runner import run_scheduler_job


def main() -> None:
    parser = argparse.ArgumentParser(description="Manually run a scheduled job")
    parser.add_argument(
        "--job",
        dest="job_key",
        required=True,
        help="Job key, e.g. daily_after_close or weekly_review",
    )
    args = parser.parse_args()

    result = run_scheduler_job(args.job_key)
    if result.success:
        logger.info(result.message)
        if result.detail and result.detail not in {"skipped"}:
            logger.info(result.detail)
    else:
        logger.error(result.message)
        if result.detail:
            logger.error(result.detail)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
