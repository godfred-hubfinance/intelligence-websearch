import time
from database.connection import SessionLocal
from database.models import Organisation
from pipeline.orchestrator import IntelligencePipeline

def run_all_organisations():
    db = SessionLocal()
    orgs = db.query(Organisation.name).all()
    org_names = [o.name for o in orgs if o.name]
    db.close()

    print(f"--- Monitoring {len(org_names)} Family Offices ---")

    pipeline = IntelligencePipeline()
    
    # Process in batches of 15 to manage network throughput cleanly
    batch_size = 15
    try:
        for i in range(0, len(org_names), batch_size):
            batch = org_names[i : i + batch_size]
            queries = [f'"{name}"' for name in batch]
            print(f"\nProcessing Batch {i // batch_size + 1} ({len(batch)} companies)...")
            
            pipeline.run(
                google_news_queries=queries,
                limit_per_source=3
            )
            time.sleep(2)
    finally:
        pipeline.close()

if __name__ == "__main__":
    run_all_organisations()