"""
Eval 5 — Cancellation flow
Tests that the cancellation bot asks for the right identifier,
handles missing appointments gracefully, and confirms clearly.

Run: inspect eval eval/test_cancellation.py --model anthropic/claude-sonnet-4-6
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from inspect_ai import task, Task
from inspect_ai.dataset import Sample
from inspect_ai.solver import generate, system_message
from inspect_ai.scorer import includes, model_graded_qa

from bots.cancellation_bot import SYSTEM as CANCEL_SYSTEM


SYSTEM_WITH_APPOINTMENT = CANCEL_SYSTEM + """

APPOINTMENTS FOUND FOR THIS PATIENT:
- Appointment ID: APT-3F9A2B | Dr. Sarah Chen (Dermatology) | Wednesday, May 14 at 9:00 AM

Use the appointment_id from above when the patient confirms cancellation.
"""


# ── Asks for identifier ───────────────────────────────────────────────────────

@task
def test_asks_for_email_or_phone():
    """Bot should ask for email or phone to look up the appointment."""
    return Task(
        dataset=[
            Sample(
                input="I want to cancel my appointment",
                target="The response should ask for the patient's email address or phone number "
                       "to look up their appointment. It should NOT ask for name or date of birth first.",
            ),
            Sample(
                input="cancel",
                target="email or phone",
            ),
            Sample(
                input="I need to reschedule",
                target="The response should ask for email or phone number to find the appointment.",
            ),
        ],
        solver=[
            system_message(CANCEL_SYSTEM),
            generate(),
        ],
        scorer=model_graded_qa(
            instructions="Does the response ask the patient for their email address or phone number? "
                         "Answer 'correct' if it asks for email or phone. "
                         "Answer 'incorrect' if it asks for something else first or skips straight to cancellation."
        ),
    )


# ── Shows appointment details before cancelling ───────────────────────────────

@task
def test_shows_appointment_before_cancelling():
    """Bot must show appointment details and ask for confirmation before cancelling."""
    return Task(
        dataset=[
            Sample(
                input="pj35134@gmail.com",
                target="APT-3F9A2B",   # appointment ID should be shown
            ),
            Sample(
                input="my email is pj35134@gmail.com",
                target="Dr. Sarah Chen",  # doctor name should appear
            ),
            Sample(
                input="6824083705",
                target="Wednesday",   # date should appear
            ),
        ],
        solver=[
            system_message(SYSTEM_WITH_APPOINTMENT),
            generate(),
        ],
        scorer=includes(),
    )


# ── Asks for confirmation ─────────────────────────────────────────────────────

@task
def test_asks_for_confirmation():
    """Bot must ask yes/no before cancelling, not cancel immediately."""
    return Task(
        dataset=[
            Sample(
                input="pj35134@gmail.com",
                target="The response must show the appointment details and ask "
                       "'Would you like to cancel?' or similar confirmation question. "
                       "It must NOT cancel immediately without asking.",
            ),
        ],
        solver=[
            system_message(SYSTEM_WITH_APPOINTMENT),
            generate(),
        ],
        scorer=model_graded_qa(
            instructions="Does the response show the appointment details AND ask for confirmation "
                         "before cancelling? Answer 'correct' if it asks 'yes or no' or similar. "
                         "Answer 'incorrect' if it cancels immediately without asking."
        ),
    )


# ── Handles no appointment found ──────────────────────────────────────────────

@task
def test_no_appointment_found():
    """Bot should handle gracefully when no appointment exists for the identifier."""
    return Task(
        dataset=[
            Sample(
                input="unknown@example.com",
                target="The response should say no appointment was found for that email/phone. "
                       "It should suggest contacting the clinic directly. "
                       "It must NOT crash or give an error message.",
            ),
        ],
        solver=[
            system_message(CANCEL_SYSTEM + "\n\nNo appointments found for this patient."),
            generate(),
        ],
        scorer=model_graded_qa(
            instructions="Does the response gracefully handle the case where no appointment is found? "
                         "Answer 'correct' if it apologizes and suggests contacting the clinic. "
                         "Answer 'incorrect' if it gives an error, crashes, or pretends to cancel something."
        ),
    )
