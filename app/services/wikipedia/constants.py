"""Wikipedia service constants and type definitions."""

from typing import Any, TypeVar

# Constants
MAX_RETRIES = 3
RETRY_DELAY = 1.0  # seconds
JITTER = 0.2  # Random jitter to prevent thundering herd
CHUNK_SIZE = 40  # Keep under 50 (Wikipedia API limit)
WIKIPEDIA_API_URL = "https://{lang}.wikipedia.org/w/api.php"

# Type Aliases
T = TypeVar("T")
PageData = dict[str, Any]
PageDataMap = dict[str, PageData]
RedirectMap = dict[str, str]
