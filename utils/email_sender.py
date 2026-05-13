import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from utils.models import PatientContext, Urgency
from utils import logger


# ─── Department → coordinator email map ───────────────────────────────────────

DEPARTMENT_EMAILS = {
    "Cardiology":       os.getenv("CARDIOLOGY_EMAIL"),
    "Dermatology":      os.getenv("DERMATOLOGY_EMAIL"),
    "General Practice": os.getenv("GENERAL_EMAIL"),
    "Emergency":        os.getenv("ONCALL_EMAIL"),   # fallback
    "Unknown":          os.getenv("GENERAL_EMAIL"),
}


def _get_dept_email(context: PatientContext) -> str | None:
    """Return the right coordinator email for this patient's department."""
    return DEPARTMENT_EMAILS.get(context.department.value)


def _send(subject: str, body: str, recipient: str | None):
    if not recipient:
        logger.console.print(f"[yellow][Email] Skipped — no recipient set for this department[/yellow]")
        return
    sender = os.getenv("GMAIL_ADDRESS")
    password = os.getenv("GMAIL_APP_PASSWORD")
    if not all([sender, password]):
        logger.console.print(f"[yellow][Email] Skipped — Gmail credentials not set[/yellow]")
        return
    try:
        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, recipient, msg.as_string())
        logger.console.print(f"[green][Email] Sent → {recipient}[/green]")
    except Exception as e:
        logger.console.print(f"[red][Email] Failed → {recipient}: {e}[/red]")


# ─── EMERGENCY path ───────────────────────────────────────────────────────────
# No appointment. Alert on-call immediately. Patient told to call 911.

def alert_oncall_emergency(context: PatientContext):
    """Fires on EMERGENCY. Goes to on-call coordinator."""
    oncall_email = os.getenv("ONCALL_EMAIL")
    slot = context.appointment_slot_label or ""
    date_str, time_str = slot.rsplit(" at ", 1) if " at " in slot else (slot, "")
    appt_section = (
        f"\nAPPOINTMENT BOOKED\n"
        f"  Appointment ID : {context.appointment_id}\n"
        f"  Doctor         : {context.doctor_name}\n"
        f"  Date           : {date_str}\n"
        f"  Time           : {time_str}\n"
    ) if context.appointment_id else "\n  No slot booked — patient advised to come in immediately or call 911.\n"
    body = (
        f"EMERGENCY ALERT — CALL PATIENT BACK IMMEDIATELY\n"
        f"{'='*40}\n"
        f"{appt_section}\n"
        f"PATIENT DETAILS\n"
        f"{'-'*40}\n"
        f"  Name      : {context.patient_name or 'Unknown'}\n"
        f"  Phone     : {context.phone or '*** NOT YET COLLECTED ***'}\n"
        f"  Address   : {context.address or 'Not provided'}\n"
        f"  Email     : {context.patient_email or 'Not provided'}\n\n"
        f"CLINICAL NOTES\n"
        f"{'-'*40}\n"
        f"  Symptoms  : {context.symptom_description or 'Not specified'}\n"
        f"  Duration  : {context.symptom_duration or 'Not specified'}\n"
        f"  Severity  : {context.severity_score}/5\n"
        f"  Dept      : {context.department.value}\n\n"
        f"{'='*40}\n"
        f"CONVERSATION TRANSCRIPT\n"
        f"{'='*40}\n"
        f"{context.conversation_transcript()}"
    )
    _send("EMERGENCY ALERT — CareDesk — Call Patient Now", body, oncall_email)


def confirm_patient_emergency(context: PatientContext):
    """Sent to patient after emergency triage."""
    if not context.patient_email:
        return
    slot = context.appointment_slot_label or ""
    date_str, time_str = slot.rsplit(" at ", 1) if " at " in slot else (slot, "")
    if context.appointment_id:
        appt_section = (
            f"Your appointment has been booked:\n\n"
            f"  Appointment ID : {context.appointment_id}\n"
            f"  Doctor         : {context.doctor_name or 'TBC'}\n"
            f"  Department     : {context.department.value}\n"
            f"  Date           : {date_str}\n"
            f"  Time           : {time_str}\n\n"
            f"Please arrive as early as possible. "
        )
    else:
        appt_section = (
            f"Our on-call team has been alerted and will call you back as soon as possible.\n\n"
            f"Please come in to our clinic immediately if you can. "
        )
    body = (
        f"Hi {context.patient_name or 'there'},\n\n"
        f"We've received your emergency request.\n\n"
        f"{appt_section}"
        f"If this is life-threatening, please call 911 immediately — do not wait.\n\n"
        f"Details we have on file:\n"
        f"  Symptoms : {context.symptom_description or 'Not specified'}\n"
        f"  Phone    : {context.phone or 'Not provided'}\n\n"
        f"— CareDesk AI\n"
        f"Your Health Coordination Assistant"
    )
    subject = (
        f"[CareDesk] Emergency appointment — {context.doctor_name} — {date_str} at {time_str}"
        if context.appointment_id
        else "[CareDesk] Emergency request received — we're on it"
    )
    _send(subject, body, context.patient_email)


