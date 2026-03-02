"""
scheduler.py — Automated full-pipeline scheduler (every 15 days).

Runs as a standalone background process. Start it once and it will
execute the complete pipeline on the configured schedule:

  1. Screener on ALL markets (fresh data)
  2. Merge candidates into watchlist
  3. Full Buffett analysis on the watchlist
  4. Results saved to results_cache.json (Ranking tab auto-updates)

Usage:
    python3 scheduler.py                  # run every 15 days (default)
    python3 scheduler.py --interval 15d   # same as above (explicit)
    python3 scheduler.py --interval daily # run Mon-Fri at 17:00 ET (testing)
    python3 scheduler.py --interval weekly # run every Monday at 08:00 ET (testing)
    python3 scheduler.py --run-now        # run immediately, then follow schedule
    python3 scheduler.py --launchd        # print macOS launchd plist for auto-start

Why a separate process (not embedded in Streamlit):
  Streamlit re-runs the entire script on every interaction. Embedding a
  scheduler inside it would create multiple scheduler instances. A separate
  process is the correct pattern — it runs independently and writes to the
  shared JSON cache that Streamlit reads.

How to start automatically on macOS login:
  See the generated launchd plist printed by --launchd.
"""

import argparse
import logging
import os
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

import pipeline as pipeline_mod
import watchlist as wl

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SCHEDULER] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _log_progress(msg: str, pct: float) -> None:
    logger.info(f"  {pct*100:3.0f}% — {msg}")


def run_pipeline() -> None:
    """Single pipeline run — called by the scheduler on each fire."""
    logger.info("=" * 60)
    logger.info("Starting scheduled pipeline run...")
    logger.info("=" * 60)
    try:
        status = pipeline_mod.run_full_pipeline(progress_callback=_log_progress)
        logger.info(
            f"Pipeline complete. "
            f"Candidates: {status.get('candidates_found', '?')} | "
            f"Added to WL: {status.get('added_to_watchlist', '?')} | "
            f"WL size: {status.get('watchlist_size', '?')} | "
            f"Duration: {status.get('duration_seconds', 0)/60:.1f} min"
        )
        logger.info(f"Next run: {status.get('next_run_at', '?')[:10]}")
    except Exception as exc:
        logger.error(f"Pipeline run failed: {exc}", exc_info=True)
    logger.info("=" * 60)


def print_launchd_instructions(script_path: str) -> None:
    plist = f"""
To start this scheduler automatically on macOS login, create a launchd plist:

1. Create file: ~/Library/LaunchAgents/com.buffettbot.scheduler.plist

<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.buffettbot.scheduler</string>
    <key>ProgramArguments</key>
    <array>
        <string>{sys.executable}</string>
        <string>{script_path}</string>
        <string>--interval</string>
        <string>15d</string>
        <string>--run-now</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{os.path.expanduser('~/Library/Logs/buffettbot.log')}</string>
    <key>StandardErrorPath</key>
    <string>{os.path.expanduser('~/Library/Logs/buffettbot.error.log')}</string>
</dict>
</plist>

2. Load it:
   launchctl load ~/Library/LaunchAgents/com.buffettbot.scheduler.plist

3. To unload:
   launchctl unload ~/Library/LaunchAgents/com.buffettbot.scheduler.plist
"""
    print(plist)


def main():
    parser = argparse.ArgumentParser(
        description="Buffett Bot — automated full pipeline scheduler"
    )
    parser.add_argument(
        "--interval",
        choices=["15d", "daily", "weekly"],
        default="15d",
        help=(
            "15d: every 15 days (default, recommended for production). "
            "daily: Mon-Fri at 17:00 ET (for testing). "
            "weekly: every Monday at 08:00 ET (for testing)."
        ),
    )
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Run the full pipeline immediately before starting the schedule.",
    )
    parser.add_argument(
        "--launchd",
        action="store_true",
        help="Print macOS launchd plist for auto-start on login.",
    )
    args = parser.parse_args()

    script_path = os.path.abspath(__file__)

    if args.launchd:
        print_launchd_instructions(script_path)
        return

    logger.info("=" * 60)
    logger.info("Buffett Bot Scheduler — pipeline every 15 days")
    logger.info(f"Schedule: {args.interval}")
    logger.info(f"Watchlist at startup: {wl.load()}")
    logger.info("=" * 60)

    if args.run_now:
        logger.info("--run-now: executing pipeline immediately...")
        run_pipeline()

    scheduler = BlockingScheduler(timezone="America/New_York")

    if args.interval == "15d":
        trigger = IntervalTrigger(days=15)
        logger.info("Scheduled: every 15 days")
    elif args.interval == "daily":
        trigger = CronTrigger(
            day_of_week="mon-fri", hour=17, minute=0, timezone="America/New_York"
        )
        logger.info("Scheduled: Mon-Fri at 17:00 ET")
    else:  # weekly
        trigger = CronTrigger(
            day_of_week="mon", hour=8, minute=0, timezone="America/New_York"
        )
        logger.info("Scheduled: every Monday at 08:00 ET")

    scheduler.add_job(
        run_pipeline,
        trigger=trigger,
        id="buffett_pipeline",
        name="Buffett Full Pipeline",
        misfire_grace_time=3600,  # allow up to 1h late if machine was asleep
    )

    logger.info("Scheduler running. Press Ctrl+C to stop.")
    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
