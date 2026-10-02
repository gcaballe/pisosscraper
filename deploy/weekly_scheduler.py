import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORTALS = ("habitaclia", "fotocasa", "idealista", "yaencontre")


def seconds_until_next_run():
    now = datetime.now(timezone.utc)
    days_until_sunday = (6 - now.weekday()) % 7
    next_run = (now + timedelta(days=days_until_sunday)).replace(
        hour=3, minute=0, second=0, microsecond=0
    )
    if next_run <= now:
        next_run += timedelta(days=7)
    return (next_run - now).total_seconds(), next_run


while True:
    delay, next_run = seconds_until_next_run()
    print(f"Next weekly scrape: {next_run.isoformat()}", flush=True)
    time.sleep(delay)

    for index, portal in enumerate(PORTALS):
        print(f"Starting {portal} scrape", flush=True)
        result = subprocess.run(
            [sys.executable, "run.py", portal, "--db"],
            cwd=ROOT,
            check=False,
        )
        print(f"{portal} exited with status {result.returncode}", flush=True)
        if index < len(PORTALS) - 1:
            time.sleep(15 * 60)
