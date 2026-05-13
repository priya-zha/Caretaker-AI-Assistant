import json
from anthropic import Anthropic
from utils.models import PatientContext, Urgency, Department

client = Anthropic()

SYSTEM = """
You are SymptomBot, the intake agent for CareDesk AI.

Your job is to gather enough detail about the patient's symptoms before routing them to the right care.

Rules:
- The patient has already been greeted. Do NOT say hello or introduce yourself.
- Ask only one question at a time.
- Never diagnose. Never give medical advice.
- Be warm, calm, and brief. Patients may be anxious.
- If urgency is OBVIOUS and life-threatening (chest pain, can't breathe, stroke, severe bleeding, loss of consciousness), classify EMERGENCY immediately — do not ask more questions.
- Otherwise, ask AT LEAST 3 questions across these areas before setting needs_more_info=false:
    1. What the symptom looks/feels like (appearance, type, nature)
    2. How long they've had it (duration)
    3. Severity on a scale of 1–5 (1=mild, 5=severe)
  Optional follow-ups depending on symptom type:
    - Rash/skin: spreading? fever? itching/pain?
    - Pain: location, radiating, sharp/dull?
    - Breathing: when does it worsen?
- Do NOT say "Great" or "Perfect" in response to high pain scores — be empathetic ("I'm sorry to hear that", "Thank you for letting me know").

URGENCY LEVELS:
- EMERGENCY: chest pain, difficulty breathing, stroke, severe bleeding, loss of consciousness, severe allergic reaction, suicidal thoughts
- URGENT: high fever (>103F), severity 4–5/5, spreading infection, worsening chronic condition, mental health crisis
- ROUTINE: checkup, mild symptoms (1–3/5), prescription refill, follow-up

DEPARTMENT:
- Chest pain, palpitations, heart-related -> Cardiology
- Rash, skin issue, eczema, dermatitis -> Dermatology
- Everything else -> General Practice

Always reply ONLY with valid JSON, nothing else:
{
  "patient_name": "string or null",
  "symptom_description": "string",
  "symptom_duration": "string or null",
  "severity_score": 1-5,
  "urgency": "EMERGENCY|URGENT|ROUTINE",
  "department": "Cardiology|Dermatology|General Practice",
  "needs_more_info": true or false,
  "reply_to_patient": "what to say to the patient"
}
"""

URGENCY_MAP = {"EMERGENCY": Urgency.EMERGENCY, "URGENT": Urgency.URGENT, "ROUTINE": Urgency.ROUTINE}
DEPT_MAP = {"Cardiology": Department.CARDIOLOGY, "Dermatology": Department.DERMATOLOGY, "General Practice": Department.GENERAL}


def run(user_message: str, context: PatientContext) -> tuple[PatientContext, str, bool]:
    context.conversation_history.append({"role": "user", "content": user_message})
    context.intake_turns += 1

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=600,
            system=SYSTEM,
            messages=context.conversation_history,
        )
        raw = response.content[0].text.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        data = json.loads(raw)
    except json.JSONDecodeError:
        reply = "Could you tell me a bit more about what you're experiencing?"
        context.conversation_history.append({"role": "assistant", "content": reply})
        return context, reply, False
    except Exception as e:
        reply = "I'm having trouble processing that. Could you describe your symptoms again?"
        context.conversation_history.append({"role": "assistant", "content": reply})
        return context, reply, False

    if data.get("patient_name"):
        context.patient_name = data["patient_name"]
    if data.get("symptom_description"):
        context.symptom_description = data["symptom_description"]
    if data.get("symptom_duration"):
        context.symptom_duration = data["symptom_duration"]
    if data.get("severity_score"):
        context.severity_score = data["severity_score"]

    context.urgency = URGENCY_MAP.get(data.get("urgency", "ROUTINE"), Urgency.ROUTINE)
    context.department = DEPT_MAP.get(data.get("department", "General Practice"), Department.GENERAL)

    reply = data.get("reply_to_patient", "Could you tell me more?")
    context.conversation_history.append({"role": "assistant", "content": reply})

    urgency_determined = not data.get("needs_more_info", True)
    return context, reply, urgency_determined
