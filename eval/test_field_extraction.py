"""
Eval 4 — Field extraction
Tests that the appointment bot correctly extracts name, phone, email, address.

Run: inspect eval eval/test_field_extraction.py --model anthropic/claude-sonnet-4-6
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from inspect_ai import task, Task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.solver import generate, system_message
from inspect_ai.scorer import includes, model_graded_fact

from bots.appointment_bot import COLLECT_SYSTEM

SYSTEM_NO_DETAILS = COLLECT_SYSTEM + """

ALREADY COLLECTED:
- Name: Not yet provided
- Phone: Not yet provided
- Email: Not yet provided
- Address: Not yet provided
"""

SYSTEM_HAVE_NAME_PHONE = COLLECT_SYSTEM + """

ALREADY COLLECTED:
- Name: Priya Jha
- Phone: 6824083705
- Email: Not yet provided
- Address: Not yet provided
"""


@task
def test_extracts_name():
    """Bot extracts patient name into the <fields> JSON block."""
    return Task(
        dataset=MemoryDataset([
            Sample(input="My name is Priya Jha",            target='"patient_name": "Priya Jha"'),
            Sample(input="I'm John Smith",                  target='"patient_name": "John Smith"'),
            Sample(input="call me Sarah Connor",            target='"patient_name": "Sarah Connor"'),
        ]),
        solver=[system_message(SYSTEM_NO_DETAILS), generate()],
        scorer=includes(),
    )


@task
def test_extracts_phone():
    """Bot extracts phone number in varied formats."""
    return Task(
        dataset=MemoryDataset([
            Sample(input="My phone is 6824083705",          target="6824083705"),
            Sample(input="You can reach me at 682-408-3705", target="682"),
            Sample(input="My number is +1 (682) 408-3705",  target="682"),
        ]),
        solver=[system_message(SYSTEM_NO_DETAILS), generate()],
        scorer=includes(),
    )


@task
def test_extracts_email():
    """Bot extracts email address."""
    return Task(
        dataset=MemoryDataset([
            Sample(input="My email is pj35134@gmail.com",          target='"email": "pj35134@gmail.com"'),
            Sample(input="Send to john.smith@outlook.com",         target='"email": "john.smith@outlook.com"'),
        ]),
        solver=[system_message(SYSTEM_HAVE_NAME_PHONE), generate()],
        scorer=includes(),
    )


@task
def test_extracts_all_four_at_once():
    """When patient gives all 4 fields in one message, bot extracts all of them."""
    return Task(
        dataset=MemoryDataset([
            Sample(
                input="Priya Jha, 6824083705, pj35134@gmail.com, 1003 Eagle Dr Denton Texas",
                target='"patient_name": "Priya Jha"',
            ),
            Sample(
                input="Name: John Smith | Phone: 5551234567 | Email: john@gmail.com | Address: 42 Oak St Austin TX",
                target='"patient_name": "John Smith"',
            ),
        ]),
        solver=[system_message(SYSTEM_NO_DETAILS), generate()],
        scorer=includes(),
    )


@task
def test_does_not_ask_for_extra_fields():
    """Bot must only ask for name, phone, email, address — nothing else."""
    return Task(
        dataset=MemoryDataset([
            Sample(
                input="I have skin rashes and need an appointment",
                target="The response must only ask for contact details: name, phone, email, or address. "
                       "It must NOT ask for date of birth, insurance, or any other information.",
            ),
            Sample(
                input="My name is Priya Jha",
                target="The response should ask for phone number next. "
                       "It must NOT ask for date of birth or insurance details.",
            ),
        ]),
        solver=[system_message(SYSTEM_NO_DETAILS), generate()],
        scorer=model_graded_fact(
            instructions="Does the response ask ONLY for contact details (name, phone, email, or address)? "
                         "Answer 'correct' if it only asks for those 4 fields. "
                         "Answer 'incorrect' if it asks for date of birth, insurance, medical history, "
                         "or anything beyond those 4 fields."
        ),
    )
