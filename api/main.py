import io
import os
import math
import datetime
import pandas as pd
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from datetime import date
from typing import List, Optional
from fastapi import FastAPI, Depends, Query, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from database.models import Event, Organisation
from database.connection import get_db, SessionLocal
from database.models import Organisation, Event, Document, Person
from api.schemas import (
    DocumentOut,
    EventListOut,
    EventDetailOut,
    OrganisationOut,
    PaginatedEventsOut,
    PaginatedEventsOut,
    PersonOut,
    PipelineTriggerRequest
)
from pipeline.orchestrator import IntelligencePipeline

from contextlib import asynccontextmanager
from scheduler.scheduler import start_scheduler, shutdown_scheduler, scheduler, run_scheduled_pipeline
from fastapi import BackgroundTasks

app = FastAPI(
    title="Market Intelligence Engine API",
    version="1.0.0",
    description="REST API for querying structured events and triggering intelligence pipelines on European Multi-Family Offices."
)

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    os.getenv("FRONTEND_URL"),
     "https://intelligencesearch.vercel.app",
]

origins = [origin for origin in origins if origin]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Health & Metadata ---
@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok", "service": "intelligence-engine"}


# --- Organisations ---
@app.get("/organisations", response_model=List[OrganisationOut], tags=["Organisations"])
def list_organisations(
    country: Optional[str] = Query(None, description="Filter by country (e.g. France, Luxembourg, Belgium)"),
    db: Session = Depends(get_db)
):
    """List all monitored family offices along with their extracted event count."""
    query = db.query(
        Organisation.id,
        Organisation.name,
        Organisation.country,
        Organisation.city,
        Organisation.website,
        func.count(Event.id).label("event_count")
    ).outerjoin(Event, Organisation.id == Event.organisation_id)

    if country:
        query = query.filter(Organisation.country.ilike(f"%{country}%"))

    results = query.group_by(Organisation.id).order_by(Organisation.name.asc()).all()

    return [
        OrganisationOut(
            id=r.id,
            name=r.name,
            country=r.country,
            city=r.city,
            website=r.website,
            event_count=r.event_count
        )
        for r in results
    ]


