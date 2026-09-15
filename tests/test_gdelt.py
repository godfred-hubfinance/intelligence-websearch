from collectors.gdelt_collector import GDELTCollector

collector = GDELTCollector()

# Query for wealth management news in Luxembourg
query = '"wealth management" luxembourg'
documents = collector.fetch(query=query, limit=3)

print(f"\n--- Successfully collected {len(documents)} standard documents from GDELT ---")
for idx, doc in enumerate(documents, start=1):
    print(f"\n[{idx}] Title: {doc.title}")
    print(f"    Source: {doc.source} ({doc.source_type})")
    print(f"    Domain: {doc.author}")
    print(f"    Published: {doc.published_at}")
    print(f"    URL: {doc.url}")