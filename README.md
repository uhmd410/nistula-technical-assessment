# Nistula Technical Assessment — Guest Message Handler

A backend system that receives guest messages from multiple channels (WhatsApp, Airbnb, Booking.com, Instagram, Direct), normalises them into a unified schema, drafts AI-powered replies via Claude, and returns responses with confidence-based routing.

## Repository Structure

```
├── README.md                   # This file
├── .env.example                # Environment variable template
├── .gitignore                  # Python gitignore
├── requirements.txt            # Python dependencies
├── schema.sql                  # Part 2 — PostgreSQL schema with design comments
├── thinking.md                 # Part 3 — Written answers
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app entry point
│   ├── config.py               # Settings from .env
│   ├── models.py               # Pydantic request/response models
│   ├── classifier.py           # Rule-based query classification
│   ├── normalizer.py           # Webhook payload → unified schema
│   ├── context.py              # Mock property context data
│   ├── claude_client.py        # Claude API integration
│   ├── confidence.py           # Confidence scoring logic
│   └── routes/
│       ├── __init__.py
│       └── webhook.py          # POST /webhook/message endpoint
└── tests/
    ├── __init__.py
    └── test_webhook.py         # 6 test scenarios (3 required + 3 extra)
```

---

## Setup Instructions

### Prerequisites

