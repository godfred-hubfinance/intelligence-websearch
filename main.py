from pipeline.orchestrator import IntelligencePipeline

if __name__ == "__main__":
    pipeline = IntelligencePipeline()
    
    # Configure feeds and queries
    rss_feeds = [
        "https://finance.yahoo.com/news/rssindex",
        "https://techcrunch.com/feed/"
    ]
    
    gdelt_queries = [
        '"Alpha Wealth"',
        '"Nexus HR"'
    ]

    try:
        pipeline.run(
            rss_feeds=rss_feeds,
            gdelt_queries=gdelt_queries,
            limit_per_source=10
        )
    finally:
        pipeline.close()