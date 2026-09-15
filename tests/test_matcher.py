from collectors.schemas import StandardDocument
from pipeline.matcher import EntityMatcher

# 1. Mock Target List (simulating your 500 DB dataset)
target_orgs = [
    {
        "id": 1,
        "name": "Alpha Wealth Partners",
        "alternative_names": ["Alpha Wealth", "AWP"],
        "website": "https://alphawealth.com",
        "people": ["Jane Doe", "Marc Weber"]
    },
    {
        "id": 2,
        "name": "Nexus HR Solutions",
        "alternative_names": ["Nexus HR"],
        "website": "https://nexushr.io",
        "people": ["Claire Dupont"]
    }
]

matcher = EntityMatcher(target_organisations=target_orgs)

# 2. Test Cases
docs_to_test = [
    StandardDocument(
        source="gdelt",
        source_type="news",
        url="https://news.lu/alpha-wealth-ceo",
        title="Alpha Wealth Partners Appoints Jane Doe as New CEO",
        content="Alpha Wealth announced strategic growth in Luxembourg."
    ),
    StandardDocument(
        source="rss",
        source_type="news",
        url="https://techcrunch.com/other-news",
        title="Global Markets Slide Amid Tech Selloff",
        content="General market updates with no specific company mentions."
    )
]

print("--- Testing Entity Matching & Relevance Filtering ---")
for idx, doc in enumerate(docs_to_test, start=1):
    result = matcher.match(doc)
    print(f"\nDocument [{idx}]: {doc.title}")
    if result:
        print(f"  --> MATCH FOUND: Org ID {result['organisation_id']} ({result['organisation_name']})")
        print(f"      Confidence Score: {result['confidence_score']}")
        print(f"      Matched Terms: {result['matched_terms']}")
    else:
        print("  --> NO MATCH (Filtered out cleanly without LLM invocation)")