# ─── URGENT path ──────────────────────────────────────────────────────────────
# Alert department coordinator. Promise callback within 2hrs. No firm slot yet.

def alert_dept_urgent(context: PatientContext):
    """
    Fires for URGENT cases.
    Goes to the specific department coordinator inbox.
    """
    dept_email = _get_dept_email(context)
    slot = context.appointment_slot_label or ""
    date_str, time_str = slot.rsplit(" at ", 1) if " at " in slot else (slot, "")
    appt_line = (
        f"\nAPPOINTMENT BOOKED\n"
        f"{'-'*40}\n"
        f"  Appointment ID : {context.appointment_id}\n"
        f"  Doctor         : {context.doctor_name}\n"
        f"  Date           : {date_str}\n"
        f"  Time           : {time_str}\n"
    ) if context.appointment_id else "\n  No slot booked — callback requested within 10 minutes.\n"
    body = (
        f"URGENT — Priority Case — {context.department.value}\n"
        f"{'='*40}\n"
        f"{appt_line}\n"
        f"PATIENT DETAILS\n"
        f"{'-'*40}\n"
        f"  Name       : {context.patient_name or 'Unknown'}\n"
        f"  Phone      : {context.phone or 'Not provided'}\n"
        f"  Email      : {context.patient_email or 'Not provided'}\n"
        f"  Address    : {context.address or 'Not provided'}\n\n"
        f"CLINICAL NOTES\n"
        f"{'-'*40}\n"
        f"  Symptoms   : {context.symptom_description or 'Not specified'}\n"
        f"  Duration   : {context.symptom_duration or 'Not specified'}\n"
        f"  Severity   : {context.severity_score}/5\n\n"
        f"{'='*40}\n"
        f"CONVERSATION TRANSCRIPT\n"
        f"{'='*40}\n"
        f"{context.conversation_transcript()}"
    )
    _send(f"[CareDesk] URGENT — {context.department.value} — {context.patient_name}", body, dept_email)
    logger.console.print(f"[yellow][Routing] URGENT -> {context.department.value} coordinator ({dept_email})[/yellow]")


def confirm_patient_urgent(context: PatientContext):
    if not context.patient_email:
        return
    slot = context.appointment_slot_label or ""
    date_str, time_str = slot.rsplit(" at ", 1) if " at " in slot else (slot, "")
    if context.appointment_id:
        appt_section = (
            f"Your appointment details:\n\n"
            f"  Appointment ID : {context.appointment_id}\n"
            f"  Doctor         : {context.doctor_name or 'TBC'}\n"
            f"  Department     : {context.department.value}\n"
            f"  Date           : {date_str}\n"
            f"  Time           : {time_str}\n"
        )
    else:
        appt_section = (
            f"Our {context.department.value} team will call you within 10 minutes "
            f"to arrange your appointment.\n"
        )
    body = (
        f"Hi {context.patient_name or 'there'},\n\n"
        f"We've received your urgent request.\n\n"
        f"{appt_section}\n"
        f"Your contact details on file:\n"
        f"  Phone    : {context.phone or 'Not provided'}\n"
        f"  Address  : {context.address or 'Not provided'}\n\n"
        f"To cancel, start a new chat at CareDesk AI and say \"I want to cancel my appointment\".\n\n"
        f"If your symptoms worsen, please call 911 immediately.\n\n"
        f"— CareDesk AI\n"
        f"Your Health Coordination Assistant"
    )
    subject = (
        f"[CareDesk] Appointment confirmed — {context.doctor_name} — {date_str} at {time_str}"
        if context.appointment_id
        else f"[CareDesk] Urgent request received — {context.department.value} will call within 10 mins"
    )
    _send(subject, body, context.patient_email)


# ─── ROUTINE path ─────────────────────────────────────────────────────────────
# Full booking. Routes to department coordinator. Confirmation to patient.

