"""Utility functions for Meta webhook ingestion."""

from __future__ import annotations

import hashlib
import hmac
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class MetaMessageData:
    provider_message_id: str
    phone_number_id: str
    sender_phone: str
    text_body: str
    timestamp: Optional[str]
    contact_name: Optional[str]
    metadata: Dict[str, Any]


@dataclass(frozen=True)
class MetaStatusUpdateData:
    provider_message_id: str
    phone_number_id: str
    status: str
    timestamp: Optional[str]


def generate_correlation_id() -> uuid.UUID:
    """Generate a trace ID that follows the webhook through the pipeline."""
    return uuid.uuid4()


def verify_meta_signature(raw_body: bytes, signature_header: str, app_secret: str) -> bool:
    """Validate Meta's X-Hub-Signature-256 HMAC header."""
    if not app_secret or not signature_header:
        return False

    prefix = "sha256="
    if not signature_header.startswith(prefix):
        return False

    expected_digest = hmac.new(
        key=app_secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    provided_digest = signature_header[len(prefix):]

    return hmac.compare_digest(provided_digest, expected_digest)


def extract_meta_message_data(payload: Dict[str, Any]) -> List[MetaMessageData]:
    """
    Safely extract supported inbound WhatsApp message data from a Meta payload.

    Unsupported changes, status callbacks, and non-text messages are ignored for
    now but preserved in RawWebhookEvent for future replay.
    """
    messages: List[MetaMessageData] = []

    for entry in _as_list(payload.get("entry")):
        for change in _as_list(entry.get("changes")):
            value = change.get("value") if isinstance(change, dict) else {}
            if not isinstance(value, dict):
                continue

            metadata = value.get("metadata") if isinstance(value.get("metadata"), dict) else {}
            phone_number_id = metadata.get("phone_number_id")
            contacts = _as_list(value.get("contacts"))
            contact = contacts[0] if contacts else {}
            contact_name = _extract_contact_name(contact)

            for message in _as_list(value.get("messages")):
                if not isinstance(message, dict):
                    continue

                provider_message_id = message.get("id")
                sender_phone = message.get("from")
                text_body = _extract_text_body(message)

                if not provider_message_id or not phone_number_id or not sender_phone or not text_body:
                    continue

                messages.append(
                    MetaMessageData(
                        provider_message_id=provider_message_id,
                        phone_number_id=phone_number_id,
                        sender_phone=sender_phone,
                        text_body=text_body,
                        timestamp=message.get("timestamp"),
                        contact_name=contact_name,
                        metadata={
                            "provider": "meta",
                            "raw_message_type": message.get("type"),
                            "business_account_id": value.get("messaging_product"),
                            "display_phone_number": metadata.get("display_phone_number"),
                            "wa_id": contact.get("wa_id") if isinstance(contact, dict) else None,
                            "raw_message": message,
                        },
                    )
                )

    return messages


def extract_meta_status_data(payload: Dict[str, Any]) -> List[MetaStatusUpdateData]:
    """Extract WhatsApp message status updates (sent, delivered, read, failed)."""
    updates: List[MetaStatusUpdateData] = []

    for entry in _as_list(payload.get("entry")):
        for change in _as_list(entry.get("changes")):
            value = change.get("value") if isinstance(change, dict) else {}
            if not isinstance(value, dict):
                continue

            metadata = value.get("metadata") if isinstance(value.get("metadata"), dict) else {}
            phone_number_id = metadata.get("phone_number_id")
            if not phone_number_id:
                continue

            for status in _as_list(value.get("statuses")):
                if not isinstance(status, dict):
                    continue

                sid = status.get("id")
                st = status.get("status")
                if sid is None or st is None:
                    continue
                sid_str = str(sid).strip()
                st_str = str(st).strip().lower()
                if not sid_str or not st_str:
                    continue

                updates.append(
                    MetaStatusUpdateData(
                        provider_message_id=sid_str,
                        phone_number_id=str(phone_number_id),
                        status=st_str,
                        timestamp=status.get("timestamp") if isinstance(status.get("timestamp"), str) else None,
                    )
                )

    return updates


def _extract_text_body(message: Dict[str, Any]) -> Optional[str]:
    text = message.get("text")
    if isinstance(text, dict):
        body = text.get("body")
        if isinstance(body, str) and body.strip():
            return body.strip()
    return None


def _extract_contact_name(contact: Dict[str, Any]) -> Optional[str]:
    if not isinstance(contact, dict):
        return None

    profile = contact.get("profile")
    if isinstance(profile, dict):
        name = profile.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return None


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    return []
