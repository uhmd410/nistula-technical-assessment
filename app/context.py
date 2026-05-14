"""
Mock property context used to ground Claude's replies in real property data.

In production this would be fetched from a database keyed by property_id.
For this assessment, we use a single hardcoded property.
"""

PROPERTY_CONTEXT: dict = {
    "property_id": "villa-b1",
    "name": "Villa B1",
    "location": "Assagao, North Goa",
    "bedrooms": 3,
    "max_guests": 6,
    "private_pool": True,
    "check_in_time": "2:00 PM",
    "check_out_time": "11:00 AM",
    "base_rate_inr": 18000,
    "base_rate_guests": 4,
    "extra_guest_charge_inr": 2000,
    "wifi_password": "Nistula@2024",
    "caretaker_hours": "8:00 AM to 10:00 PM",
    "chef_on_call": True,
    "chef_note": "Pre-booking required",
    "availability_apr_20_24": True,
    "cancellation_policy": "Free cancellation up to 7 days before check-in",
}


def get_property_context_string(property_id: str | None = None) -> str:
    """
    Return a formatted plain-text block of property information
    suitable for injection into a Claude system prompt.

    Args:
        property_id: Currently ignored — always returns Villa B1 context.
    """
    ctx = PROPERTY_CONTEXT
    return f"""
=== PROPERTY INFORMATION ===
Property: {ctx['name']}, {ctx['location']}
Property ID: {ctx['property_id']}
Bedrooms: {ctx['bedrooms']} | Max Guests: {ctx['max_guests']} | Private Pool: {'Yes' if ctx['private_pool'] else 'No'}
Check-in: {ctx['check_in_time']} | Check-out: {ctx['check_out_time']}

PRICING:
- Base rate: INR {ctx['base_rate_inr']:,} per night (up to {ctx['base_rate_guests']} guests)
- Extra guest: INR {ctx['extra_guest_charge_inr']:,} per night per additional person

AMENITIES & SERVICES:
- WiFi Password: {ctx['wifi_password']}
- Caretaker: Available {ctx['caretaker_hours']}
- Chef on call: {'Yes' if ctx['chef_on_call'] else 'No'} ({ctx['chef_note']})

AVAILABILITY:
- April 20–24, 2026: {'Available' if ctx['availability_apr_20_24'] else 'Not Available'}

POLICIES:
- Cancellation: {ctx['cancellation_policy']}
=== END PROPERTY INFORMATION ===
""".strip()
