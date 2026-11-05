"""Run the whole pipeline one time.

    python -m app.jobs.run_once                 # all enabled sources
    python -m app.jobs.run_once --no-llm        # force basic (regex) mode
    python -m app.jobs.run_once --source "Demo University (sample notices)"
"""
from __future__ import annotations

import argparse
import logging

from ..config import Config
from ..db import connection, init_db
from ..services import alerts, pipeline


def run(only_source: str | None = None, send_reminders: bool = True) -> dict:
    init_db()
    stats = pipeline.run_all(only_source=only_source)
    if send_reminders:
        with connection() as conn:
            stats["reminders"] = alerts.process_due_alerts(conn)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch notices, extract details, send alerts.")
    parser.add_argument("--source", help="only run the source with this exact name")
    parser.add_argument("--no-llm", action="store_true", help="skip the AI and use basic regex mode")
    parser.add_argument("--no-reminders", action="store_true", help="do not send due reminders")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.no_llm:
        Config.LLM_PROVIDER = "none"
    stats = run(args.source, send_reminders=not args.no_reminders)
    print("Done:", stats)


if __name__ == "__main__":
    main()