# --- Events ---
@app.get("/events", response_model=PaginatedEventsOut, tags=["Events"])
def list_events(
    organisation_id: Optional[int] = Query(None, description="Filter by organisation ID"),
    organisation_name: Optional[str] = Query(None, description="Search by organisation name"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    page: int = Query(1, ge=1, description="Page number (starts at 1)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    query = (
        db.query(Event)
        .options(joinedload(Event.documents), joinedload(Event.people), joinedload(Event.organisation))
        .join(Organisation)
    )

    if organisation_id:
        query = query.filter(Event.organisation_id == organisation_id)
    if organisation_name and organisation_name.strip():
        query = query.filter(Organisation.name.ilike(f"%{organisation_name.strip()}%"))
    if event_type and event_type.strip():
        query = query.filter(Event.event_type.ilike(f"%{event_type.strip()}%"))
    if min_confidence > 0.0:
        query = query.filter(Event.confidence_score >= min_confidence)
    if start_date:
        query = query.filter(Event.event_date >= start_date)
    if end_date:
        query = query.filter(Event.event_date <= end_date)

    total = query.count()
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    offset = (page - 1) * page_size

    events = (
        query.order_by(Event.event_date.desc().nullslast(), Event.id.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    items = [
        EventListOut(
            id=e.id,
            organisation_id=e.organisation_id,
            organisation_name=e.organisation.name,
            organisation_website=e.organisation.website,
            event_type=e.event_type,
            event_date=e.event_date,
            summary=e.summary,
            location=e.location,
            sector=e.sector,
            amount=str(e.amount) if e.amount is not None else None,
            confidence_score=e.confidence_score,
            created_at=e.created_at,
            sources_count=len(e.documents),
            people=[
                PersonOut(
                    id=p.id,
                    full_name=p.full_name,
                    role_title=getattr(p, "role_title", getattr(p, "role", None)),
                    linkedin_url=getattr(p, "linkedin_url", None),
                )
                for p in e.people
            ],
            documents=[
                DocumentOut(
                    id=d.id,
                    title=d.title,
                    url=d.url,
                    source=d.source,
                    source_type=d.source_type,
                    published_at=d.published_at,
                )
                for d in e.documents
                if d.url
            ],
        )
        for e in events
    ]

    return PaginatedEventsOut(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )

@app.get("/events/export", tags=["Events"])
def export_events(
    format: str = Query("csv", description="Export file format ('csv' or 'xlsx')"),
    organisation_id: Optional[int] = Query(None, description="Filter by organisation ID"),
    organisation_name: Optional[str] = Query(None, description="Search by organisation name"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    min_confidence: float = Query(0.0, description="Minimum confidence score"),
    start_date: Optional[str] = Query(None, description="Filter events on or after YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Filter events on or before YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    """Export filtered intelligence events to a downloadable CSV or Excel (.xlsx) file."""
    format_clean = (format or "csv").lower().strip()
    if format_clean not in ["csv", "xlsx"]:
        raise HTTPException(status_code=400, detail="Invalid format. Use 'csv' or 'xlsx'.")

    query = db.query(Event).join(Organisation)

    if organisation_id:
        query = query.filter(Event.organisation_id == organisation_id)
    if organisation_name:
        query = query.filter(Organisation.name.ilike(f"%{organisation_name.strip()}%"))
    if event_type:
        query = query.filter(Event.event_type.ilike(f"%{event_type.strip()}%"))
    if min_confidence and min_confidence > 0.0:
        query = query.filter(Event.confidence_score >= min_confidence)

    # Safely parse dates if provided
    if start_date and start_date.strip():
        try:
            parsed_start = datetime.strptime(start_date.strip(), "%Y-%m-%d").date()
            query = query.filter(Event.event_date >= parsed_start)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD.")

    if end_date and end_date.strip():
        try:
            parsed_end = datetime.strptime(end_date.strip(), "%Y-%m-%d").date()
            query = query.filter(Event.event_date <= parsed_end)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD.")

    events = query.order_by(Event.event_date.desc().nullslast(), Event.id.desc()).all()

    # Flatten data for tabular presentation
    rows = []
    for e in events:
        source_urls = " | ".join([d.url for d in e.documents if d.url])
        people_names = ", ".join([p.full_name for p in e.people if p.full_name])
        
        rows.append({
            "Event ID": e.id,
            "Organisation": e.organisation.name,
            "Country": e.organisation.country or "",
            "City": e.organisation.city or "",
            "Event Type": e.event_type,
            "Event Date": e.event_date.strftime("%Y-%m-%d") if e.event_date else "",
            "Summary": e.summary,
            "Location": e.location or "",
            "Sector": e.sector or "",
            "Amount": str(e.amount) if e.amount is not None else "",
            "Confidence Score": e.confidence_score,
            "Mentioned People": people_names,
            "Source URLs": source_urls,
            "Extracted At": e.created_at.strftime("%Y-%m-%d %H:%M:%S") if e.created_at else ""
        })

    df = pd.DataFrame(rows)

    # Stream CSV
    if format_clean == "csv":
        stream = io.StringIO()
        df.to_csv(stream, index=False, encoding="utf-8-sig")
        stream.seek(0)
        
        return StreamingResponse(
            iter([stream.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=market_intelligence_events.csv"}
        )

    # Stream Excel (.xlsx)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Events")
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=market_intelligence_events.xlsx"}
    )


@app.get("/events/{event_id}", response_model=EventDetailOut, tags=["Events"])
def get_event_detail(event_id: int, db: Session = Depends(get_db)):
    """Fetch complete event payload including linked source documents and mentioned people."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return EventDetailOut(
        id=event.id,
        organisation_id=event.organisation_id,
        organisation_name=event.organisation.name,
        event_type=event.event_type,
        event_date=event.event_date,
        summary=event.summary,
        location=event.location,
        sector=event.sector,
        amount=event.amount,
        confidence_score=event.confidence_score,
        created_at=event.created_at,
        documents=event.documents,
        people=event.people
    )


# --- Pipeline Trigger ---
def _run_pipeline_task(org_ids: Optional[List[int]], limit_per_source: int):
    """Background worker function for asynchronous pipeline runs."""
    db = SessionLocal()
    query = db.query(Organisation.name)
    if org_ids:
        query = query.filter(Organisation.id.in_(org_ids))
    org_names = [o.name for o in query.all()]
    db.close()

    if not org_names:
        return

    queries = [f'"{name}"' for name in org_names]
    pipeline = IntelligencePipeline()
    try:
        pipeline.run(google_news_queries=queries, limit_per_source=limit_per_source)
    finally:
        pipeline.close()


@app.post("/pipeline/trigger", tags=["Pipeline"])
def trigger_pipeline(
    payload: PipelineTriggerRequest,
    background_tasks: BackgroundTasks
):
    """Trigger an on-demand extraction run in the background without blocking the API."""
    background_tasks.add_task(_run_pipeline_task, payload.organisation_ids, payload.limit_per_source)
    return {
        "status": "queued",
        "message": "Intelligence pipeline triggered in the background.",
        "target_organisations_count": len(payload.organisation_ids) if payload.organisation_ids else "all"
    }

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    start_scheduler()
    yield
    # Shutdown
    shutdown_scheduler()


@app.get("/scheduler/status", tags=["Scheduler"])
def get_scheduler_status():
    """Check the running status and next execution times of scheduled jobs."""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger)
        })
    return {
        "scheduler_running": scheduler.running,
        "scheduled_jobs": jobs
    }


@app.post("/scheduler/run-now", tags=["Scheduler"])
def trigger_pipeline_now(background_tasks: BackgroundTasks):
    """Manually trigger the full intelligence scan immediately in the background."""
    background_tasks.add_task(run_scheduled_pipeline)
    return {"message": "Intelligence pipeline execution triggered in the background."}
