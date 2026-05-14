"""
Pydantic models for request validation, internal schema, and API response.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------- Enums ----------

class SourceChannel(str, Enum):
    """Supported inbound message channels."""
    WHATSAPP = "whatsapp"
    BOOKING_COM = "booking_com"
    AIRBNB = "airbnb"
    INSTAGRAM = "instagram"
    DIRECT = "direct"


class QueryType(str, Enum):
    """Classification categories for guest messages."""
    PRE_SALES_AVAILABILITY = "pre_sales_availability"
    PRE_SALES_PRICING = "pre_sales_pricing"
    POST_SALES_CHECKIN = "post_sales_checkin"
    SPECIAL_REQUEST = "special_request"
    COMPLAINT = "complaint"
    GENERAL_ENQUIRY = "general_enquiry"


class ActionType(str, Enum):
    """Routing action based on confidence score."""
    AUTO_SEND = "auto_send"
    AGENT_REVIEW = "agent_review"
    ESCALATE = "escalate"


# ---------- Request Model ----------

class WebhookPayload(BaseModel):
    """Inbound webhook payload from any messaging channel."""
    source: SourceChannel
    guest_name: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=5000)
    timestamp: datetime
    booking_ref: Optional[str] = Field(default=None, max_length=50)
    property_id: Optional[str] = Field(default=None, max_length=50)


# ---------- Internal Unified Schema ----------

class UnifiedMessage(BaseModel):
    """Normalised internal representation of any guest message."""
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: SourceChannel
    guest_name: str
    message_text: str
    timestamp: datetime
    booking_ref: Optional[str] = None
    property_id: Optional[str] = None
    query_type: QueryType = QueryType.GENERAL_ENQUIRY


# ---------- Response Model ----------

class WebhookResponse(BaseModel):
    """API response returned to the caller."""
    message_id: str
    query_type: QueryType
    drafted_reply: str
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    action: ActionType
