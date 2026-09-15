import os
from collectors.schemas import StandardDocument
from pipeline.extractor import EventExtractor

# Mock relevant document passing through matcher
doc = StandardDocument(
    source="newsapi",
    source_type="news",
    url="https://techcrunch.com/2026/08/18/nexus-hr-raises-series-a",
    title="Paris-based Nexus HR Solutions secures €12M Series A",
    content="Nexus HR Solutions has completed a €12M Series A funding round to scale its automated workforce planning engine. The round was led by European Tech Ventures, with participation from existing angels.",
    language="en"
)

extractor = EventExtractor()
extracted_data = extractor.extract(document=doc, matched_org_name="Nexus HR Solutions")

if extracted_data:
    print("\n--- Successfully Extracted Structured Event ---")
    print(f"Organisation : {extracted_data.organisation}")
    print(f"Event Type   : {extracted_data.event_type}")
    print(f"Summary      : {extracted_data.summary}")
    print(f"Amount       : €{extracted_data.amount:,.2f}" if extracted_data.amount else "Amount       : None")
    print(f"Location     : {extracted_data.location}")
    print(f"Confidence   : {extracted_data.confidence}")
else:
    print("Extraction failed or API key missing.")