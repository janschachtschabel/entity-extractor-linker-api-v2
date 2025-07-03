"""Base models for QA functionality.

This module contains shared Pydantic models used across QA endpoints.
"""

from pydantic import BaseModel, Field


class QALevelsConfigMixin(BaseModel):
    """Mixin for QA models that support educational levels configuration."""

    # Bildungsstufen-Konfiguration
    level_property: str | None = Field(
        None, description="Name der Bildungsstufen-Eigenschaft (z.B. 'Bildungsstufe')"
    )
    level_values: list[str] | None = Field(
        None, description="Liste der Bildungsstufen-Werte (z.B. ['Schule', 'Hochschule', 'Berufsbildung'])"
    )


class QABaseRequest(QALevelsConfigMixin):
    """Base request model for QA generation with common parameters."""

    num_pairs: int = Field(10, ge=1, le=20)
    max_answer_length: int = Field(250, ge=50, le=1000)
