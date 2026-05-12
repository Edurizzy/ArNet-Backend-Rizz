"""Provider-level event helpers for Meta ingestion observability."""

from __future__ import annotations

from typing import Any, Dict, Optional

from django.utils import timezone


def build_meta_ingestion_context(
    *,
    correlation_id: str,
    event_id: Optional[str] = None,
    organization_id: Optional[str] = None,
    provider_message_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Return stable metadata for logs, audit trails, and future tracing."""
    return {
        "provider": "meta",
        "correlation_id": correlation_id,
        "event_id": event_id,
        "organization_id": organization_id,
        "provider_message_id": provider_message_id,
        "timestamp": timezone.now().isoformat(),
    }
