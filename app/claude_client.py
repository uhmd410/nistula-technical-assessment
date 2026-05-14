"""
Claude API client — drafts guest replies using Anthropic's Claude API.

Sends the unified message along with property context to Claude,
and parses back a structured reply with a self-reported confidence score.
"""

import json
import logging

import anthropic

from app.config import get_settings
from app.context import get_property_context_string
from app.models import UnifiedMessage

logger = logging.getLogger(__name__)

# System prompt template
_SYSTEM_PROMPT = """You are a warm, professional hospitality concierge for Nistula — a luxury villa rental company in Goa, India.

Your job is to draft replies to guest messages. Follow these rules:
1. Use the guest's first name to keep it personal.
2. Be warm, friendly, and helpful — but stay concise (2-4 sentences max).
3. Only answer using the property information provided below. Do NOT invent details.
4. If you cannot confidently answer from the provided context, say so politely and mention that the team will follow up.
5. For complaints, be empathetic and assure the guest that the team is on it. Never be defensive.
6. Use INR (₹) for all prices.

{property_context}

IMPORTANT: You MUST respond with valid JSON in this exact format and nothing else:
{{
    "reply": "Your drafted reply text here",
    "confidence": 0.85
}}

The "confidence" field should be a float between 0.0 and 1.0 representing how confident you are that your reply fully and accurately addresses the guest's query based on the available context. Use these guidelines:
- 0.9-1.0: The answer is directly and completely covered by the property context.
- 0.7-0.89: The answer is mostly covered, but some minor details are assumed.
- 0.5-0.69: The answer is partially covered; some parts need human verification.
- Below 0.5: You are guessing or the context does not cover the query at all.
"""


async def draft_reply(unified_message: UnifiedMessage) -> tuple[str, float]:
    """
    Send the guest message to Claude and get a drafted reply.

    Args:
        unified_message: The normalised guest message.

    Returns:
        (drafted_reply_text, claude_confidence_score)

    Raises:
        anthropic.APIError: If the Claude API call fails.
        ValueError: If the response cannot be parsed.
    """
    settings = get_settings()

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    property_context = get_property_context_string(unified_message.property_id)

    system_prompt = _SYSTEM_PROMPT.format(property_context=property_context)

    user_prompt = (
        f"Guest Name: {unified_message.guest_name}\n"
        f"Channel: {unified_message.source.value}\n"
        f"Query Type: {unified_message.query_type.value}\n"
        f"Booking Reference: {unified_message.booking_ref or 'N/A'}\n"
        f"Property: {unified_message.property_id or 'N/A'}\n"
        f"Timestamp: {unified_message.timestamp.isoformat()}\n\n"
        f"Guest Message:\n{unified_message.message_text}"
    )

    logger.info(
        "Calling Claude API for message_id=%s, query_type=%s",
        unified_message.message_id,
        unified_message.query_type.value,
    )

    response = client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=settings.CLAUDE_MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    # Extract text from response
    raw_text = response.content[0].text.strip()

    # Parse JSON response
    try:
        parsed = json.loads(raw_text)
        reply = parsed.get("reply", "")
        confidence = float(parsed.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))
    except (json.JSONDecodeError, TypeError, KeyError) as e:
        logger.warning(
            "Failed to parse Claude JSON response: %s. Raw: %s",
            str(e),
            raw_text[:200],
        )
        # Fallback: use the raw text as the reply with low confidence
        reply = raw_text
        confidence = 0.4

    if not reply:
        raise ValueError("Claude returned an empty reply.")

    logger.info(
        "Claude responded for message_id=%s — confidence=%.2f",
        unified_message.message_id,
        confidence,
    )

    return reply, confidence
