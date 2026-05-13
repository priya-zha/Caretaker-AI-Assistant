from anthropic import Anthropic
from utils.models import PatientContext
from utils.schedule import get_patient_appointments, cancel_appointment

client = Anthropic()

SYSTEM = """
You are a CareDesk AI assistant helping a patient cancel their appointment.

Do NOT greet. Get straight to the point.

YOUR FLOW:
1. If you don't have the patient's email or phone yet, ask for it.
2. Once you have it, the system will look up their appointment and you will be given the details.
3. Show the appointment details and ask "Would you like to cancel this appointment? Reply yes or no."
4. If they say yes, confirm cancellation warmly. If no, say okay and close.

Rules:
- Be warm and concise.
- One question at a time.
- If no appointment is found, apologize and suggest they contact the clinic directly.

End every reply with:
<action>
{"identifier": null, "confirm_cancel": false, "appointment_id": null}
</action>

- identifier: the email or phone number the patient just provided (if any)
- confirm_cancel: true only if the patient said yes to cancellation
- appointment_id: the appointment ID being cancelled (provided to you in context)
"""


def run(message: str, context: PatientContext) -> tuple[PatientContext, str, bool]:
    """
    Returns (context, reply, done).
    done=True when the cancellation is complete or patient says no.
    """
    import json

    context.conversation_history.append({"role": "user", "content": message})

    # Inject appointment info into system if we found their appointments
    system = SYSTEM
    if hasattr(context, "_found_appointments") and context._found_appointments:
        appts = context._found_appointments
        appt_lines = []
        for a in appts:
            appt_lines.append(
                f"- Appointment ID: {a['id']} | {a['doctor_name']} ({a['department']}) "
                f"| {a['slot_label']}"
            )
        system += f"\n\nAPPOINTMENTS FOUND FOR THIS PATIENT:\n" + "\n".join(appt_lines)
        system += "\n\nUse the appointment_id from above when the patient confirms cancellation."

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=300,
            system=system,
            messages=context.conversation_history,
        )
        full_text = response.content[0].text.strip()
    except Exception:
        reply = "I'm having trouble right now. Please try again or contact the clinic directly."
        context.conversation_history.append({"role": "assistant", "content": reply})
        return context, reply, False

    reply = full_text
    done = False

    if "<action>" in full_text:
        parts = full_text.split("<action>")
        reply = parts[0].strip()
        try:
            json_str = parts[1].split("</action>")[0].strip()
            action = json.loads(json_str)

            # Look up appointments if identifier was just provided
            identifier = action.get("identifier") or ""
            if identifier and not getattr(context, "_found_appointments", None):
                appts = get_patient_appointments(identifier)
                context._found_appointments = appts
                if not appts:
                    reply = (
                        f"I couldn't find any appointments linked to {identifier}. "
                        "Please double-check the email or phone number, or contact the clinic directly."
                    )
                    context.conversation_history.append({"role": "assistant", "content": reply})
                    return context, reply, True  # end flow

                # Re-run with appointment info injected
                return run.__wrapped__(context) if hasattr(run, "__wrapped__") else _rerun(context, system, appts)

            # Cancel if confirmed
            if action.get("confirm_cancel") and action.get("appointment_id"):
                appt_id = action["appointment_id"]
                appt_details = cancel_appointment(appt_id)
                if appt_details:
                    # Store on context so orchestrator can send emails
                    context._cancelled_appt_id = appt_id
                    context._cancelled_appt_details = appt_details
                    slot = appt_details.get("slot_label", "")
                    date_str, time_str = slot.rsplit(" at ", 1) if " at " in slot else (slot, "")
                    reply = (
                        f"Your appointment with {appt_details.get('doctor_name', 'your doctor')} "
                        f"on {date_str} at {time_str} has been successfully cancelled. "
                        f"The slot is now available for other patients. "
                        f"If you need to rebook, just start a new chat."
                    )
                else:
                    reply = "I couldn't find that appointment. It may have already been cancelled."
                done = True

        except Exception:
            pass

    if not reply:
        reply = "Could you please provide your email address or phone number so I can find your appointment?"

    context.conversation_history.append({"role": "assistant", "content": reply})
    return context, reply, done


def _rerun(context: PatientContext, old_system: str, appts: list) -> tuple[PatientContext, str, bool]:
    """Re-call the LLM now that we have appointment data to inject."""
    import json

    appt_lines = [
        f"- Appointment ID: {a['id']} | {a['doctor_name']} ({a['department']}) | {a['slot_label']}"
        for a in appts
    ]
    system = old_system + "\n\nAPPOINTMENTS FOUND:\n" + "\n".join(appt_lines)
    system += "\n\nShow these details and ask the patient to confirm cancellation."

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=300,
            system=system,
            messages=context.conversation_history,
        )
        full_text = response.content[0].text.strip()
    except Exception:
        full_text = f"I found your appointment:\n" + "\n".join(appt_lines) + "\n\nWould you like to cancel this? Reply yes or no."

    reply = full_text
    if "<action>" in full_text:
        reply = full_text.split("<action>")[0].strip()

    context.conversation_history.append({"role": "assistant", "content": reply})
    return context, reply, False
