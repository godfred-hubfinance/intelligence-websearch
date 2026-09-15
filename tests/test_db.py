from database.connection import SessionLocal
from database.models import Organisation, Event

db = SessionLocal()

print("--- Testing Database Read ---")
orgs = db.query(Organisation).all()
for org in orgs:
    print(f"ID: {org.id} | Org: {org.name} | Type: {org.organisation_type}")

events = db.query(Event).all()
for event in events:
    print(f"Event ID: {event.id} | Type: {event.event_type} | Org ID: {event.organisation_id}")

db.close()