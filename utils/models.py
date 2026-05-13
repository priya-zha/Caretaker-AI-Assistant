from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Urgency(Enum):
    UNKNOWN = "unknown"
    EMERGENCY = "emergency"   # call 911, alert on-call, NO appointment
    URGENT = "urgent"         # callback within 2hrs, department coordinator
    ROUTINE = "routine"       # standard booking, department coordinator


class Department(Enum):
    CARDIOLOGY = "Cardiology"
    DERMATOLOGY = "Dermatology"
    GENERAL = "General Practice"
    UNKNOWN = "Unknown"


@dataclass
class PatientContext:
    # Identity
    patient_name: Optional[str] = None
    patient_email: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None

    # Clinical
    symptom_description: Optional[str] = None
    symptom_duration: Optional[str] = None
    severity_score: Optional[int] = None   # 1–5
    urgency: Urgency = Urgency.UNKNOWN
    department: Department = Department.UNKNOWN

    # Appointment (only populated for URGENT / ROUTINE)
    preferred_time: Optional[str] = None
    preferred_doctor: Optional[str] = None
    address: Optional[str] = None
    insurance_provider: Optional[str] = None

    # Appointment booking
    appointment_id: Optional[str] = None
    doctor_name: Optional[str] = None
    appointment_slot_label: Optional[str] = None
    selected_slot_id: Optional[str] = None

    # Internal
    conversation_history: list = field(default_factory=list)
    intake_turns: int = 0
    is_cancellation: bool = False

    def conversation_transcript(self) -> str:
        lines = []
        for msg in self.conversation_history:
            role = "Patient" if msg["role"] == "user" else "CareDesk"
            lines.append(f"{role}: {msg['content']}")
        return "\n".join(lines)
