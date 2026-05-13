import os
import json
from datetime import datetime
from dotenv import load_dotenv

from utils.models import PatientContext, Urgency
from utils import logger
from utils.email_sender import (
    alert_oncall_emergency, confirm_patient_emergency,
    alert_dept_urgent, confirm_patient_urgent,
    notify_dept_booking, confirm_patient_booking,
    notify_cancellation,
)
import bots.symptom_bot as symptom_bot
import bots.triage_bot as triage_bot
import bots.appointment_bot as appointment_bot
import bots.cancellation_bot as cancellation_bot

load_dotenv()

CANCEL_KEYWORDS = {"cancel", "cancellation", "reschedule", "cancel appointment", "my appointment"}


def is_cancellation_intent(message: str) -> bool:
    msg = message.lower()
    return any(kw in msg for kw in CANCEL_KEYWORDS)


# ── Intake ────────────────────────────────────────────────────────────────────

def start_conversation(message: str) -> tuple[PatientContext, str, bool]:
    context = PatientContext()
    logger.log_bot_turn("Patient", "user", message)
    context, reply, urgency_determined = symptom_bot.run(message, context)
    logger.log_bot_turn("SymptomBot", "assistant", reply)
    return context, reply, urgency_determined


def continue_intake(message: str, context: PatientContext) -> tuple[PatientContext, str, bool]:
    logger.log_bot_turn("Patient", "user", message)
    context, reply, urgency_determined = symptom_bot.run(message, context)
    logger.log_bot_turn("SymptomBot", "assistant", reply)
    return context, reply, urgency_determined


# ── Specialist routing ────────────────────────────────────────────────────────

def route_to_specialist(context: PatientContext) -> tuple[PatientContext, str, bool]:
    # History ends with an assistant message from SymptomBot — add a user
    # acknowledgment so the specialist bot generates a fresh opening response.
    context.conversation_history.append({"role": "user", "content": "Okay, understood."})

    if context.urgency in (Urgency.EMERGENCY, Urgency.URGENT):
        level = "EMERGENCY" if context.urgency == Urgency.EMERGENCY else "URGENT"
        logger.log_bot_turn("Orchestrator", "system", f"{level} -> TriageBot -> {context.department.value}")
        context, reply, done = triage_bot.run(context)
        logger.log_bot_turn("TriageBot", "assistant", reply)
    else:
        logger.log_bot_turn("Orchestrator", "system", f"ROUTINE -> AppointmentBot -> {context.department.value}")
        context, reply, done = appointment_bot.run(context)
        logger.log_bot_turn("AppointmentBot", "assistant", reply)

    if done:
        _finalize(context)

    return context, reply, done


def next_specialist_turn(message: str, context: PatientContext) -> tuple[PatientContext, str, bool]:
    logger.log_bot_turn("Patient", "user", message)
    context.conversation_history.append({"role": "user", "content": message})

    if context.urgency in (Urgency.EMERGENCY, Urgency.URGENT):
        context, reply, done = triage_bot.run(context)
        logger.log_bot_turn("TriageBot", "assistant", reply)
    else:
        context, reply, done = appointment_bot.run(context)
        logger.log_bot_turn("AppointmentBot", "assistant", reply)

    if done:
        _finalize(context)

    return context, reply, done


# ── Cancellation ──────────────────────────────────────────────────────────────

def start_cancellation(message: str) -> tuple[PatientContext, str, bool]:
    context = PatientContext()
    context.is_cancellation = True
    logger.log_bot_turn("Patient", "user", message)
    context, reply, done = cancellation_bot.run(message, context)
    logger.log_bot_turn("CancellationBot", "assistant", reply)
    if done:
        _finalize_cancellation(context)
    return context, reply, done


def continue_cancellation(message: str, context: PatientContext) -> tuple[PatientContext, str, bool]:
    logger.log_bot_turn("Patient", "user", message)
    context, reply, done = cancellation_bot.run(message, context)
    logger.log_bot_turn("CancellationBot", "assistant", reply)
    if done:
        _finalize_cancellation(context)
    return context, reply, done


def _finalize_cancellation(context: PatientContext):
    appt_id = getattr(context, "_cancelled_appt_id", None)
    appt_details = getattr(context, "_cancelled_appt_details", None)
    if appt_id and appt_details:
        logger.log_bot_turn("Orchestrator", "system", f"Cancellation complete — notifying doctor + patient")
        notify_cancellation(appt_id, appt_details)


# ── Finalize ──────────────────────────────────────────────────────────────────

def _finalize(context: PatientContext):
    logger.log_job(context)
    _save_conversation(context)

    if context.urgency == Urgency.EMERGENCY:
        logger.log_bot_turn("Orchestrator", "system", "EMERGENCY - alerting on-call")
        alert_oncall_emergency(context)
        confirm_patient_emergency(context)
    elif context.urgency == Urgency.URGENT:
        logger.log_bot_turn("Orchestrator", "system", f"URGENT - alerting {context.department.value} coordinator")
        alert_dept_urgent(context)
        confirm_patient_urgent(context)
    else:
        logger.log_bot_turn("Orchestrator", "system", f"ROUTINE - booking with {context.department.value}")
        notify_dept_booking(context)
        confirm_patient_booking(context)


def _save_conversation(context: PatientContext):
    if not context.patient_email:
        return

    history_file = os.path.join(os.path.dirname(__file__), "logs", "conversations.json")
    os.makedirs(os.path.dirname(history_file), exist_ok=True)

    try:
        with open(history_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}

    try:
        from utils.crypto import hash_email, encrypt_record
        key = hash_email(context.patient_email)
        record = encrypt_record({
            "timestamp": datetime.now().isoformat(),
            "urgency": context.urgency.value,
            "department": context.department.value,
            "severity": context.severity_score,
            "symptoms": context.symptom_description,
            "patient_name": context.patient_name,
            "phone": context.phone,
            "appointment_id": context.appointment_id,
            "doctor": context.doctor_name,
            "slot": context.appointment_slot_label,
            "transcript": context.conversation_history,
        })
    except RuntimeError:
        logger.log_bot_turn("Orchestrator", "system", "DATA_ENCRYPTION_KEY not set - not saved")
        return
    except Exception:
        return

    if key not in data:
        data[key] = []
    data[key].append(record)

    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
