import logging
from collectors.website_collector import WebsiteCollector

logging.basicConfig(level=logging.INFO)

def main():
    collector = WebsiteCollector()
    
    test_urls = [
        "https://www.flornoyferri.com",
        "https://www.cyrus-herez.fr",
    ]

    for url in test_urls:
        print(f"\n================ Crawling {url} ================")
        docs = collector.collect(url, max_articles=2)
        for doc in docs:
            print(f"Title: {doc.title}")
            print(f"URL: {doc.url}")
            print(f"Language: {doc.language}")
            print(f"Content Preview:\n{doc.content[:300]}...")
            print("-" * 50)

if __name__ == "__main__":
    main()