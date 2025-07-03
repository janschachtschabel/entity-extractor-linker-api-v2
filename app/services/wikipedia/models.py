"""Data models for Wikipedia service."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WikiPage:
    """Represents a Wikipedia page with multilingual data."""

    # Required fields
    title_en: str | None = None
    abstract_en: str | None = None
    wikidata_id: str | None = None

    # German content (optional)
    title_de: str | None = None
    abstract_de: str | None = None

    # Common fields
    thumbnail_url: str | None = None
    categories: list[str] = field(default_factory=list)
    internal_links: list[str] = field(default_factory=list)
    infobox_type: str | None = None
    lat: float | None = None
    lon: float | None = None

    # Computed properties
    @property
    def wiki_url_en(self) -> str | None:
        """Get the English Wikipedia URL for this page if available."""
        if not self.title_en:
            return None
        return f"https://en.wikipedia.org/wiki/{self.title_en.replace(' ', '_')}"

    @property
    def wiki_url_de(self) -> str | None:
        """Get the German Wikipedia URL for this page if available."""
        if not self.title_de:
            return None
        return f"https://de.wikipedia.org/wiki/{self.title_de.replace(' ', '_')}"

    def to_dict(self) -> dict[str, Any]:
        """Convert the WikiPage to a dictionary."""
        return {
            "title_en": self.title_en,
            "abstract_en": self.abstract_en,
            "title_de": self.title_de,
            "abstract_de": self.abstract_de,
            "wikidata_id": self.wikidata_id,
            "thumbnail_url": self.thumbnail_url,
            "categories": self.categories,
            "internal_links": self.internal_links,  # Add internal_links to to_dict
            "infobox_type": self.infobox_type,
            "lat": self.lat,
            "lon": self.lon,
            "wiki_url_en": self.wiki_url_en,
            "wiki_url_de": self.wiki_url_de,
        }
