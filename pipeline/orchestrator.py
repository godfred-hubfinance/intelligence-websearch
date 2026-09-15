import logging
from typing import List, Optional
from datetime import datetime

from database.connection import SessionLocal
from database.models import Organisation, Document, Event, Person
from collectors.rss_collector import RSSCollector
from collectors.gdelt_collector import GDELTCollector
from collectors.google_news_collector import GoogleNewsCollector
from collectors.website_collector import WebsiteCollector
from pipeline.matcher import EntityMatcher
from pipeline.deduplicator import Deduplicator
from pipeline.extractor import EventExtractor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class IntelligencePipeline:
    """End-to-end orchestration pipeline for collection, filtering, extraction, and persistence."""

    def __init__(self):
        self.db = SessionLocal()
        self.extractor = EventExtractor()
        self.deduplicator = Deduplicator(title_similarity_threshold=80)
        self.website_collector = WebsiteCollector()
        self._load_targets()

    def _load_targets(self):
        """Loads monitored organisations and key people from PostgreSQL into the EntityMatcher."""
        orgs = self.db.query(Organisation).all()
        self.target_organisations = []
        for org in orgs:
            people_names = [p.full_name for p in org.people]
            self.target_organisations.append({
                "id": org.id,
                "name": org.name,
                "alternative_names": org.alternative_names or [],
                "website": org.website or "",
                "people": people_names
            })
        self.matcher = EntityMatcher(target_organisations=self.target_organisations)
        logger.info(f"Loaded {len(self.target_organisations)} target organisations into matcher.")

    def run_company_website_crawl(self, org_ids: Optional[List[int]] = None, max_articles_per_site: int = 2):
        """Crawls official websites of target organisations stored in DB."""
        query = self.db.query(Organisation).filter(Organisation.website.isnot(None))
        if org_ids:
            query = query.filter(Organisation.id.in_(org_ids))
        
        organisations = query.all()
        logger.info(f"Starting corporate website crawl for {len(organisations)} organisations...")

        raw_docs = []
        for org in organisations:
            if not org.website:
                continue
            try:
                docs = self.website_collector.collect(org.website, max_articles=max_articles_per_site)
                raw_docs.extend(docs)
            except Exception as e:
                logger.warning(f"Failed crawling website for {org.name} ({org.website}): {e}")

        logger.info(f"Total website documents collected: {len(raw_docs)}")
        return self._process_documents(raw_docs)

    def run(
        self,
        rss_feeds: Optional[List[str]] = None,
        google_news_queries: Optional[List[str]] = None,
        gdelt_queries: Optional[List[str]] = None,
        crawl_websites: bool = False,
        limit_per_source: int = 10
    ):
        """Executes the ingestion, entity matching, deduplication, AI extraction, and DB persistence loop."""
        logger.info("--- Starting Pipeline Run ---")
        raw_docs = []

        # 1. Ingestion Phase
        if rss_feeds:
            rss_collector = RSSCollector(feed_urls=rss_feeds)
            raw_docs.extend(rss_collector.fetch(limit=limit_per_source))

        if google_news_queries:
            gnews_collector = GoogleNewsCollector(language="fr", country="FR")
            for query in google_news_queries:
                raw_docs.extend(gnews_collector.fetch(query=query, limit=limit_per_source))

        if gdelt_queries:
            gdelt_collector = GDELTCollector()
            for query in gdelt_queries:
                raw_docs.extend(gdelt_collector.fetch(query=query, limit=limit_per_source))

        if crawl_websites:
            for org in self.target_organisations:
                if org.get("website"):
                    try:
                        docs = self.website_collector.collect(org["website"], max_articles=limit_per_source)
                        raw_docs.extend(docs)
                    except Exception as e:
                        logger.warning(f"Website crawl error for {org['name']}: {e}")

        logger.info(f"Collected {len(raw_docs)} total raw documents across all sources.")
        return self._process_documents(raw_docs)

    def _process_documents(self, raw_docs):
        """Processes collected documents: match -> deduplicate -> extract -> persist."""
        # Cache existing stored documents for title/URL deduplication
        existing_docs = [
            {"id": d.id, "url": d.url, "title": d.title}
            for d in self.db.query(Document.id, Document.url, Document.title).all()
        ]

        saved_events_count = 0

        # 2. Processing Phase
        for doc in raw_docs:
            # Step A: Deterministic Filtering & Relevance Matching
            match_result = self.matcher.match(doc)
            if not match_result:
                continue

            logger.info(f"Match found for '{match_result['organisation_name']}' in: {doc.title}")

            # Step B: Deduplication
            duplicate_info = self.deduplicator.is_duplicate(doc, existing_docs)
            if duplicate_info:
                logger.info(
                    f"Document is duplicate of Doc ID {duplicate_info['matched_id']} "
                    f"({duplicate_info['reason']}). Skipping."
                )
                continue

            # Step C: AI Event Extraction & Taxonomy Classification
            extracted_event = self.extractor.extract(doc, match_result["organisation_name"])
            if not extracted_event:
                continue

            # Step D: Relational Database Persistence
            try:
                # 1. Insert Document
                db_doc = Document(
                    source=doc.source,
                    source_type=doc.source_type,
                    url=doc.url,
                    title=doc.title,
                    content=doc.content,
                    author=doc.author,
                    language=doc.language,
                    published_at=doc.published_at,
                    metadata_json=doc.metadata
                )
                self.db.add(db_doc)
                self.db.flush()

                # 2. Parse Event Date
                event_date = None
                if extracted_event.event_date:
                    try:
                        event_date = datetime.strptime(extracted_event.event_date, "%Y-%m-%d").date()
                    except ValueError:
                        pass

                # 3. Insert Event
                db_event = Event(
                    organisation_id=match_result["organisation_id"],
                    event_type=extracted_event.event_type,
                    event_date=event_date or (doc.published_at.date() if doc.published_at else None),
                    summary=extracted_event.summary,
                    location=extracted_event.location,
                    sector=extracted_event.sector,
                    amount=extracted_event.amount,
                    confidence_score=extracted_event.confidence
                )
                self.db.add(db_event)
                self.db.flush()

                # 4. Link Junction Tables
                db_event.documents.append(db_doc)

                for person_name in extracted_event.people:
                    person = self.db.query(Person).filter(
                        Person.organisation_id == match_result["organisation_id"],
                        Person.full_name.ilike(f"%{person_name}%")
                    ).first()
                    if person:
                        db_event.people.append(person)

                self.db.commit()

                # Update in-memory dedup cache
                existing_docs.append({"id": db_doc.id, "url": db_doc.url, "title": db_doc.title})
                saved_events_count += 1
                logger.info(
                    f"Saved Event ID {db_event.id}: [{extracted_event.event_type}] "
                    f"{extracted_event.summary[:70]}..."
                )

            except Exception as e:
                self.db.rollback()
                logger.error(f"Failed to persist event to database: {str(e)}")

        logger.info(f"--- Pipeline Finished. Saved {saved_events_count} new events to database. ---")
        return saved_events_count

    def close(self):
        """Closes the active database session."""
        self.db.close()