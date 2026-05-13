import json
import re
from anthropic import Anthropic
from utils.models import PatientContext, Urgency

client = Anthropic()

# ── Emergency — show slots, say come in now or call 911 ───────────────────────

EMERGENCY_SYSTEM = """
You are a triage assistant for CareDesk AI.

Do NOT greet. Be direct, calm, and brief.

IMPORTANT: Do NOT ask for date of birth, insurance, or anything beyond name and phone number.

Your job on EVERY response:
1. Tell them we have emergency slots available and show the numbered list.
2. Say: "Please come in as soon as possible, or call 911 if this is life-threatening."
3. If you don't yet have their name and phone, ask for them (only these two — nothing else).
4. If they pick a slot number, confirm the booking immediately.
5. Always end with: "Our on-call team has been alerted and will call you shortly."

End every reply with BOTH of these blocks (in this order):
<fields>
{"patient_name": null, "phone": null, "email": null, "address": null}
</fields>
<booking>
{"chosen_slot_id": null, "confirmed": false}
</booking>
Fill in any values extracted. Set confirmed=true when patient picks a slot.
"""

# ── Urgent — collect details, then offer slots ────────────────────────────────

URGENT_COLLECT_SYSTEM = """
You are a triage assistant for CareDesk AI handling a PRIORITY case.

Do NOT greet or introduce yourself. Get straight to collecting contact details.

Collect these 4 fields in order, one or two at a time:
1. Full name
2. Phone number
3. Email address
4. Home address

Rules:
- Ask only for what is still missing.
- Be warm but brief — 1-2 sentences.
- Always end with: "Our team will call you within 10 minutes."

End every reply with:
<fields>
{"patient_name": null, "phone": null, "email": null, "address": null}
</fields>
Fill in any values extracted from the conversation.
"""

URGENT_SCHEDULE_SYSTEM = """
You are a triage assistant for CareDesk AI. All patient details have been collected for a PRIORITY case.

CRITICAL: Do NOT ask for any personal information (name, phone, email, address, date of birth, insurance, or anything else). All details are already on file. Your ONLY job is to show the slot list and let the patient pick one.

Your job: show the numbered list of available slots and let the patient choose.

Say something like:
"We have urgent slots available for [department]. Here are the options — reply with a number to book, or say 'call me' and our team will reach you within 10 minutes."

Then show the numbered list.

If the patient picks a slot number, confirm it and book immediately.
If the patient says "call me" or "no" or prefers callback, confirm that our team will call within 10 minutes.

Rules:
- Be warm and brief.
- Always say: "You can also come in immediately if this is an emergency — please call 911."

End every reply with:
<booking>
{"chosen_slot_id": null, "confirmed": false, "prefers_callback": false}
</booking>
Set confirmed=true and chosen_slot_id when patient picks a slot.
Set prefers_callback=true if patient says they'd rather be called.
"""


def run(context: PatientContext) -> tuple[PatientContext, str, bool]:
    if context.urgency == Urgency.EMERGENCY:
        return _handle_emergency(context)
    return _handle_urgent(context)


# ── Emergency flow ────────────────────────────────────────────────────────────

def _handle_emergency(context: PatientContext) -> tuple[PatientContext, str, bool]:
    from utils.schedule import get_available_slots, format_slots_text, book_slot

    available = get_available_slots(context.department.value)
    slots_text = format_slots_text(available)
    slot_map = {str(i + 1): s["slot_id"] for i, s in enumerate(available)}

    system = EMERGENCY_SYSTEM + f"""

AVAILABLE EMERGENCY SLOTS FOR {context.department.value.upper()}:
{slots_text}

SLOT ID MAP (internal — do not show to patient):
{json.dumps(slot_map)}
"""
    if context.patient_name:
        system += f"\nPATIENT NAME ON FILE: {context.patient_name}"

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=450,
            system=system,
            messages=context.conversation_history,
        )
        full_text = response.content[0].text.strip()
    except Exception:
        reply = (
            f"We have emergency slots available:\n\n{slots_text}\n\n"
            f"Please come in as soon as possible, or call 911 if life-threatening. "
            f"Our on-call team has been alerted and will call you shortly."
        )
        context.conversation_history.append({"role": "assistant", "content": reply})
        return context, reply, False

    reply, fields, booking = _parse_emergency_response(full_text)
    _apply_fields(context, fields)
    _regex_phone(context)

    # Resolve number → slot_id
    chosen_slot_id = booking.get("chosen_slot_id")
    confirmed = bool(booking.get("confirmed", False))
    if chosen_slot_id and chosen_slot_id in slot_map:
        chosen_slot_id = slot_map[chosen_slot_id]

    done = False
    if confirmed and chosen_slot_id:
        appt_id = book_slot(chosen_slot_id, {
            "patient_name": context.patient_name,
            "email": context.patient_email,
            "phone": context.phone,
            "address": context.address,
        })
        if appt_id:
            context.appointment_id = appt_id
            for s in available:
                if s["slot_id"] == chosen_slot_id:
                    context.doctor_name = s["doctor_name"]
                    context.appointment_slot_label = s["label"]
                    break
            done = True
        else:
            reply += "\n\nSorry, that slot was just taken. Please choose another from the list."
    elif context.phone:
        done = True

    if not reply:
        reply = (
            f"Emergency slots available:\n\n{slots_text}\n\n"
            f"Please come in as soon as possible or call 911. Our team has been alerted."
        )

    context.conversation_history.append({"role": "assistant", "content": reply})
    return context, reply, done


