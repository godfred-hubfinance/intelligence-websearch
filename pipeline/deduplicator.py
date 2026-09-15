import re
from typing import List, Dict, Any, Optional
from thefuzz import fuzz
from collectors.schemas import StandardDocument

class Deduplicator:
    """Detects exact and near-duplicate documents to group them under single events."""

    def __init__(self, title_similarity_threshold: int = 80):
        self.title_similarity_threshold = title_similarity_threshold

    def _normalize_title(self, title: str) -> str:
        """Cleans title string for fuzzy comparison."""
        return re.sub(r"[^\w\s]", "", (title or "")).strip().lower()

    def is_duplicate(
        self,
        new_doc: StandardDocument,
        existing_docs: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Compares a newly ingested document against already-stored or buffered documents.
        Checks:
          1. Exact URL match
          2. Fuzzy title similarity
        Returns the matching existing document record if duplicate, else None.
        """
        clean_new_title = self._normalize_title(new_doc.title)

        for existing in existing_docs:
            # 1. Exact URL match
            if existing.get("url") and existing["url"] == new_doc.url:
                return {
                    "matched_id": existing.get("id"),
                    "reason": "exact_url",
                    "similarity_score": 100
                }

            # 2. High Fuzzy Title Similarity
            clean_existing_title = self._normalize_title(existing.get("title", ""))
            similarity_ratio = fuzz.token_set_ratio(clean_new_title, clean_existing_title)

            if similarity_ratio >= self.title_similarity_threshold:
                return {
                    "matched_id": existing.get("id"),
                    "reason": "title_similarity",
                    "similarity_score": similarity_ratio
                }

        return None