from abc import ABC, abstractmethod
from typing import List
from collectors.schemas import StandardDocument

class BaseCollector(ABC):
    """Abstract interface that all data source connectors must implement."""

    def __init__(self, name: str, source_type: str):
        self.name = name
        self.source_type = source_type

    @abstractmethod
    def fetch(self, query: str = None, limit: int = 50) -> List[StandardDocument]:
        """
        Polls the external source and returns a list of StandardDocument objects.
        Must handle its own error logging so failures do not interrupt other connectors.
        """
        pass