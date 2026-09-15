from collectors.schemas import StandardDocument
from pipeline.deduplicator import Deduplicator

dedup_engine = Deduplicator(title_similarity_threshold=80)

# Simulated existing articles already stored in DB
stored_documents = [
    {
        "id": 101,
        "url": "https://alphawealth.com/press/leadership-update",
        "title": "Alpha Wealth Partners Appoints Jane Doe as New CEO in Luxembourg"
    }
]

# Ingesting two new incoming articles
incoming_docs = [
    # Case A: Syndicated news with slightly different headline
    StandardDocument(
        source="gdelt",
        source_type="news",
        url="https://financenews.lu/alpha-wealth-ceo-update",
        title="Alpha Wealth Partners Appoints Jane Doe New CEO",
        content="Alpha Wealth Partners announced Jane Doe..."
    ),
    # Case B: Completely different article
    StandardDocument(
        source="rss",
        source_type="news",
        url="https://techcrunch.com/funding-round",
        title="Nexus HR Solutions Secures Series A Funding",
        content="Nexus HR closed a round..."
    )
]

print("--- Testing Document Deduplication Engine ---")
for idx, doc in enumerate(incoming_docs, start=1):
    duplicate_match = dedup_engine.is_duplicate(doc, stored_documents)
    print(f"\nIncoming Doc [{idx}]: {doc.title}")
    if duplicate_match:
        print(f"  --> DUPLICATE DETECTED: Clusters with Doc ID {duplicate_match['matched_id']}")
        print(f"      Detection Reason: {duplicate_match['reason']} (Score: {duplicate_match['similarity_score']}%)")
    else:
        print("  --> UNIQUE DOCUMENT: Create new distinct document/event entry.")