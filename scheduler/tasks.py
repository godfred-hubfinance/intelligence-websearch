import logging
from pipeline.orchestrator import IntelligencePipeline

logger = logging.getLogger(__name__)

DEFAULT_SEARCH_QUERIES = [
    "multi-family office",
    "gestion de patrimoine",
    "family office acquisition",
    "family office nomination",
    "cabinet de gestion privée",
]


def run_scheduled_pipeline():
    """Background task to run Google News ingestion and Corporate Website crawls."""
    logger.info("⏰ [APScheduler] Starting scheduled intelligence scan...")
    pipeline = IntelligencePipeline()
    try:
        # 1. Run Google News ingestion
        news_events = pipeline.run(
            google_news_queries=DEFAULT_SEARCH_QUERIES,
            crawl_websites=False,
            limit_per_source=5,
        )
        logger.info(f"⏰ [APScheduler] Google News scan finished. Extracted {news_events} events.")

        # 2. Run Corporate Website crawl
        website_events = pipeline.run_company_website_crawl(max_articles_per_site=2)
        logger.info(f"⏰ [APScheduler] Website scan finished. Extracted {website_events} events.")

    except Exception as e:
        logger.error(f"❌ [APScheduler] Error during scheduled pipeline run: {e}", exc_info=True)
    finally:
        pipeline.close()