import re
from typing import List, Dict, Any, Optional
from thefuzz import fuzz
from collectors.schemas import StandardDocument

class EntityMatcher:
    """Matches documents against monitored organisations and people using deterministic and fuzzy matching."""

    def __init__(self, target_organisations: List[Dict[str, Any]]):
        """
        target_organisations expects a list of dictionaries with structure:
        [
            {
                "id": 1,
                "name": "Alpha Wealth Partners",
                "alternative_names": ["Alpha Wealth", "AWP Capital"],
                "website": "https://alphawealth.com",
                "people": ["Jane Doe", "Marc Weber"]
            }
        ]
        """
        self.targets = target_organisations

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"[^\w\s]", " ", (text or "")).lower()

    def match(self, document: StandardDocument) -> Optional[Dict[str, Any]]:
        """
        Evaluates whether a document matches any monitored organisation.
        Returns match metadata with a confidence score (0.0 to 1.0) or None if no match.
        """
        combined_text = f"{document.title} {document.content}"
        clean_text = self._normalize_text(combined_text)

        best_match = None
        highest_score = 0.0

        for org in self.targets:
            score = 0.0
            matched_terms = []

            # 1. Exact / Word Boundary Search on Primary Name
            org_name = org.get("name", "")
            if org_name and re.search(r"\b" + re.escape(org_name.lower()) + r"\b", clean_text):
                score += 0.70
                matched_terms.append(org_name)

            # 2. Alternative Names / Aliases Match
            for alias in org.get("alternative_names", []):
                if alias and re.search(r"\b" + re.escape(alias.lower()) + r"\b", clean_text):
                    score += 0.50
                    matched_terms.append(alias)

            # 3. People / Executive Match
            for person in org.get("people", []):
                if person and re.search(r"\b" + re.escape(person.lower()) + r"\b", clean_text):
                    score += 0.30
                    matched_terms.append(f"Person: {person}")

            # 4. Domain check (if source URL or content references the domain)
            website = org.get("website", "")
            if website:
                domain = website.replace("https://", "").replace("http://", "").replace("www.", "").strip("/")
                if domain and domain in document.url:
                    score += 0.40
                    matched_terms.append(f"Domain: {domain}")

            # Cap confidence score at 1.0
            score = min(score, 1.0)

            # Keep the highest scoring organization match
            if score > highest_score and score >= 0.50:
                highest_score = score
                best_match = {
                    "organisation_id": org["id"],
                    "organisation_name": org["name"],
                    "confidence_score": round(score, 2),
                    "matched_terms": list(set(matched_terms))
                }

        return best_match