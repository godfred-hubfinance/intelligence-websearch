from sqlalchemy import (
    Column, Integer, String, Text, Float, Numeric, Date,
    DateTime, ForeignKey, Table, func
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import relationship
from database.connection import Base

# Junction Table: Event <-> Document
event_documents = Table(
    "event_documents",
    Base.metadata,
    Column("event_id", Integer, ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
    Column("document_id", Integer, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
)

# Junction Table: Event <-> People[cite: 1]
event_people = Table(
    "event_people",
    Base.metadata,
    Column("event_id", Integer, ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
    Column("person_id", Integer, ForeignKey("people.id", ondelete="CASCADE"), primary_key=True)
)


class Organisation(Base):
    __tablename__ = "organisations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    alternative_names = Column(ARRAY(Text), default=[])
    website = Column(String(255))
    country = Column(String(100))
    city = Column(String(100))
    linkedin_url = Column(String(255))
    organisation_type = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships[cite: 1]
    people = relationship("Person", back_populates="organisation", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="organisation")


class Person(Base):
    __tablename__ = "people"

    id = Column(Integer, primary_key=True, index=True)
    organisation_id = Column(Integer, ForeignKey("organisations.id", ondelete="CASCADE"))
    full_name = Column(String(255), nullable=False)
    role = Column(String(255))
    linkedin_url = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships[cite: 1]
    organisation = relationship("Organisation", back_populates="people")
    events = relationship("Event", secondary=event_people, back_populates="people")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(50), nullable=False)        # 'gdelt', 'rss', 'newsapi'[cite: 1]
    source_type = Column(String(50), nullable=False)   # 'news', 'press_release'[cite: 1]
    url = Column(Text, unique=True, nullable=False)
    title = Column(Text, nullable=False)
    content = Column(Text)
    author = Column(String(255))
    language = Column(String(10))
    published_at = Column(DateTime(timezone=True))
    collected_at = Column(DateTime(timezone=True), server_default=func.now())
    metadata_json = Column("metadata", JSONB, default={})

    # Relationships[cite: 1]
    events = relationship("Event", secondary=event_documents, back_populates="documents")


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    organisation_id = Column(Integer, ForeignKey("organisations.id", ondelete="SET NULL"), nullable=True)
    event_type = Column(String(100), nullable=False)
    event_date = Column(Date)
    summary = Column(Text, nullable=False)
    location = Column(String(255))
    sector = Column(String(255))
    amount = Column(Numeric(15, 2), nullable=True)
    confidence_score = Column(Float, default=1.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships[cite: 1]
    organisation = relationship("Organisation", back_populates="events")
    documents = relationship("Document", secondary=event_documents, back_populates="events")
    people = relationship("Person", secondary=event_people, back_populates="events")