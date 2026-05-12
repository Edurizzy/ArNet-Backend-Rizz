"""Celery tasks for asynchronous Meta webhook processing."""

from __future__ import annotations

import logging
import traceback
import uuid

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from . import services
from .events import build_meta_ingestion_context
from .models import RawWebhookEvent
from .selectors import get_raw_event

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5)
def process_meta_webhook_task(self, event_id: str, correlation_id: str) -> int:
    """Process a persisted Meta webhook event asynchronously."""
    event_uuid = uuid.UUID(event_id)
    correlation_uuid = uuid.UUID(correlation_id)

    logger.info(
        "meta_webhook_task_started",
        extra=build_meta_ingestion_context(
            correlation_id=correlation_id,
            event_id=event_id,
        ),
    )

    _mark_event_processing(event_uuid, correlation_uuid)

    try:
        processed_count = services.process_meta_webhook(event_uuid, correlation_uuid)
        _mark_event_processed(event_uuid, correlation_uuid)
        logger.info(
            "meta_webhook_task_completed",
            extra=build_meta_ingestion_context(
                correlation_id=correlation_id,
                event_id=event_id,
            )
            | {"processed_count": processed_count},
        )
        return processed_count
    except Exception as exc:
        error = traceback.format_exc()
        _mark_event_failed(event_uuid, correlation_uuid, error)
        logger.exception(
            "meta_webhook_task_failed",
            extra=build_meta_ingestion_context(
                correlation_id=correlation_id,
                event_id=event_id,
            ),
        )
        countdown = min(60 * (2 ** self.request.retries), 900)
        raise self.retry(exc=exc, countdown=countdown)


@transaction.atomic
def _mark_event_processing(event_id: uuid.UUID, correlation_id: uuid.UUID) -> None:
    event = get_raw_event(event_id, correlation_id)
    event.status = RawWebhookEvent.Status.PROCESSING
    event.error_message = None
    event.save(update_fields=["status", "error_message", "updated_at"])


@transaction.atomic
def _mark_event_processed(event_id: uuid.UUID, correlation_id: uuid.UUID) -> None:
    event = get_raw_event(event_id, correlation_id)
    event.status = RawWebhookEvent.Status.PROCESSED
    event.error_message = None
    event.processed_at = timezone.now()
    event.save(update_fields=["status", "error_message", "processed_at", "updated_at"])


@transaction.atomic
def _mark_event_failed(event_id: uuid.UUID, correlation_id: uuid.UUID, error: str) -> None:
    event = get_raw_event(event_id, correlation_id)
    event.status = RawWebhookEvent.Status.FAILED
    event.error_message = error
    event.processed_at = timezone.now()
    event.save(update_fields=["status", "error_message", "processed_at", "updated_at"])
