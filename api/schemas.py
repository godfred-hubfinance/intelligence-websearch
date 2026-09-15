from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field


# --- Document Schemas ---
class DocumentOut(BaseModel):
    id: int
    source: str
    source_type: str
    url: str
    title: str
    content: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    language: Optional[str] = None

    class Config:
        from_attributes = True


# --- Person Schemas ---
class PersonOut(BaseModel):
    id: int
    full_name: str
    role_title: Optional[str] = None
    linkedin_url: Optional[str] = None

    class Config:
        from_attributes = True


# --- Organisation Schemas ---
class OrganisationOut(BaseModel):
    id: int
    name: str
    country: Optional[str] = None
    city: Optional[str] = None
    website: Optional[str] = None
    event_count: Optional[int] = 0

    class Config:
        from_attributes = True


# --- Event Schemas ---
class EventListOut(BaseModel):
    id: int
    organisation_id: int
    organisation_name: str
    organisation_website: Optional[str] = None
    event_type: str
    event_date: Optional[date] = None
    summary: str
    location: Optional[str] = None
    sector: Optional[str] = None
    amount: Optional[str] = None
    confidence_score: Optional[float] = None
    created_at: Optional[datetime] = None
    sources_count: int = 0
    people: List[PersonOut] = []
    documents: List[DocumentOut] = []

    class Config:
        from_attributes = True


class EventDetailOut(BaseModel):
    id: int
    organisation_id: int
    organisation_name: str
    event_type: str
    event_date: Optional[date] = None
    summary: str
    location: Optional[str] = None
    sector: Optional[str] = None
    amount: Optional[str] = None
    confidence_score: Optional[float] = None
    created_at: datetime
    documents: List[DocumentOut] = []
    people: List[PersonOut] = []

    class Config:
        from_attributes = True


# --- Trigger Pipeline Request ---
class PipelineTriggerRequest(BaseModel):
    organisation_ids: Optional[List[int]] = Field(default=None, description="Specific org IDs to scan (default: all)")
    limit_per_source: int = Field(default=3, description="Max news articles to fetch per query")


class PaginatedEventsOut(BaseModel):
    items: List[EventListOut]
    total: int
    page: int
    page_size: int
    total_pages: int

