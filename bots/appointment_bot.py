import json
import re
from anthropic import Anthropic
from utils.models import PatientContext
from utils.schedule import get_available_slots, format_slots_text, book_slot

client = Anthropic()

COLLECT_SYSTEM = """
You are a scheduling assistant for CareDesk AI. Do NOT greet or introduce yourself.

YOUR JOB: Collect these 4 fields in order, one or two at a time:
1. Full name
2. Phone number
3. Email address
4. Home address

Rules:
- Ask only for what is still missing. Never re-ask something already given.
- Be warm but brief — 1 to 2 sentences.
- Always end with: "Our team will call you within 10 minutes to confirm your appointment."

End every reply with this JSON block:
<fields>
{"patient_name": null, "phone": null, "email": null, "address": null}
</fields>
Fill in any values extracted from the conversation. Use null for anything not yet provided.
"""

SCHEDULE_SYSTEM = """
You are a scheduling assistant for CareDesk AI. All patient details have been collected.

CRITICAL: Do NOT ask for any personal information (name, phone, email, address, date of birth, insurance). All details are already on file.

Your job has TWO phases — determine which phase you are in from the conversation history:

PHASE 1 — No appointment type chosen yet:
Ask warmly:
"What type of appointment would you prefer?
1. Urgent appointment — earliest available slot
2. General / routine appointment
3. Have our team call you within 10 minutes"

PHASE 2 — Patient has replied with a preference:
- If they chose 3 or said "call me" / "call back": Confirm and set prefers_callback=true.
- Otherwise: Say "Give me a moment, I'll pull up the available slots for you." then IMMEDIATELY show the full numbered slot list from the AVAILABLE SLOTS below.
- Once they pick a slot number, confirm the booking immediately.

Rules:
- Be warm and brief.
- Always end with: "Our team will also call you within 10 minutes to confirm."

End every reply with ONE of these booking blocks:

Preference question (Phase 1) or slot list shown (no pick yet):
<booking>
{"chosen_slot_id": null, "confirmed": false, "prefers_callback": false}
</booking>

Patient picked a slot:
<booking>
{"chosen_slot_id": "the exact slot_id they picked", "confirmed": true, "prefers_callback": false}
</booking>

Patient prefers callback:
<booking>
{"chosen_slot_id": null, "confirmed": false, "prefers_callback": true}
</booking>
"""


def run(context: PatientContext) -> tuple[PatientContext, str, bool]:
    all_details = bool(
        context.patient_name and context.phone
        and context.patient_email and context.address
    )

    # ── Phase 1: Collect patient details ─────────────────────────────────────
    if not all_details:
        return _collect_details(context)

    # ── Phase 2 & 3: Show slots and book ─────────────────────────────────────
    return _handle_scheduling(context)


def _collect_details(context: PatientContext) -> tuple[PatientContext, str, bool]:
    system = COLLECT_SYSTEM + f"""

ALREADY COLLECTED:
- Name: {context.patient_name or 'Not yet provided'}
- Phone: {context.phone or 'Not yet provided'}
- Email: {context.patient_email or 'Not yet provided'}
- Address: {context.address or 'Not yet provided'}
"""
    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=300,
            system=system,
            messages=context.conversation_history,
        )
        full_text = response.content[0].text.strip()
    except Exception:
        reply = "Could you please share your full name, phone, email, and address? Our team will call you within 10 minutes."
        context.conversation_history.append({"role": "assistant", "content": reply})
        return context, reply, False

    reply, fields = _parse_fields(full_text)
    _apply_fields(context, fields)

    if not context.phone:
        last = _last_user_msg(context)
        m = re.search(r"[\+\d][\d\s\-\(\)]{7,}", last)
        if m:
            context.phone = m.group().strip()

    # If all details just became complete, skip "thank you" and show slots immediately
    if bool(context.patient_name and context.phone and context.patient_email and context.address):
        return _handle_scheduling(context)

    context.conversation_history.append({"role": "assistant", "content": reply})
    return context, reply, False


def _handle_scheduling(context: PatientContext) -> tuple[PatientContext, str, bool]:
    available = get_available_slots(context.department.value)
    slots_text = format_slots_text(available)

    # Build a slot_id lookup for the LLM: "1" → slot_id
    slot_map = {str(i + 1): s["slot_id"] for i, s in enumerate(available)}

    system = SCHEDULE_SYSTEM + f"""

AVAILABLE SLOTS FOR {context.department.value.upper()}:
{slots_text}

SLOT ID MAP (internal — do not show to patient):
{json.dumps(slot_map)}

PATIENT: {context.patient_name}
"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=400,
            system=system,
            messages=context.conversation_history,
        )
        full_text = response.content[0].text.strip()
    except Exception:
        reply = f"Here are available slots for {context.department.value}:\n\n{slots_text}\n\nReply with a number to book your slot. Our team will also call you within 10 minutes."
        context.conversation_history.append({"role": "assistant", "content": reply})
        return context, reply, False

    # Extract booking block
    reply = full_text
    chosen_slot_id = None
    confirmed = False
    prefers_callback = False

    if "<booking>" in full_text:
        parts = full_text.split("<booking>")
        reply = parts[0].strip()
        try:
            json_str = parts[1].split("</booking>")[0].strip()
            booking = json.loads(json_str)
            chosen_slot_id = booking.get("chosen_slot_id")
            confirmed = bool(booking.get("confirmed", False))
            prefers_callback = bool(booking.get("prefers_callback", False))
        except Exception:
            pass

    # Also try resolving number → slot_id if LLM gave a number
    if chosen_slot_id and chosen_slot_id in slot_map.values():
        pass  # already a valid slot_id
    elif chosen_slot_id and chosen_slot_id in slot_map:
        chosen_slot_id = slot_map[chosen_slot_id]

    # Book the slot if confirmed
    done = False
    if prefers_callback:
        done = True
    elif confirmed and chosen_slot_id:
        appt_id = book_slot(chosen_slot_id, {
            "patient_name": context.patient_name,
            "email": context.patient_email,
            "phone": context.phone,
            "address": context.address,
        })
        if appt_id:
            context.appointment_id = appt_id
            # Find the slot label for confirmation
            for s in available:
                if s["slot_id"] == chosen_slot_id:
                    context.doctor_name = s["doctor_name"]
                    context.appointment_slot_label = s["label"]
                    break
            done = True
        else:
            reply += "\n\nSorry, that slot was just taken. Please choose another."
            done = False

    if not reply:
        reply = f"Here are available slots:\n\n{slots_text}\n\nReply with a number to book."

    context.conversation_history.append({"role": "assistant", "content": reply})
    return context, reply, done


def _parse_fields(full_text: str):
    if "<fields>" in full_text:
        parts = full_text.split("<fields>")
        reply = parts[0].strip()
        try:
            json_str = parts[1].split("</fields>")[0].strip()
            return reply, json.loads(json_str)
        except Exception:
            return full_text, {}
    return full_text, {}


def _apply_fields(context: PatientContext, fields: dict):
    if fields.get("patient_name"):
        context.patient_name = fields["patient_name"]
    if fields.get("phone"):
        context.phone = fields["phone"]
    if fields.get("email"):
        context.patient_email = fields["email"]
    if fields.get("address"):
        context.address = fields["address"]


def _last_user_msg(context: PatientContext) -> str:
    return next(
        (m["content"] for m in reversed(context.conversation_history) if m["role"] == "user"),
        ""
    )
