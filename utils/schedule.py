import uuid
from datetime import datetime, timedelta
from typing import Optional

# ── Generate doctor slots for the next 7 days ─────────────────────────────────

def _make_slots(doc_id: str) -> dict:
    slots = {}
    times = ["9:00 AM", "11:00 AM", "2:00 PM", "4:00 PM"]
    today = datetime.now()
    for offset in range(1, 8):
        date = today + timedelta(days=offset)
        date_key = date.strftime("%Y%m%d")
        day_label = date.strftime("%A, %b %d")
        for i, t in enumerate(times):
            sid = f"{doc_id}_{date_key}_{i}"
            slots[sid] = {"label": f"{day_label} at {t}", "available": True}
    return slots


DOCTORS: dict = {
    "Dermatology": [
        {"id": "dr_chen",  "name": "Dr. Sarah Chen",    "slots": _make_slots("dr_chen")},
        {"id": "dr_patel", "name": "Dr. James Patel",   "slots": _make_slots("dr_patel")},
    ],
    "Cardiology": [
        {"id": "dr_torres", "name": "Dr. Michael Torres", "slots": _make_slots("dr_torres")},
        {"id": "dr_sharma", "name": "Dr. Priya Sharma",   "slots": _make_slots("dr_sharma")},
    ],
    "General Practice": [
        {"id": "dr_wong",  "name": "Dr. Lisa Wong",  "slots": _make_slots("dr_wong")},
        {"id": "dr_kumar", "name": "Dr. Raj Kumar",  "slots": _make_slots("dr_kumar")},
    ],
}

# appointment_id → appointment details
APPOINTMENTS: dict = {}

# email/phone (lowercase) → [appointment_id, ...]
PATIENT_INDEX: dict = {}


# ── Public API ────────────────────────────────────────────────────────────────

def get_available_slots(department: str, limit: int = 8) -> list[dict]:
    """Return up to `limit` available slots across all doctors in a department."""
    docs = DOCTORS.get(department) or DOCTORS.get("General Practice", [])
    results = []
    for doc in docs:
        for slot_id, slot in doc["slots"].items():
            if slot["available"]:
                results.append({
                    "slot_id": slot_id,
                    "doctor_name": doc["name"],
                    "label": slot["label"],
                })
    return results[:limit]


def format_slots_text(slots: list[dict]) -> str:
    if not slots:
        return "No slots available right now. Our team will contact you directly."
    lines = [f"{i+1}. {s['doctor_name']} — {s['label']}" for i, s in enumerate(slots)]
    return "\n".join(lines)


def book_slot(slot_id: str, patient_info: dict) -> Optional[str]:
    """Mark slot as booked. Returns appointment_id, or None if already taken."""
    for dept, docs in DOCTORS.items():
        for doc in docs:
            if slot_id in doc["slots"]:
                slot = doc["slots"][slot_id]
                if not slot["available"]:
                    return None
                slot["available"] = False
                appt_id = "APT-" + uuid.uuid4().hex[:6].upper()
                APPOINTMENTS[appt_id] = {
                    **patient_info,
                    "doctor_name": doc["name"],
                    "slot_label": slot["label"],
                    "slot_id": slot_id,
                    "department": dept,
                }
                for key in [
                    (patient_info.get("email") or "").lower().strip(),
                    (patient_info.get("phone") or "").strip(),
                ]:
                    if key:
                        PATIENT_INDEX.setdefault(key, []).append(appt_id)
                return appt_id
    return None


def cancel_appointment(appt_id: str) -> dict | None:
    """Cancel appointment and free the slot. Returns the appointment details on success, None if not found."""
    appt = APPOINTMENTS.pop(appt_id, None)
    if not appt:
        return None
    # Free the slot so other patients can book it
    slot_id = appt.get("slot_id", "")
    for docs in DOCTORS.values():
        for doc in docs:
            if slot_id in doc["slots"]:
                doc["slots"][slot_id]["available"] = True
    # Remove from patient index
    for ids in PATIENT_INDEX.values():
        if appt_id in ids:
            ids.remove(appt_id)
    return appt


def get_patient_appointments(identifier: str) -> list[dict]:
    """Look up appointments by email or phone number."""
    key = identifier.lower().strip()
    ids = PATIENT_INDEX.get(key, [])
    return [{"id": aid, **APPOINTMENTS[aid]} for aid in ids if aid in APPOINTMENTS]
