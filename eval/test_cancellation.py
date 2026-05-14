"""
Eval 5 — Cancellation flow
Tests the cancellation bot asks for the right info, shows details, and confirms.

Run: inspect eval eval/test_cancellation.py --model anthropic/claude-sonnet-4-6
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from inspect_ai import task, Task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.solver import generate, system_message
from inspect_ai.scorer import includes, model_graded_fact

from bots.cancellation_bot import SYSTEM as CANCEL_SYSTEM


SYSTEM_WITH_APPOINTMENT = CANCEL_SYSTEM + """

APPOINTMENTS FOUND FOR THIS PATIENT:
- Appointment ID: APT-3F9A2B | Dr. Sarah Chen (Dermatology) | Wednesday, May 14 at 9:00 AM

Use the appointment_id from above when the patient confirms cancellation.
"""

SYSTEM_NO_APPOINTMENT = CANCEL_SYSTEM + """

No appointments found for this patient.
"""


@task
def test_asks_for_email_or_phone():
    """Bot should ask for email or phone to look up the appointment."""
    return Task(
        dataset=MemoryDataset([
            Sample(input="I want to cancel my appointment", target="email or phone"),
            Sample(input="cancel",                          target="email or phone"),
            Sample(input="I need to reschedule",            target="email or phone"),
        ]),
        solver=[system_message(CANCEL_SYSTEM), generate()],
        scorer=model_graded_fact(
            instructions="Does the response ask the patient for their email address or phone number? "
                         "Answer 'correct' if it asks for email or phone. "
                         "Answer 'incorrect' if it asks for something else first or skips the lookup."
        ),
    )


@task
def test_shows_appointment_before_cancelling():
    """Bot must show appointment details before cancelling."""
    return Task(
        dataset=MemoryDataset([
            Sample(input="pj35134@gmail.com", target="APT-3F9A2B"),
            Sample(input="my email is pj35134@gmail.com", target="Dr. Sarah Chen"),
            Sample(input="6824083705",                    target="Wednesday"),
        ]),
        solver=[system_message(SYSTEM_WITH_APPOINTMENT), generate()],
        scorer=includes(),
    )


@task
def test_asks_for_confirmation():
    """Bot must ask yes/no confirmation before cancelling."""
    return Task(
        dataset=MemoryDataset([
            Sample(
                input="pj35134@gmail.com",
                target="The response must show appointment details and ask for confirmation "
                       "('Would you like to cancel?' or similar). It must NOT cancel immediately.",
            ),
        ]),
        solver=[system_message(SYSTEM_WITH_APPOINTMENT), generate()],
        scorer=model_graded_fact(
            instructions="Does the response show appointment details AND ask for confirmation before cancelling? "
                         "Answer 'correct' if it asks 'yes or no' or similar confirmation. "
                         "Answer 'incorrect' if it cancels immediately without asking."
        ),
    )


@task
def test_no_appointment_found():
    """Bot handles gracefully when no appointment exists."""
    return Task(
        dataset=MemoryDataset([
            Sample(
                input="unknown@example.com",
                target="The response should say no appointment was found and suggest "
                       "contacting the clinic directly. It must not crash or give an error.",
            ),
        ]),
        solver=[system_message(SYSTEM_NO_APPOINTMENT), generate()],
        scorer=model_graded_fact(
            instructions="Does the response gracefully handle no appointment found? "
                         "Answer 'correct' if it apologizes and suggests contacting the clinic. "
                         "Answer 'incorrect' if it errors, crashes, or pretends to cancel something."
        ),
    )
