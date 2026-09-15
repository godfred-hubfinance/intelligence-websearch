import logging
from datetime import datetime
from time import mktime
from typing import List, Optional
import feedparser
from bs4 import BeautifulSoup

from collectors.base import BaseCollector
from collectors.schemas import StandardDocument

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RSSCollector(BaseCollector):
    """Connector for polling public RSS/Atom feeds."""

    def __init__(self, feed_urls: Optional[List[str]] = None):
        super().__init__(name="rss", source_type="news")
        self.feed_urls = feed_urls or []

    def add_feed_url(self, url: str) -> None:
        if url not in self.feed_urls:
            self.feed_urls.append(url)

    def _clean_html(self, raw_html: str) -> str:
        """Strips HTML tags to extract clean body text."""
        if not raw_html:
            return ""
        soup = BeautifulSoup(raw_html, "html.parser")
        return soup.get_text(separator=" ", strip=True)

    def _parse_published_date(self, entry: feedparser.FeedParserDict) -> Optional[datetime]:
        """Extracts publication timestamp across varied feed specs."""
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            return datetime.fromtimestamp(mktime(entry.published_parsed))
        if hasattr(entry, "updated_parsed") and entry.updated_parsed:
            return datetime.fromtimestamp(mktime(entry.updated_parsed))
        return None

    def fetch(self, query: str = None, limit: int = 50) -> List[StandardDocument]:
        """
        Parses all configured RSS feeds and returns standardized documents.
        Catches errors per feed so one failing URL doesn't stop ingestion.
        """
        collected_documents: List[StandardDocument] = []

        for feed_url in self.feed_urls:
            try:
                logger.info(f"Fetching RSS feed: {feed_url}")
                parsed_feed = feedparser.parse(feed_url)

                if parsed_feed.bozo and not parsed_feed.entries:
                    logger.warning(f"Failed to parse or empty feed: {feed_url}")
                    continue

                for entry in parsed_feed.entries[:limit]:
                    raw_summary = entry.get("summary", "") or entry.get("description", "")
                    clean_content = self._clean_html(raw_summary)
                    published_dt = self._parse_published_date(entry)

                    doc = StandardDocument(
                        source=self.name,
                        source_type=self.source_type,
                        url=entry.get("link", ""),
                        title=entry.get("title", "Untitled"),
                        content=clean_content,
                        author=entry.get("author", parsed_feed.feed.get("title")),
                        published_at=published_dt,
                        language=parsed_feed.feed.get("language", "en")[:2] if parsed_feed.feed.get("language") else "en",
                        metadata={
                            "feed_url": feed_url,
                            "tags": [tag.term for tag in entry.get("tags", [])] if "tags" in entry else []
                        }
                    )
                    collected_documents.append(doc)

            except Exception as e:
                logger.error(f"Error fetching RSS feed '{feed_url}': {str(e)}")

        return collected_documents