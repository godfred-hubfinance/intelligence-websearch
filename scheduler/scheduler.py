import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from scheduler.tasks import run_scheduled_pipeline

logger = logging.getLogger(__name__)

# Configure scheduler with resilient defaults
scheduler = BackgroundScheduler(
    timezone="UTC",
    job_defaults={
        "coalesce": True,            # Combine missed runs into a single execution
        "misfire_grace_time": 3600,   # Allow execution if within 60 mins of scheduled time
        "max_instances": 1,           # Prevent overlapping duplicate scans
    },
)


def start_scheduler():
    """Initializes and starts the non-blocking background scheduler."""
    if not scheduler.running:
        # Schedule daily run at 06:00 UTC
        scheduler.add_job(
            run_scheduled_pipeline,
            trigger=CronTrigger(hour=6, minute=0),
            id="daily_intelligence_scan",
            name="Daily Google News & Website Scan",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        scheduler.start()
        logger.info(
            "🚀 [APScheduler] Background scheduler started (Daily at 06:00 UTC, grace=60m)."
        )


def shutdown_scheduler():
    """Gracefully shuts down the background scheduler on server stop."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("🛑 [APScheduler] Background scheduler shut down.")