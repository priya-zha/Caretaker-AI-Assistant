# CareDesk AI — Health Services Co-Worker

> A Red-Zone multi-agent AI Co-Worker for healthcare intake and patient coordination.

CareDesk is a bespoke, persona-driven AI system that routes patients to the right care pathway — triaging urgency, collecting structured clinical data, and triggering automated notifications to both patient and care coordinator.

Built on the same architectural principles as enterprise AI workers: controlled, context-specific workflows with full conversation observability.

---

## Architecture

```
Patient Message
      │
      ▼
┌─────────────┐
│ SymptomBot  │  ← Classifies urgency + department from natural language
│  (Intake)   │    Outputs structured JSON: severity 1–5, urgency, dept
└──────┬──────┘
       │
       ▼
  Orchestrator  ← Routes based on urgency
  /           \
 EMERGENCY    ROUTINE
 URGENT
  │              │
  ▼              ▼
TriageBot    AppointmentBot
  │              │
  └──────┬───────┘
         │
         ▼
    Email Engine
   /            \
Coordinator    Patient
  Email         Email
```

### The Three Agents

| Agent | Role | Triggered When |
|---|---|---|
| **SymptomBot** | Intake — reads symptoms, scores severity (1–5), classifies urgency, routes to department | Every conversation |
| **TriageBot** | Emergency handler — gives safety instructions, collects contact info, escalates to care team | EMERGENCY or URGENT |
| **AppointmentBot** | Scheduler — books with the right department, collects details, sets expectations | ROUTINE |

### Department Routing

SymptomBot automatically routes to the right department based on symptoms:

| Symptoms | Department |
|---|---|
| Chest pain, palpitations | Cardiology |
| Rash, skin lesion | Dermatology |
| Joint pain, injury | Orthopedics |
| Headache, numbness, dizziness | Neurology |
| Child under 18 | Pediatrics |
| Anxiety, depression | Mental Health |
| Everything else | General Practice |

---

## What It Does

1. **Patient sends a message** — "I've had chest tightness for 2 days and I'm short of breath"
2. **SymptomBot classifies** — URGENT, Cardiology, severity 4/5
3. **Orchestrator routes** — to TriageBot (urgent case)
4. **TriageBot responds** — gives safety guidance, collects contact info
5. **Emails fire automatically:**
   - Coordinator gets full transcript + patient details flagged as urgent
   - Patient gets confirmation + what to do if symptoms worsen
6. **Everything is logged** — conversation history saved by patient email for lookup

---

## Setup

```bash
git clone https://github.com/your-username/caredesk-ai
cd caredesk-ai

pip install -r requirements.txt

cp .env.example .env
# Fill in your ANTHROPIC_API_KEY and Gmail credentials

python main.py
```

---

## Example Conversations

**Emergency path:**
```
You: I have severe chest pain radiating to my left arm
CareDesk: I hear you — this sounds serious. Please stop what you're doing and sit down. 
          Chew an aspirin if you have one and aren't allergic, and call 911 now. 
          I'm flagging this as an emergency. Can I get your address and a contact number 
          so our care team can reach you immediately?
```

**Routine path:**
```
You: I've had a rash on my arm for about a week, it's a bit itchy
CareDesk: Hi! I'm CareDesk. Could I get your name first?

You: Sarah
CareDesk: Hi Sarah — a week-long itchy rash is definitely worth getting checked out. 
          I'm going to route you to our Dermatology team. What's the best time for 
          an appointment, and do you have a preferred contact number?
```

---

## Why This Is "Red Zone"

This isn't a simple FAQ chatbot. It:

- **Orchestrates 3 specialized agents** with distinct roles and prompts
- **Makes real-time routing decisions** based on natural language understanding
- **Handles adversarial inputs** — a patient saying "I'm fine, just checking" when describing chest pain
- **Triggers controlled downstream actions** — structured emails, conversation logging
- **Maintains full observability** — every decision is logged with transcript

The same architecture can be adapted for: aged care intake, insurance claims triage, mental health crisis lines, hospital discharge coordination.

---

## File Structure

```
caredesk-ai/
├── main.py               ← CLI entry point
├── orchestrator.py       ← Agent routing + email triggers + logging
├── SOUL.md               ← Shared persona and rules for all agents
├── bots/
│   ├── symptom_bot.py    ← Intake agent (JSON output)
│   ├── triage_bot.py     ← Emergency handler
│   └── appointment_bot.py← Scheduler
├── utils/
│   ├── models.py         ← PatientContext, Urgency, Department enums
│   ├── email_sender.py   ← Email dispatch (coordinator + patient)
│   └── logger.py         ← Rich console logging
├── logs/                 ← Auto-created, conversation history JSON
├── .env.example
└── requirements.txt
```
