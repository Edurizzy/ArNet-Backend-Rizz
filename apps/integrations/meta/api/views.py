"""HTTP gateway for Meta webhook ingestion."""

from __future__ import annotations

import json
import logging

from django.conf import settings
from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import services
from ..events import build_meta_ingestion_context
from ..selectors import get_connection_by_verify_token
from ..tasks import process_meta_webhook_task
from ..utils import generate_correlation_id, verify_meta_signature

logger = logging.getLogger(__name__)


class MetaWebhookView(APIView):
    """Meta webhook verification and ingestion endpoint."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        mode = request.query_params.get("hub.mode")
        verify_token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")
        correlation_id = generate_correlation_id()

        if mode != "subscribe" or not verify_token or not challenge:
            logger.warning(
                "meta_webhook_verification_invalid",
                extra=build_meta_ingestion_context(correlation_id=str(correlation_id)),
            )
            return Response({"detail": "Invalid verification request"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            connection = get_connection_by_verify_token(verify_token)
        except Exception:
            logger.warning(
                "meta_webhook_verification_failed",
                extra=build_meta_ingestion_context(correlation_id=str(correlation_id)),
            )
            return Response({"detail": "Invalid verify token"}, status=status.HTTP_403_FORBIDDEN)

        logger.info(
            "meta_webhook_verified",
            extra=build_meta_ingestion_context(
                correlation_id=str(correlation_id),
                organization_id=str(connection.organization_id),
            ),
        )
        return HttpResponse(challenge, content_type="text/plain")

    def post(self, request):
        correlation_id = generate_correlation_id()
        raw_body = request.body
        signature = request.headers.get("X-Hub-Signature-256", "")

        #if not verify_meta_signature(raw_body, signature, settings.META_APP_SECRET):
         #   logger.warning(
          #      "meta_webhook_signature_rejected",
           #     extra=build_meta_ingestion_context(correlation_id=str(correlation_id)),
            #)
            #return Response({"detail": "Invalid signature"}, status=status.HTTP_403_FORBIDDEN)

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning(
                "meta_webhook_invalid_json",
                extra=build_meta_ingestion_context(correlation_id=str(correlation_id)),
            )
            return Response({"detail": "Invalid JSON payload"}, status=status.HTTP_400_BAD_REQUEST)

        event_type = str(payload.get("object", "meta_webhook"))
        raw_event = services.persist_raw_webhook_event(
            payload=payload,
            headers=_safe_headers(request),
            correlation_id=correlation_id,
            event_type=event_type,
        )

        process_meta_webhook_task.delay(str(raw_event.id), str(correlation_id))

        logger.info(
            "meta_webhook_accepted",
            extra=build_meta_ingestion_context(
                correlation_id=str(correlation_id),
                event_id=str(raw_event.id),
            ),
        )
        return Response({"status": "accepted", "correlation_id": str(correlation_id)}, status=status.HTTP_200_OK)


def _safe_headers(request) -> dict:
    redacted = {}
    for key, value in request.headers.items():
        if key.lower() in {"authorization", "x-hub-signature-256"}:
            redacted[key] = "***redacted***"
        else:
            redacted[key] = value
    return redacted
