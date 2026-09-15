import logging
import urllib.parse
from datetime import datetime
from typing import List, Optional, Set
import requests
from bs4 import BeautifulSoup
import trafilatura
import urllib3

# Suppress insecure request warnings if a site has cert quirks
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from collectors.base import BaseCollector, StandardDocument

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Sec-Ch-Ua": '"Not-A.Brand";v="99", "Chromium";v="124"',
    "Sec-Ch-Ua-Platform": '"Windows"',
}

NEWS_KEYWORDS = [
    "actualite", "actualité", "news", "presse", "blog", "article",
    "publication", "nomination", "communique", "insights", "mag",
    "point-de-vue", "analyses", "evenement"
]


class WebsiteCollector(BaseCollector):
    """
    Crawls target MFO corporate websites for internal news, press releases,
    and appointments that third-party media outlets miss.
    """

    def __init__(self, timeout: int = 12):
        super().__init__(name="website", source_type="CORPORATE_WEBSITE")
        self.source_name = "Company Website"
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _safe_get(self, url: str) -> Optional[requests.Response]:
        """Tries request, falling back between www and apex domain if DNS/connection fails."""
        for target in [url, self._toggle_www(url)]:
            if not target:
                continue
            try:
                resp = self.session.get(target, timeout=self.timeout, allow_redirects=True, verify=False)
                if resp.status_code == 200:
                    return resp
            except Exception:
                continue
        return None

    def _toggle_www(self, url: str) -> Optional[str]:
        try:
            parsed = urllib.parse.urlparse(url)
            if "www." in parsed.netloc:
                netloc = parsed.netloc.replace("www.", "")
            else:
                netloc = "www." + parsed.netloc
            return urllib.parse.urlunparse(parsed._replace(netloc=netloc))
        except Exception:
            return None

    def _discover_article_urls(self, base_url: str, max_links: int = 5) -> Set[str]:
        """Scans the homepage navigation to dynamically find news/article links."""
        discovered: Set[str] = set()
        resp = self._safe_get(base_url)
        if not resp or "text/html" not in resp.headers.get("Content-Type", ""):
            return discovered

        parsed_base = urllib.parse.urlparse(base_url)
        base_domain = parsed_base.netloc.lower().replace("www.", "")

        soup = BeautifulSoup(resp.text, "lxml")

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            full_url = urllib.parse.urljoin(base_url, href)
            parsed_link = urllib.parse.urlparse(full_url)
            link_domain = parsed_link.netloc.lower().replace("www.", "")

            # Check if internal domain
            if base_domain in link_domain and full_url != base_url:
                # Avoid non-content extensions
                if any(ext in parsed_link.path.lower() for ext in [".pdf", ".png", ".jpg", ".jpeg", ".zip", "mailto:", "tel:"]):
                    continue

                path_lower = (parsed_link.path + " " + a.get_text()).lower()
                if any(k in path_lower for k in NEWS_KEYWORDS):
                    discovered.add(full_url)

            if len(discovered) >= max_links:
                break

        return discovered

    def _extract_page_content(self, url: str) -> Optional[StandardDocument]:
        """Extracts clean body text, title, and metadata with dual extraction fallback."""
        try:
            resp = self._safe_get(url)
            if not resp or resp.status_code != 200:
                return None

            html = resp.text
            
            # Primary: Trafilatura (cleans boilerplate)
            extracted_text = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=False,
                no_fallback=False
            )

            soup = BeautifulSoup(html, "lxml")
            
            # Secondary fallback: Direct text parsing if trafilatura stripped too much
            if not extracted_text or len(extracted_text.strip()) < 80:
                # Remove scripts and style elements
                for element in soup(["script", "style", "nav", "footer", "header", "noscript"]):
                    element.extract()
                extracted_text = " ".join(soup.stripped_strings)

            if not extracted_text or len(extracted_text.strip()) < 80:
                return None

            # Extract Title
            metadata = trafilatura.extract_metadata(html)
            title = metadata.title if metadata and metadata.title else None
            if not title:
                title_tag = soup.find("h1") or soup.find("title")
                title = title_tag.get_text().strip() if title_tag else "Corporate Update"

            # Clean trailing boilerplate from title if present
            title = title.split(" - ")[0].split(" | ")[0].strip()

            pub_date = None
            if metadata and metadata.date:
                try:
                    pub_date = datetime.fromisoformat(metadata.date)
                except Exception:
                    pub_date = None

            return StandardDocument(
                source=self.source_name,
                source_type=self.source_type,
                url=url,
                title=title,
                content=extracted_text,
                author=metadata.author if metadata else None,
                published_at=pub_date or datetime.utcnow(),
                language=metadata.language if metadata and metadata.language else "fr"
            )

        except Exception as e:
            logger.warning(f"Error extracting content from {url}: {e}")
            return None

    def fetch(self, query: str = "", limit: int = 3, **kwargs) -> List[StandardDocument]:
        """Implements BaseCollector.fetch()."""
        website_url = kwargs.get("website_url") or query
        return self.collect(website_url=website_url, max_articles=limit)

    def collect(self, website_url: str, max_articles: int = 3) -> List[StandardDocument]:
        """Main collection entry point for a single company website."""
        if not website_url or not website_url.startswith("http"):
            return []

        logger.info(f"Crawling corporate website: {website_url}")
        article_urls = self._discover_article_urls(website_url, max_links=max_articles)

        # Fallback to crawling homepage if no specific news link found
        if not article_urls:
            article_urls = {website_url}

        documents: List[StandardDocument] = []
        for url in article_urls:
            doc = self._extract_page_content(url)
            if doc:
                documents.append(doc)

        logger.info(f"Extracted {len(documents)} document(s) from {website_url}")
        return documents