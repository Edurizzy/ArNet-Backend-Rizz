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


@shared_task(bind=True, max_retries=5)
def send_outbound_message_task(self, message_id: str, correlation_id: str) -> None:
    """
    Send a queued outbound WhatsApp message via Meta Graph API.

    Idempotent: skips if ``provider_message_id`` is already set.
    """
    mid = uuid.UUID(message_id)
    cid = uuid.UUID(correlation_id)

    from apps.helpdesk import services as helpdesk_services
    from apps.helpdesk.models import Message
    from apps.integrations.meta import selectors as meta_selectors
    from apps.integrations.meta.services import MetaGraphAPIError, send_whatsapp_text_message_via_account

    OUTBOUND_GRAPH_FAILURE_USER_MESSAGE = (
        "WhatsApp send failed. Verify the connected account access token and Meta API status."
    )

    try:
        org_id = Message.objects.values_list("organization_id", flat=True).get(pk=mid)
    except Message.DoesNotExist:
        logger.warning("send_outbound_message_missing_row", extra={"message_id": message_id})
        return

    with transaction.atomic():
        msg = helpdesk_services.start_outbound_message_send(mid, org_id)

    if msg.provider_message_id:
        return
    if msg.delivery_status != Message.DeliveryStatus.SENDING:
        return

    try:
        conn = meta_selectors.get_active_whatsapp_connection_for_org(org_id)
    except meta_selectors.MetaWhatsAppConnectionError as exc:
        with transaction.atomic():
            helpdesk_services.finalize_outbound_message_failed(mid, org_id, str(exc))
        finalized = Message.objects.get(pk=mid)
        helpdesk_services.broadcast_helpdesk_message_event(
            org_id, finalized, correlation_id=cid, provider="meta"
        )
        return

    row = Message.objects.select_related("ticket", "ticket__customer").get(pk=mid)
    to_number = helpdesk_services.normalize_whatsapp_to_number(row.ticket.customer.phone or "")

    try:
        wamid = send_whatsapp_text_message_via_account(conn, to_number, row.content)
    except MetaGraphAPIError as exc:
        if self.request.retries >= self.max_retries:
            with transaction.atomic():
                helpdesk_services.finalize_outbound_message_failed(
                    mid, org_id, OUTBOUND_GRAPH_FAILURE_USER_MESSAGE
                )
            finalized = Message.objects.get(pk=mid)
            helpdesk_services.broadcast_helpdesk_message_event(
                org_id, finalized, correlation_id=cid, provider="meta"
            )
            return
        countdown = min(60 * (2 ** self.request.retries), 900)
        raise self.retry(exc=exc, countdown=countdown) from exc

    with transaction.atomic():
        finalized = helpdesk_services.finalize_outbound_message_sent(mid, org_id, wamid)

    helpdesk_services.broadcast_helpdesk_message_event(
        org_id, finalized, correlation_id=cid, provider="meta"
    )


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
