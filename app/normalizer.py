"""
Normaliser — converts raw webhook payloads into the unified internal schema.
"""

from app.models import WebhookPayload, UnifiedMessage
from app.classifier import classify_query


def normalise_message(payload: WebhookPayload) -> UnifiedMessage:
    """
    Transform a raw webhook payload into the unified message schema.

    Steps:
        1. Generate a unique message_id (handled by UnifiedMessage default)
        2. Classify the query type via keyword matching
        3. Map field names (message → message_text)
    """
    query_type, _ = classify_query(payload.message)

    return UnifiedMessage(
        source=payload.source,
        guest_name=payload.guest_name,
        message_text=payload.message,
        timestamp=payload.timestamp,
        booking_ref=payload.booking_ref,
        property_id=payload.property_id,
        query_type=query_type,
    )
