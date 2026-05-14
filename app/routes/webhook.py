"""
Webhook route — POST /webhook/message

Receives inbound guest messages, normalises them, drafts an AI reply
via Claude, computes a confidence score, and returns the response.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.models import WebhookPayload, WebhookResponse
from app.normalizer import normalise_message
from app.classifier import classify_query
from app.claude_client import draft_reply
from app.confidence import compute_confidence, determine_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["Webhook"])


@router.post("/message", response_model=WebhookResponse)
async def handle_message(payload: WebhookPayload) -> WebhookResponse:
    """
    Process an inbound guest message.

    Pipeline:
        1. Normalise the payload into the unified schema
        2. Classify the query type (already done in normaliser)
        3. Send to Claude for a drafted reply
        4. Compute composite confidence score
        5. Determine routing action
        6. Return structured response
    """
    logger.info(
        "Received message from %s via %s",
        payload.guest_name,
        payload.source.value,
    )

    # Step 1-2: Normalise and classify
    unified = normalise_message(payload)

    # Get classification clarity for confidence scoring
    _, classification_clarity = classify_query(payload.message)

    logger.info(
        "Classified message_id=%s as %s (clarity=%.2f)",
        unified.message_id,
        unified.query_type.value,
        classification_clarity,
    )

    # Step 3: Draft reply via Claude
    try:
        drafted_reply, claude_confidence = await draft_reply(unified)
    except Exception as e:
        logger.error("Claude API error: %s", str(e))
        raise HTTPException(
            status_code=503,
            detail=f"AI service temporarily unavailable: {str(e)}",
        )

    # Step 4: Compute composite confidence
    confidence_score = compute_confidence(
        classification_clarity=classification_clarity,
        query_type=unified.query_type,
        claude_confidence=claude_confidence,
    )

    # Step 5: Determine action
    action = determine_action(confidence_score, unified.query_type)

    logger.info(
        "Response ready for message_id=%s — confidence=%.2f, action=%s",
        unified.message_id,
        confidence_score,
        action.value,
    )

    # Step 6: Build and return response
    return WebhookResponse(
        message_id=unified.message_id,
        query_type=unified.query_type,
        drafted_reply=drafted_reply,
        confidence_score=confidence_score,
        action=action,
    )
