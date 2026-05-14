"""
Rule-based query classifier.

Uses keyword matching with weighted scoring to classify guest messages
into one of six predefined query types. Each category has a set of
trigger phrases; the category with the highest cumulative score wins.
"""

import re
from app.models import QueryType


# Each entry: (query_type, weight, list_of_trigger_phrases)
# Higher weight = stronger signal when matched
_CLASSIFICATION_RULES: list[tuple[QueryType, float, list[str]]] = [
    (
        QueryType.COMPLAINT,
        3.0,   # complaints are high-priority, boost weight
        [
            "not working", "broken", "dirty", "unhappy", "not happy",
            "terrible", "worst", "disgusting", "complain", "complaint",
            "disappointed", "unacceptable", "damaged", "noisy", "smell",
            "refund", "compensation", "horrible", "awful", "poor service",
            "angry", "frustrated", "issue with",
        ],
    ),
    (
        QueryType.PRE_SALES_AVAILABILITY,
        2.0,
        [
            "available", "availability", "vacant", "vacancy", "open dates",
            "free dates", "is the villa available", "can i book",
            "dates available", "book for", "reserve",
        ],
    ),
    (
        QueryType.PRE_SALES_PRICING,
        2.0,
        [
            "rate", "price", "pricing", "cost", "charge", "charges",
            "how much", "tariff", "per night", "total cost",
            "quotation", "quote", "budget", "expensive", "discount",
            "offer", "deal",
        ],
    ),
    (
        QueryType.POST_SALES_CHECKIN,
        2.0,
        [
            "check-in", "check in", "checkin", "check-out", "check out",
            "checkout", "wifi", "wi-fi", "password", "arrival",
            "key", "keys", "directions", "address", "reach",
            "how to get", "location",
        ],
    ),
    (
        QueryType.SPECIAL_REQUEST,
        2.0,
        [
            "early check-in", "early checkin", "late check-out",
            "late checkout", "airport transfer", "airport pickup",
            "arrange", "special", "extra bed", "crib", "baby cot",
            "birthday", "anniversary", "decoration", "surprise",
            "cake", "flowers", "candles",
        ],
    ),
    (
        QueryType.GENERAL_ENQUIRY,
        1.0,   # fallback has lowest weight
        [
            "pet", "pets", "parking", "pool", "policy", "rules",
            "allowed", "permit", "facility", "facilities", "amenity",
            "amenities", "restaurant", "nearby", "transport",
        ],
    ),
]


def classify_query(message_text: str) -> tuple[QueryType, float]:
    """
    Classify a guest message into a query type.

    Returns:
        (query_type, classification_clarity)
        - query_type: the best-matching QueryType
        - classification_clarity: a 0-1 score indicating how clearly
          the top category stood out vs the rest (used in confidence calc)
    """
    text = message_text.lower()

    scores: dict[QueryType, float] = {qt: 0.0 for qt in QueryType}

    for query_type, weight, phrases in _CLASSIFICATION_RULES:
        for phrase in phrases:
            # Count non-overlapping occurrences
            count = len(re.findall(re.escape(phrase), text))
            if count > 0:
                scores[query_type] += weight * count

    # Sort by score descending
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_type, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0

    # If nothing matched, default to general enquiry
    if top_score == 0.0:
        return QueryType.GENERAL_ENQUIRY, 0.3

    # Classification clarity: how much the winner stands out
    # Range: 0 (tied) to 1 (dominant)
    if top_score > 0:
        clarity = 1.0 - (second_score / top_score)
    else:
        clarity = 0.0

    # Clamp to [0.3, 1.0] — even a clear winner gets at least 0.3
    clarity = max(0.3, min(1.0, clarity))

    return top_type, clarity
