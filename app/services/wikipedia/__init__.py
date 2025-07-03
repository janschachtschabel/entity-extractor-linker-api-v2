"""
Wikipedia service module with modular architecture.

This module provides Wikipedia entity linking with:
- Clean output structure (label_de/label_en, url_de/url_en, extract)
- Prompt data integration as fallbacks
- Efficient batch processing
- Modular design with separate concerns
"""

from .exceptions import (
    WikipediaAPIError,
    WikipediaAPITimeoutError,
    WikipediaRateLimitError,
    WikipediaServiceError,
    WikipediaValidationError,
)
from .models import WikiPage
from .service import WikipediaService

# For backward compatibility, also export the old service
try:
    from .service_backup import WikipediaService as LegacyWikipediaService
except ImportError:
    LegacyWikipediaService = None

__all__ = [
    "LegacyWikipediaService",
    "WikiPage",
    "WikipediaAPIError",
    "WikipediaAPITimeoutError",
    "WikipediaRateLimitError",
    "WikipediaService",
    "WikipediaServiceError",
    "WikipediaValidationError",
]