- Python 3.11+
- An Anthropic API key ([get one here](https://console.anthropic.com/))

### 1. Clone and set up virtual environment

```bash
git clone https://github.com/<your-username>/nistula-technical-assessment.git
cd nistula-technical-assessment

python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and insert your Anthropic API key:

```
ANTHROPIC_API_KEY=sk-ant-xxxxx
```

### 4. Run the server

```bash
uvicorn app.main:app --reload
```

The server starts at `http://127.0.0.1:8000`. Interactive API docs are available at `http://127.0.0.1:8000/docs`.

---

## API Endpoints

### `POST /webhook/message`

Receives a guest message and returns an AI-drafted reply.

**Request body:**

```json
{
    "source": "whatsapp",
    "guest_name": "Rahul Sharma",
    "message": "Is the villa available from April 20 to 24? What is the rate for 2 adults?",
    "timestamp": "2026-05-05T10:30:00Z",
    "booking_ref": "NIS-2024-0891",
    "property_id": "villa-b1"
}
```

| Field          | Type     | Required | Notes                                                |
|----------------|----------|----------|------------------------------------------------------|
| `source`       | string   | ✅       | One of: `whatsapp`, `booking_com`, `airbnb`, `instagram`, `direct` |
| `guest_name`   | string   | ✅       | 1–200 characters                                     |
| `message`      | string   | ✅       | 1–5000 characters                                    |
| `timestamp`    | datetime | ✅       | ISO 8601 format                                      |
| `booking_ref`  | string   | ❌       | Booking reference if available                       |
| `property_id`  | string   | ❌       | Property identifier                                  |

**Response:**

```json
{
    "message_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "query_type": "pre_sales_availability",
    "drafted_reply": "Hi Rahul! Great news — Villa B1 is available from April 20 to 24! ...",
    "confidence_score": 0.91,
    "action": "auto_send"
}
```

**cURL example:**

```bash
curl -X POST http://127.0.0.1:8000/webhook/message \
  -H "Content-Type: application/json" \
  -d '{
    "source": "whatsapp",
    "guest_name": "Rahul Sharma",
    "message": "Is the villa available from April 20 to 24? What is the rate for 2 adults?",
    "timestamp": "2026-05-05T10:30:00Z",
    "booking_ref": "NIS-2024-0891",
    "property_id": "villa-b1"
  }'
```

**Invoke-RestMethod example (for PowerShell):**

```bash
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/webhook/message" -ContentType "application/json" -Body '{
  "source": "direct",
  "guest_name": "Arjun Nair",
  "message": "What time is check-in and what is the WiFi password?",
  "timestamp": "2026-05-14T11:00:00Z",
  "booking_ref": "NIS-2025-0042",
  "property_id": "villa-b1"
}'
```

### `GET /health`

Returns `{"status": "healthy", "service": "nistula-message-handler"}`.

---

## Query Classification

Messages are classified into one of six types using a rule-based keyword engine:

| Query Type                | Examples                                          |
|---------------------------|---------------------------------------------------|
| `pre_sales_availability`  | "Is the villa available on these dates?"          |
| `pre_sales_pricing`       | "What is the rate for 2 adults, 3 nights?"        |
| `post_sales_checkin`      | "What time can we check in? WiFi password?"       |
| `special_request`         | "Can you arrange an early check-in?"              |
| `complaint`               | "The AC is not working. I am not happy."          |
| `general_enquiry`         | "Do you allow pets? Is there parking?"            |

The classifier uses weighted keyword matching — each category has trigger phrases with assigned weights. The category with the highest cumulative score wins. Complaints have the highest weight (3x) to ensure they're never missed.

---

## Confidence Scoring Logic

The confidence score (0–1) is a **weighted composite** of three independent signals:

### Factor 1: Classification Clarity (Weight: 30%)

Measures how unambiguously the message was classified. Calculated as the gap between the top-scoring category and the runner-up in keyword matching.

- **High clarity (0.8–1.0):** Message clearly belongs to one category (e.g. "Is it available?" → availability)
- **Low clarity (0.3–0.5):** Message triggers multiple categories equally (e.g. "Is it available and how much?" → availability + pricing)

### Factor 2: Context Coverage (Weight: 35%)

A static score per query type reflecting how completely our property context can answer that type of question:

| Query Type              | Coverage Score | Rationale                                    |
|-------------------------|----------------|----------------------------------------------|
| `pre_sales_availability`| 0.95           | Exact dates available in context             |
| `pre_sales_pricing`     | 0.90           | Full rate card available                     |
| `post_sales_checkin`    | 0.85           | Check-in time, WiFi, caretaker info present  |
| `general_enquiry`       | 0.65           | Some FAQs covered, not all                   |
| `special_request`       | 0.60           | Chef available, but not all requests possible|
| `complaint`             | 0.40           | Can acknowledge, but can't resolve with data |

### Factor 3: Claude Self-Reported Confidence (Weight: 35%)

Claude is instructed to return a confidence float (0–1) alongside its reply. This captures nuance that the rule engine misses — ambiguous phrasing, multi-part questions, or requests requiring human judgment.

### Final Score

```
confidence = 0.30 × clarity + 0.35 × coverage + 0.35 × claude_confidence
```

### Action Routing

| Confidence        | Action         | Meaning                          |
|-------------------|----------------|----------------------------------|
| ≥ 0.85            | `auto_send`    | Send reply without human review  |
| 0.60 – 0.84       | `agent_review` | Queue for agent to review/edit   |
| < 0.60            | `escalate`     | Route to senior agent            |
| Any (complaint)   | `escalate`     | Complaints always escalate       |

---

## Running Tests

Tests mock the Claude API — no API key needed.

```bash
pytest tests/ -v
```

The test suite covers 6 scenarios:
1. ✅ Pre-sales availability query (WhatsApp)
2. ✅ Complaint with auto-escalation (Airbnb)
3. ✅ Post-sales check-in info (Direct)
4. ✅ Invalid source channel → 422
5. ✅ Missing required field → 422
6. ✅ Special request (Instagram)

---

## Error Handling

| Status Code | Scenario                                  |
|-------------|-------------------------------------------|
| 200         | Successful response                       |
| 422         | Invalid payload (wrong source, missing fields) |
| 503         | Claude API unavailable                    |
| 500         | Unexpected server error                   |

All errors return structured JSON with a `detail` field.

---

## Tech Stack

- **FastAPI** — async web framework
- **Pydantic** — data validation and serialization
- **Anthropic SDK** — Claude API client
- **pytest** — test framework