def notify_dept_booking(context: PatientContext):
    dept_email = _get_dept_email(context)
    doctor = context.doctor_name or "TBC"
    slot = context.appointment_slot_label or "TBC"
    appt_id = context.appointment_id or "N/A"
    date_str, time_str = slot.rsplit(" at ", 1) if " at " in slot else (slot, "")
    body = (
        f"NEW APPOINTMENT SCHEDULED\n"
        f"{'='*40}\n\n"
        f"  Appointment ID : {appt_id}\n"
        f"  Doctor         : {doctor}\n"
        f"  Department     : {context.department.value}\n"
        f"  Date           : {date_str}\n"
        f"  Time           : {time_str}\n\n"
        f"PATIENT DETAILS\n"
        f"{'-'*40}\n"
        f"  Name     : {context.patient_name or 'Unknown'}\n"
        f"  Phone    : {context.phone or 'Not provided'}\n"
        f"  Email    : {context.patient_email or 'Not provided'}\n"
        f"  Address  : {context.address or 'Not provided'}\n\n"
        f"CLINICAL NOTES\n"
        f"{'-'*40}\n"
        f"  Symptoms : {context.symptom_description or 'Not specified'}\n"
        f"  Duration : {context.symptom_duration or 'Not specified'}\n"
        f"  Severity : {context.severity_score}/5\n\n"
        f"{'='*40}\n"
        f"CONVERSATION TRANSCRIPT\n"
        f"{'='*40}\n"
        f"{context.conversation_transcript()}"
    )
    _send(f"[CareDesk] New Appointment — {doctor} — {date_str} at {time_str}", body, dept_email)
    logger.console.print(f"[Routing] ROUTINE -> {context.department.value} coordinator ({dept_email})")


def confirm_patient_booking(context: PatientContext):
    if not context.patient_email:
        return
    doctor = context.doctor_name or "our specialist"
    slot = context.appointment_slot_label or "your scheduled time"
    appt_id = context.appointment_id or "N/A"
    date_str, time_str = slot.rsplit(" at ", 1) if " at " in slot else (slot, "")
    body = (
        f"Hi {context.patient_name or 'there'},\n\n"
        f"Your appointment has been confirmed! Here are your details:\n\n"
        f"  Appointment ID : {appt_id}\n"
        f"  Doctor         : {doctor}\n"
        f"  Department     : {context.department.value}\n"
        f"  Date           : {date_str}\n"
        f"  Time           : {time_str}\n\n"
        f"  Your contact details on file:\n"
        f"    Phone   : {context.phone or 'Not provided'}\n"
        f"    Address : {context.address or 'Not provided'}\n\n"
        f"To cancel your appointment, simply start a new chat at CareDesk AI and say "
        f"\"I want to cancel my appointment\".\n\n"
        f"If your symptoms worsen before your appointment, please call 911 immediately.\n\n"
        f"— CareDesk AI\n"
        f"Your Health Coordination Assistant"
    )
    _send(f"[CareDesk] Appointment confirmed — {doctor} — {date_str} at {time_str}", body, context.patient_email)


# ─── CANCELLATION path ────────────────────────────────────────────────────────

def notify_cancellation(appt_id: str, appt: dict):
    """Send cancellation emails to the department coordinator and the patient."""
    doctor = appt.get("doctor_name", "TBC")
    dept = appt.get("department", "Unknown")
    slot = appt.get("slot_label", "")
    date_str, time_str = slot.rsplit(" at ", 1) if " at " in slot else (slot, "")
    patient_name = appt.get("patient_name", "Unknown")
    patient_email = appt.get("email", "")
    patient_phone = appt.get("phone", "Not provided")
    patient_address = appt.get("address", "Not provided")

    dept_email = DEPARTMENT_EMAILS.get(dept) or os.getenv("GENERAL_EMAIL")
    doctor_body = (
        f"APPOINTMENT CANCELLED\n"
        f"{'='*40}\n\n"
        f"  Appointment ID : {appt_id}\n"
        f"  Doctor         : {doctor}\n"
        f"  Department     : {dept}\n"
        f"  Date           : {date_str}\n"
        f"  Time           : {time_str}\n\n"
        f"PATIENT DETAILS\n"
        f"{'-'*40}\n"
        f"  Name    : {patient_name}\n"
        f"  Phone   : {patient_phone}\n"
        f"  Email   : {patient_email or 'Not provided'}\n"
        f"  Address : {patient_address}\n\n"
        f"NOTE: This slot has been freed and is now available for other patients."
    )
    _send(
        f"[CareDesk] Cancelled — {doctor} — {date_str} at {time_str}",
        doctor_body,
        dept_email,
    )
    logger.console.print(f"[Cancellation] Notified {dept} coordinator ({dept_email})")

    if not patient_email:
        return
    patient_body = (
        f"Hi {patient_name},\n\n"
        f"Your appointment has been successfully cancelled.\n\n"
        f"  Appointment ID : {appt_id}\n"
        f"  Doctor         : {doctor}\n"
        f"  Department     : {dept}\n"
        f"  Date           : {date_str}\n"
        f"  Time           : {time_str}\n\n"
        f"The slot has been freed and is now available for other patients.\n\n"
        f"To book a new appointment, start a fresh chat at CareDesk AI.\n\n"
        f"— CareDesk AI\n"
        f"Your Health Coordination Assistant"
    )
    _send(
        f"[CareDesk] Appointment cancelled — {doctor} — {date_str} at {time_str}",
        patient_body,
        patient_email,
    )
