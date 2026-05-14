# Thinking - Part 3

## Question A - The Immediate Response

"Hi [Guest Name], I'm so sorry, I understand the urgency with breakfast guests arriving. I've immediately alerted our caretaker and property manager, who will call you within the next 15 minutes to resolve this tonight. As a gesture of goodwill, tonight's stay will be fully refunded. You shouldn't have to deal with this.
Thank you for your patience."

This message acknowledges the frustruation of the guest without being defensive. It makes a promise which is concrete with a specific timeframe not a vague reassurance. It goes through with the refund demand rather than making the guest fight for it. Owning the outcome immediately defuses escalation.

## Question B - The System Design

- The moment the message is classified as a complaint it escalates.
- Page the caretaker via SMS/Whatsapp with the guest's unit, issue summary, and a 15 minute SLA clock.
- Notify the property manager
- Log a structured incident record: guest ID, property, issue type, timestamp, reservation details, and a refund flag
- Start an escalation timer: If no caretaker acknowledgement within 15 minutes, auto-escalate to manager's phone. If no response within 30 minutes, escalate to on call senior and send the guest a status update message automatically every 15 mins so they don't feel let down.
- Flag the reservation for finance to process a refund which requires manager confirmation.

## Question C - The Learning

The system should auto tag recurring issues by property + issue type. After two occurrences within 60 days, create a maintainence ticket and notify the property owner not just log it. 
Building a property health dashboard that surfaces issue frequency per property so operations teams can see patterns before a third complaint arrives. Also should have a check protocol that schedules a inspection checklist before a guest arrives specifically for the recurring issue at the property. 