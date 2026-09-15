import os
from typing import List, Optional
from pydantic import BaseModel, Field
from openai import OpenAI
from dotenv import load_dotenv

from collectors.schemas import StandardDocument

load_dotenv()

class ExtractedEvent(BaseModel):
    """Schema enforcing strict structured extraction format."""
    organisation: str = Field(..., description="Name of the primary organisation involved")
    people: List[str] = Field(default_factory=list, description="Key people/executives mentioned")
    event_type: str = Field(
        ...,
        description="One of: Investment, Acquisition, Divestment, Appointment, Departure, Recruitment, Partnership, New office, Fundraising, Product/service launch, Portfolio announcement, Conference/event, Strategic announcement, Other"
    )
    event_date: Optional[str] = Field(default=None, description="Event date in YYYY-MM-DD format if mentioned")
    companies_mentioned: List[str] = Field(default_factory=list, description="All companies mentioned in text")
    location: Optional[str] = Field(default=None, description="City or Country where event occurred")
    sector: Optional[str] = Field(default=None, description="Industry sector (e.g., Wealth Management, HR Tech)")
    amount: Optional[float] = Field(default=None, description="Financial amount involved in EUR/USD if any")
    summary: str = Field(..., description="Clear 1-2 sentence executive summary of the event")
    confidence: float = Field(..., description="Extraction confidence score between 0.0 and 1.0")


class EventExtractor:
    """Uses an LLM to classify content into taxonomy and extract structured event entities."""

    def __init__(self, api_key: Optional[str] = None):
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    def extract(self, document: StandardDocument, matched_org_name: str) -> Optional[ExtractedEvent]:
        prompt = f"""
You are an expert market intelligence analyst.
Analyze the following document related to the target organisation: '{matched_org_name}'.

Allowed event_type values:
- Investment, Acquisition, Divestment, Appointment, Departure, Recruitment, 
  Partnership, New office, Fundraising, Product/service launch, Portfolio announcement, 
  Conference/event, Strategic announcement, Other

Document Title: {document.title}
Document Content: {document.content}
Source URL: {document.url}
"""
        try:
            response = self.client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You extract structured business intelligence events strictly adhering to the schema."},
                    {"role": "user", "content": prompt}
                ],
                response_format=ExtractedEvent,
                temperature=0.0
            )

            return response.choices[0].message.parsed

        except Exception as e:
            print(f"Error during AI structured extraction: {str(e)}")
            return None