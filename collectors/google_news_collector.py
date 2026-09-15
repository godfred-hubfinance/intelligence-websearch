import logging
import urllib.parse
from datetime import datetime
from time import mktime
from typing import List, Optional
import feedparser
from bs4 import BeautifulSoup
from googlenewsdecoder import gnewsdecoder

from collectors.base import BaseCollector
from collectors.schemas import StandardDocument

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Keywords that disqualify personal notices from corporate intelligence
NEGATIVE_KEYWORDS = [
    "nécrologie", "necrologie", "avis de décès", "avis de deces", 
    "obituary", "décès de", "funérailles", "deuil"
]

class GoogleNewsCollector(BaseCollector):
    """Searches Google News RSS for specific company and executive mentions."""

    BASE_URL = "https://news.google.com/rss/search"

    def __init__(self, language: str = "fr", country: str = "FR"):
        super().__init__(name="google_news", source_type="news")
        self.language = language
        self.country = country

    def _clean_html(self, raw_html: str) -> str:
        if not raw_html:
            return ""
        soup = BeautifulSoup(raw_html, "html.parser")
        return soup.get_text(separator=" ", strip=True)

    def _parse_date(self, entry) -> Optional[datetime]:
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            return datetime.fromtimestamp(mktime(entry.published_parsed))
        return None

    def _resolve_url(self, google_url: str) -> str:
        """Decodes Google News tracking URL to direct publisher link."""
        try:
            res = gnewsdecoder(google_url, interval=0.5)
            if res.get("status"):
                return res.get("decoded_url")
        except Exception:
            pass
        return google_url

    def fetch(self, query: str = None, limit: int = 5) -> List[StandardDocument]:
        if not query:
            return []

        params = {
            "q": query,
            "hl": self.language,
            "gl": self.country,
            "ceid": f"{self.country}:{self.language}"
        }
        query_string = urllib.parse.urlencode(params)
        rss_url = f"{self.BASE_URL}?{query_string}"

        collected_docs: List[StandardDocument] = []
        try:
            logger.info(f"Querying Google News RSS for: '{query}'")
            parsed_feed = feedparser.parse(rss_url)

            for entry in parsed_feed.entries[:limit]:
                title = entry.get("title", "")
                raw_summary = entry.get("summary", "") or entry.get("description", "")
                clean_content = self._clean_html(raw_summary)

                # Skip obituaries / non-business personal notices
                combined_lower = f"{title} {clean_content}".lower()
                if any(neg in combined_lower for neg in NEGATIVE_KEYWORDS):
                    logger.info(f"Filtered out personal/necrology notice: {title}")
                    continue

                raw_link = entry.get("link", "")
                canonical_url = self._resolve_url(raw_link)

                doc = StandardDocument(
                    source=self.name,
                    source_type=self.source_type,
                    url=canonical_url,
                    title=title,
                    content=clean_content or title,
                    author=entry.get("source", {}).get("title", "Google News"),
                    published_at=self._parse_date(entry),
                    language=self.language,
                    metadata={"query": query, "original_source": entry.get("source", {}).get("title")}
                )
                collected_docs.append(doc)

        except Exception as e:
            logger.error(f"Error fetching Google News RSS for '{query}': {str(e)}")

        return collected_docs