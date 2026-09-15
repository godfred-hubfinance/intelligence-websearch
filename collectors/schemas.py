from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, HttpUrl

class StandardDocument(BaseModel):
    """Common internal document format across all connectors."""
    source: str = Field(..., description="Source name, e.g., 'gdelt', 'rss', 'newsapi'")
    source_type: str = Field(..., description="Source classification, e.g., 'news', 'press_release'")
    url: str = Field(..., description="Original canonical URL of the content")
    title: str = Field(..., description="Document headline or title")
    content: Optional[str] = Field(default="", description="Full text body or cleaned snippet")
    author: Optional[str] = Field(default=None, description="Author or publisher name")
    published_at: Optional[datetime] = Field(default=None, description="Original publication timestamp")
    collected_at: datetime = Field(default_factory=datetime.utcnow, description="Ingestion timestamp")
    language: Optional[str] = Field(default=None, description="ISO language code, e.g., 'en', 'fr', 'de'")
    entities_detected: List[str] = Field(default_factory=list, description="Initial entities found during collection")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Raw source-specific metadata payload")