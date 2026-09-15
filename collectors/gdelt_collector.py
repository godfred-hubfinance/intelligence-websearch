import logging
import time
from datetime import datetime
from typing import List, Optional
import requests

from collectors.base import BaseCollector
from collectors.schemas import StandardDocument

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GDELTCollector(BaseCollector):
    """Connector for querying GDELT 2.0 with backoff and rate limit management."""

    GDELT_DOC_API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

    def __init__(self):
        super().__init__(name="gdelt", source_type="news")
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }

    def _parse_gdelt_date(self, date_str: Optional[str]) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y%m%d%H%M%S")
        except ValueError:
            return None

    def fetch(self, query: str = None, limit: int = 25) -> List[StandardDocument]:
        if not query:
            return []

        params = {
            "query": query,
            "mode": "artlist",
            "maxrecords": min(limit, 100),
            "format": "json",
            "sort": "datedesc"
        }

        collected_documents: List[StandardDocument] = []
        max_retries = 3
        backoff_seconds = 6

        for attempt in range(max_retries):
            try:
                # Minimum spacing between GDELT calls
                time.sleep(5)
                
                response = requests.get(
                    self.GDELT_DOC_API_URL, 
                    params=params, 
                    headers=self.headers, 
                    timeout=15
                )

                if response.status_code == 429:
                    logger.warning(f"GDELT Rate Limit (429). Backing off for {backoff_seconds}s (Attempt {attempt+1}/{max_retries})...")
                    time.sleep(backoff_seconds)
                    backoff_seconds *= 2
                    continue

                response.raise_for_status()

                try:
                    data = response.json()
                except ValueError:
                    return []

                articles = data.get("articles", [])
                for item in articles:
                    url = item.get("url", "")
                    if not url:
                        continue

                    published_dt = self._parse_gdelt_date(item.get("seendate"))
                    
                    doc = StandardDocument(
                        source=self.name,
                        source_type=self.source_type,
                        url=url,
                        title=item.get("title", "Untitled"),
                        content=item.get("title", ""),
                        author=item.get("domain", ""),
                        published_at=published_dt,
                        language=item.get("language", "en")[:2].lower() if item.get("language") else "en",
                        metadata={
                            "domain": item.get("domain"),
                            "sourcecountry": item.get("sourcecountry")
                        }
                    )
                    collected_documents.append(doc)
                
                # Successful fetch -> exit retry loop
                break

            except requests.RequestException as e:
                logger.error(f"Network error querying GDELT for '{query}': {str(e)}")
                break

        return collected_documents