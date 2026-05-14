"""
Integration tests for the /webhook/message endpoint.

These tests mock the Claude API to avoid real API calls during testing,
while still exercising the full pipeline: validation → normalisation →
classification → confidence scoring → response formatting.

Run with:
    pytest tests/ -v
"""

import json
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _mock_claude_response(reply: str, confidence: float):
    """Create a mock Anthropic API response."""
    mock_response = MagicMock()
    mock_content = MagicMock()
    mock_content.text = json.dumps({"reply": reply, "confidence": confidence})
    mock_response.content = [mock_content]
    return mock_response


# ---------- Test 1: Pre-sales Availability (WhatsApp) ----------

@patch("app.claude_client.anthropic.Anthropic")
def test_pre_sales_availability(mock_anthropic_class):
    """
    Scenario: A guest asks about villa availability via WhatsApp.
    Expected: query_type = pre_sales_availability, high confidence, auto_send.
    """
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_claude_response(
        reply="Hi Rahul! Great news — Villa B1 is available from April 20 to 24! "
              "The base rate is ₹18,000 per night for up to 4 guests. "
              "For 2 adults, the total would be ₹72,000 for 4 nights. "
              "Would you like me to reserve it for you?",
        confidence=0.95,
    )
    mock_anthropic_class.return_value = mock_client

    payload = {
        "source": "whatsapp",
        "guest_name": "Rahul Sharma",
        "message": "Is the villa available from April 20 to 24? What is the rate for 2 adults?",
        "timestamp": "2026-05-05T10:30:00Z",
        "booking_ref": "NIS-2024-0891",
        "property_id": "villa-b1",
    }

    response = client.post("/webhook/message", json=payload)

    assert response.status_code == 200
    data = response.json()

    assert data["query_type"] in ["pre_sales_availability", "pre_sales_pricing"]
    assert 0 <= data["confidence_score"] <= 1
    assert data["confidence_score"] >= 0.60
    assert data["action"] in ["auto_send", "agent_review"]
    assert len(data["drafted_reply"]) > 0
    assert "message_id" in data


# ---------- Test 2: Complaint (Airbnb) ----------

@patch("app.claude_client.anthropic.Anthropic")
def test_complaint_message(mock_anthropic_class):
    """
    Scenario: A guest complains about the AC not working via Airbnb.
    Expected: query_type = complaint, action = escalate (always for complaints).
    """
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_claude_response(
        reply="Hi Priya, I'm so sorry to hear about the AC issue. "
              "I've immediately flagged this to our caretaker who will be at "
              "the villa within the hour. Your comfort is our top priority.",
        confidence=0.80,
    )
    mock_anthropic_class.return_value = mock_client

    payload = {
        "source": "airbnb",
        "guest_name": "Priya Patel",
        "message": "The AC is not working in the master bedroom. I am very unhappy with the experience so far.",
        "timestamp": "2026-05-06T22:15:00Z",
        "booking_ref": "NIS-2024-1102",
        "property_id": "villa-b1",
    }

    response = client.post("/webhook/message", json=payload)

    assert response.status_code == 200
    data = response.json()

    assert data["query_type"] == "complaint"
    assert data["action"] == "escalate"  # complaints always escalate
    assert len(data["drafted_reply"]) > 0
    assert 0 <= data["confidence_score"] <= 1


# ---------- Test 3: Post-sales Check-in (Direct) ----------

@patch("app.claude_client.anthropic.Anthropic")
def test_post_sales_checkin(mock_anthropic_class):
    """
    Scenario: A guest asks about check-in time and WiFi via direct channel.
    Expected: query_type = post_sales_checkin, reasonable confidence.
    """
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_claude_response(
        reply="Hi Amit! Check-in is at 2:00 PM and the WiFi password is Nistula@2024. "
              "Our caretaker will be there to welcome you. See you soon!",
        confidence=0.92,
    )
    mock_anthropic_class.return_value = mock_client

    payload = {
        "source": "direct",
        "guest_name": "Amit Desai",
        "message": "What time can we check in tomorrow? Also, what is the WiFi password?",
        "timestamp": "2026-05-07T09:00:00Z",
        "booking_ref": "NIS-2024-1200",
        "property_id": "villa-b1",
    }

    response = client.post("/webhook/message", json=payload)

    assert response.status_code == 200
    data = response.json()

    assert data["query_type"] == "post_sales_checkin"
    assert 0 <= data["confidence_score"] <= 1
    assert data["action"] in ["auto_send", "agent_review"]
    assert len(data["drafted_reply"]) > 0


# ---------- Test 4: Validation Error ----------

def test_invalid_source_returns_422():
    """
    Scenario: Payload has an invalid source channel.
    Expected: 422 Unprocessable Entity.
    """
    payload = {
        "source": "telegram",  # not a valid source
        "guest_name": "Test User",
        "message": "Hello",
        "timestamp": "2026-05-05T10:30:00Z",
    }

    response = client.post("/webhook/message", json=payload)
    assert response.status_code == 422


# ---------- Test 5: Missing required field ----------

def test_missing_message_returns_422():
    """
    Scenario: Payload is missing the required 'message' field.
    Expected: 422 Unprocessable Entity.
    """
    payload = {
        "source": "whatsapp",
        "guest_name": "Test User",
        "timestamp": "2026-05-05T10:30:00Z",
    }

    response = client.post("/webhook/message", json=payload)
    assert response.status_code == 422


# ---------- Test 6: Special Request (Instagram) ----------

@patch("app.claude_client.anthropic.Anthropic")
def test_special_request(mock_anthropic_class):
    """
    Scenario: A guest requests early check-in via Instagram.
    Expected: query_type = special_request.
    """
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_claude_response(
        reply="Hi Sneha! I'd be happy to arrange an early check-in for you. "
              "Let me check with the team and get back to you shortly.",
        confidence=0.70,
    )
    mock_anthropic_class.return_value = mock_client

    payload = {
        "source": "instagram",
        "guest_name": "Sneha Reddy",
        "message": "Can you arrange an early check-in around 10 AM? We have a long flight and would like to rest.",
        "timestamp": "2026-05-08T14:20:00Z",
        "booking_ref": "NIS-2024-1305",
        "property_id": "villa-b1",
    }

    response = client.post("/webhook/message", json=payload)

    assert response.status_code == 200
    data = response.json()

    assert data["query_type"] == "special_request"
    assert 0 <= data["confidence_score"] <= 1
    assert len(data["drafted_reply"]) > 0
