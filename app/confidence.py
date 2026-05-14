"""
Confidence scoring logic.

Combines three weighted factors to produce a final 0-1 confidence score:

1. Classification Clarity (weight: 0.30)
   How unambiguously the message was classified into a query type.
   Measured as the ratio gap between the top-scoring category and
   the runner-up in the keyword classifier.

2. Context Coverage (weight: 0.35)
   Whether the mock property context contains the information
   needed to answer the query. For example, availability and pricing
   queries score high because we have explicit data; vague or
   out-of-scope requests score lower.

3. Claude Self-Reported Confidence (weight: 0.35)
   Claude is asked to rate its own confidence in its reply.
   This captures nuances the rule engine cannot — e.g. ambiguous
   phrasing, multi-part questions, or requests requiring judgment.

Action mapping:
   confidence >= 0.85            → auto_send
   0.60 <= confidence < 0.85     → agent_review
   confidence < 0.60 OR complaint → escalate
"""

from app.models import QueryType, ActionType


# Context coverage scores per query type.
# These reflect how completely our mock property data can answer each type.
_CONTEXT_COVERAGE: dict[QueryType, float] = {
    QueryType.PRE_SALES_AVAILABILITY: 0.95,  # we have exact dates
    QueryType.PRE_SALES_PRICING: 0.90,       # we have rate card
    QueryType.POST_SALES_CHECKIN: 0.85,       # we have check-in, wifi etc.
    QueryType.SPECIAL_REQUEST: 0.60,          # partial — chef yes, but not all requests
    QueryType.COMPLAINT: 0.40,                # can't resolve complaints with static data
    QueryType.GENERAL_ENQUIRY: 0.65,          # some answers available, some not
}

# Weights for each factor
W_CLARITY = 0.30
W_COVERAGE = 0.35
W_CLAUDE = 0.35


def compute_confidence(
    classification_clarity: float,
    query_type: QueryType,
    claude_confidence: float,
) -> float:
    """
    Compute a weighted confidence score from three independent signals.

    Args:
        classification_clarity: 0-1 score from the classifier indicating
            how clearly the top category dominated.
        query_type: The classified query type (used to look up context coverage).
        claude_confidence: 0-1 score self-reported by Claude.

    Returns:
        Composite confidence score clamped to [0, 1].
    """
    coverage = _CONTEXT_COVERAGE.get(query_type, 0.5)

    score = (
        W_CLARITY * classification_clarity
        + W_COVERAGE * coverage
        + W_CLAUDE * claude_confidence
    )

    return round(max(0.0, min(1.0, score)), 2)


def determine_action(confidence: float, query_type: QueryType) -> ActionType:
    """
    Map a confidence score + query type to a routing action.

    Complaints are always escalated regardless of confidence.
    """
    if query_type == QueryType.COMPLAINT:
        return ActionType.ESCALATE

    if confidence >= 0.85:
        return ActionType.AUTO_SEND
    elif confidence >= 0.60:
        return ActionType.AGENT_REVIEW
    else:
        return ActionType.ESCALATE
