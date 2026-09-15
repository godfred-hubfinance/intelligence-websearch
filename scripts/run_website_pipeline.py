import logging
from pipeline.orchestrator import IntelligencePipeline

logging.basicConfig(level=logging.INFO)

def main():
    pipeline = IntelligencePipeline()
    try:
        # Crawl websites for all stored MFOs (1-2 articles per site)
        events_created = pipeline.run_company_website_crawl(max_articles_per_site=2)
        print(f"\nSuccessfully created {events_created} new event(s) from corporate websites.")
    finally:
        pipeline.close()

if __name__ == "__main__":
    main()