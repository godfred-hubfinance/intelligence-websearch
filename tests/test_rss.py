from collectors.rss_collector import RSSCollector

# Test feeds (e.g., Yahoo Finance Top News & TechCrunch)
test_feeds = [
    "https://finance.yahoo.com/news/rssindex",
    "https://techcrunch.com/feed/"
]

collector = RSSCollector(feed_urls=test_feeds)
documents = collector.fetch(limit=3)

print(f"\n--- Successfully collected {len(documents)} standard documents ---")
for idx, doc in enumerate(documents, start=1):
    print(f"\n[{idx}] Title: {doc.title}")
    print(f"    Source: {doc.source} ({doc.source_type})")
    print(f"    Published: {doc.published_at}")
    print(f"    URL: {doc.url}")
    print(f"    Content Snippet: {doc.content[:120]}...")