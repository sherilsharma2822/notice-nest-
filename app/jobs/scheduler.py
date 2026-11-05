"""Run the pipeline again and again, forever (Ctrl+C to stop).

    python -m app.jobs.scheduler --every-minutes 180

This is the simplest possible scheduler: run, sleep, repeat.
On a real server you could use cron, Windows Task Scheduler or a scheduled GitHub Action
to call `python -m app.jobs.run_once` instead.
"""
from __future__ import annotations

import argparse
import logging
import time

from .run_once import run

log = logging.getLogger("scheduler")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--every-minutes", type=int, default=180)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    while True:
        try:
            log.info("Run finished: %s", run())
        except Exception:
            log.exception("Run crashed; will try again next time.")
        time.sleep(max(1, args.every_minutes) * 60)


if __name__ == "__main__":
    main()
