"""Entity models for processing and data exchange.

This module defines the core data structures used for entity processing
throughout the application, especially for service interactions.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Entity:
    """Final entity representation with all linked data."""

    # Core identity
    label: str
    label_en: str | None = None  # English label from Wikipedia
    type: str = "UNKNOWN"

    # Wikipedia URLs
    wiki_url_de: str | None = None
    wiki_url_en: str | None = None

    # Abstracts/descriptions
    abstract_de: str | None = None
    abstract_en: str | None = None

    # Categories and classification
    categories: list[str] = field(default_factory=list)

    # Wikipedia metadata
    internal_links: list[str] = field(default_factory=list)
    infobox_type: str | None = None

    # External identifiers
    wikidata_id: str | None = None
    dbpedia_uri: str | None = None  # DBpedia URI derived from English Wikipedia title

    # Geographic data
    geo_lat: float | None = None
    geo_lon: float | None = None

    # Media
    image_url: str | None = None

    # Status
    status: str = "not_linked"  # "linked" or "not_linked"



    def to_dict(self) -> dict[str, Any]:
        """Convert entity to dictionary for API responses."""
        return {
            "label": self.label,
            "label_en": self.label_en,
            "type": self.type,
            "wiki_url_de": self.wiki_url_de,
            "wiki_url_en": self.wiki_url_en,
            "abstract_de": self.abstract_de,
            "abstract_en": self.abstract_en,
            "categories": self.categories,
            "internal_links": self.internal_links,
            "infobox_type": self.infobox_type,
            "wikidata_id": self.wikidata_id,
            "dbpedia_uri": self.dbpedia_uri,
            "geo_lat": self.geo_lat,
            "geo_lon": self.geo_lon,
            "image_url": self.image_url,
            "status": self.status,
        }
