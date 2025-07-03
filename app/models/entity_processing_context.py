"""Entity processing context for intermediate data during entity linking pipeline."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EntityProcessingContext:
    """Context object for entity processing that holds intermediate data during different processing stages.

    This includes Wikipedia, Wikidata, etc.
    This is used internally during the pipeline and converted to Entity at the end.
    """

    # Core entity information
    label: str
    type: str
    confidence: float = 0.0

    # Service data
    wikipedia_data: dict[str, Any] | None = None
    wikidata_data: dict[str, Any] | None = None

    # Processing metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary."""
        result = {
            "label": self.label,
            "type": self.type,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }

        # Add service data if present
        if self.wikipedia_data:
            result["wikipedia_data"] = self.wikipedia_data

        if self.wikidata_data:
            result["wikidata_data"] = self.wikidata_data

        return result

    def get_service_data(self, service_name: str) -> dict[str, Any] | None:
        """Get data from a specific service."""
        if service_name == "wikipedia":
            return self.wikipedia_data
        if service_name == "wikidata":
            return self.wikidata_data
        return None

    def set_service_data(self, service_name: str, data: dict[str, Any]) -> None:
        """Set data for a specific service."""
        if service_name == "wikipedia":
            self.wikipedia_data = data
        elif service_name == "wikidata":
            self.wikidata_data = data

    def is_linked(self) -> bool:
        """
        Check if entity is considered linked based on available data.

        Returns:
            True if entity has sufficient linking data
        """
        # Check if we have Wikipedia data with Wikidata ID
        if self.wikipedia_data and self.wikipedia_data.get("status") == "found":
            if self.wikipedia_data.get("wikidata_id"):
                return True

        # Check if we have direct Wikidata data
        if self.wikidata_data and self.wikidata_data.get("status") == "found":
            return True

        return False
