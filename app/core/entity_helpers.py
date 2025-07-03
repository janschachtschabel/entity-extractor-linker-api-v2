from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class Entity:
    """Represents a linked entity with multilingual & DBpedia data."""

    label: str
    type: str
    uri: str | None = None  # DBpedia URI
    label_en: str | None = None
    wiki_url_de: str | None = None
    wiki_url_en: str | None = None
    wikidata_id: str | None = None
    dbpedia_uri: str | None = None  # Same as uri, for backward compatibility
    abstract_en: str | None = None
    abstract_de: str | None = None
    abstract: str | None = None  # DBpedia abstract
    thumbnail_url: str | None = None
    image_url: str | None = None  # DBpedia image URL
    categories: list[str] | None = None
    types: list[str] | None = None  # DBpedia types
    has_part: list[str] | None = None  # DBpedia hasPart relationships
    part_of: list[str] | None = None  # DBpedia partOf relationships
    lat: float | None = None
    lon: float | None = None
    geo_lat: float | None = None  # Geographic latitude
    geo_lon: float | None = None  # Geographic longitude
    internal_links: list[str] | None = None  # Wikipedia internal links
    infobox_type: str | None = None
    status: str = "not_linked"  # 'linked' or 'not_linked'

    def to_dict(self) -> dict[str, Any]:
        """Convert entity to dictionary representation."""
        return asdict(self)


def deduplicate_entities(entities: list[tuple[str, str, Any]], max_entities: int = 10) -> list[tuple[str, str, Any]]:
    """Return unique entities (by label, case-insensitive) limited to max_entities."""
    seen = set()
    unique_entities = []
    for label, typ, meta in entities:  # type: str, str, Any
        if label.lower() not in seen and label.strip():
            seen.add(label.lower())
            unique_entities.append((label, typ, meta))
    return unique_entities[:max_entities]