# ── Urgent flow ───────────────────────────────────────────────────────────────

def _handle_urgent(context: PatientContext) -> tuple[PatientContext, str, bool]:
    all_details = bool(
        context.patient_name and context.phone
        and context.patient_email and context.address
    )

    if not all_details:
        return _collect_details(context)

    return _offer_slots(context)


def _collect_details(context: PatientContext) -> tuple[PatientContext, str, bool]:
    system = URGENT_COLLECT_SYSTEM + f"""

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
        reply = "Could you please share your full name, phone, email, and home address? Our team will call you within 10 minutes."
        context.conversation_history.append({"role": "assistant", "content": reply})
        return context, reply, False

    reply, fields = _parse_fields(full_text)
    _apply_fields(context, fields)
    _regex_phone(context)

    # If all details just became complete, skip the "thank you" reply and
    # go straight to showing slots in the same turn
    if bool(context.patient_name and context.phone and context.patient_email and context.address):
        return _offer_slots(context)

    if not reply:
        reply = "Thank you. Our team will call you within 10 minutes."

    context.conversation_history.append({"role": "assistant", "content": reply})
    return context, reply, False


def _offer_slots(context: PatientContext) -> tuple[PatientContext, str, bool]:
    from utils.schedule import get_available_slots, format_slots_text, book_slot

    available = get_available_slots(context.department.value)
    slots_text = format_slots_text(available)
    slot_map = {str(i + 1): s["slot_id"] for i, s in enumerate(available)}

    system = URGENT_SCHEDULE_SYSTEM + f"""

DEPARTMENT: {context.department.value}
PATIENT: {context.patient_name}

AVAILABLE URGENT SLOTS:
{slots_text}

SLOT ID MAP (internal):
{json.dumps(slot_map)}
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
        reply = (
            f"Here are urgent slots available for {context.department.value}:\n\n{slots_text}\n\n"
            f"Reply with a number to book, or say 'call me' and our team will call you within 10 minutes.\n"
            f"You can also come in immediately if this is an emergency — please call 911."
        )
        context.conversation_history.append({"role": "assistant", "content": reply})
        return context, reply, False

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

    # Resolve number → slot_id
    if chosen_slot_id and chosen_slot_id in slot_map:
        chosen_slot_id = slot_map[chosen_slot_id]

    done = False

    if confirmed and chosen_slot_id:
        appt_id = book_slot(chosen_slot_id, {
            "patient_name": context.patient_name,
            "email": context.patient_email,
            "phone": context.phone,
            "address": context.address,
        })
        if appt_id:
            context.appointment_id = appt_id
            for s in available:
                if s["slot_id"] == chosen_slot_id:
                    context.doctor_name = s["doctor_name"]
                    context.appointment_slot_label = s["label"]
                    break
            done = True
        else:
            reply += "\n\nSorry, that slot was just taken. Please choose another."

    elif prefers_callback:
        done = True

    if not reply:
        reply = f"Available slots:\n\n{slots_text}\n\nReply with a number to book, or say 'call me'."

    context.conversation_history.append({"role": "assistant", "content": reply})
    return context, reply, done


# ── Helpers ───────────────────────────────────────────────────────────────────

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


def _parse_emergency_response(full_text: str):
    """Parse a response containing both <fields> and <booking> blocks."""
    reply = full_text
    fields = {}
    booking = {}

    if "<fields>" in full_text:
        before, rest = full_text.split("<fields>", 1)
        reply = before.strip()
        fields_end, *after_parts = rest.split("</fields>", 1)
        try:
            fields = json.loads(fields_end.strip())
        except Exception:
            pass
        after = after_parts[0] if after_parts else ""
    else:
        after = full_text

    if "<booking>" in after:
        booking_str = after.split("<booking>", 1)[1].split("</booking>", 1)[0].strip()
        try:
            booking = json.loads(booking_str)
        except Exception:
            pass

    return reply, fields, booking


def _regex_phone(context: PatientContext):
    if context.phone:
        return
    last = next(
        (m["content"] for m in reversed(context.conversation_history) if m["role"] == "user"),
        ""
    )
    m = re.search(r"[\+\d][\d\s\-\(\)]{7,}", last)
    if m:
        context.phone = m.group().strip()
