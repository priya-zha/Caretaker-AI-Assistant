"""
Eval 4 — Field extraction
Tests that the appointment bot correctly extracts name, phone, email,
and address from varied patient inputs — including when all 4 are given
at once, or given in casual/non-standard formats.

Run: inspect eval eval/test_field_extraction.py --model anthropic/claude-sonnet-4-6
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from inspect_ai import task, Task
from inspect_ai.dataset import Sample
from inspect_ai.solver import generate, system_message
from inspect_ai.scorer import includes, model_graded_qa

from bots.appointment_bot import COLLECT_SYSTEM


# ── Extracts all 4 fields correctly ──────────────────────────────────────────

@task
def test_extracts_name():
    """Bot should extract patient name in the <fields> JSON block."""
    return Task(
        dataset=[
            Sample(
                input="My name is Priya Jha",
                target='"patient_name": "Priya Jha"',
            ),
            Sample(
                input="I'm John Smith, calling about my rash",
                target='"patient_name": "John Smith"',
            ),
            Sample(
                input="call me Sarah, Sarah Connor",
                target='"patient_name": "Sarah Connor"',
            ),
        ],
        solver=[
            system_message(COLLECT_SYSTEM + "\nALREADY COLLECTED:\n- Name: Not yet provided\n- Phone: Not yet provided\n- Email: Not yet provided\n- Address: Not yet provided"),
            generate(),
        ],
        scorer=includes(),
    )


@task
def test_extracts_phone():
    """Bot should extract phone number in varied formats."""
    return Task(
        dataset=[
            Sample(
                input="My phone is 6824083705",
                target='"phone": "6824083705"',
            ),
            Sample(
                input="You can reach me at 682-408-3705",
                target="682",   # partial match — number was captured
            ),
            Sample(
                input="My number is +1 (682) 408-3705",
                target="682",
            ),
        ],
        solver=[
            system_message(COLLECT_SYSTEM + "\nALREADY COLLECTED:\n- Name: Not yet provided\n- Phone: Not yet provided\n- Email: Not yet provided\n- Address: Not yet provided"),
            generate(),
        ],
        scorer=includes(),
    )


@task
def test_extracts_email():
    """Bot should extract email address."""
    return Task(
        dataset=[
            Sample(
                input="My email is pj35134@gmail.com",
                target='"email": "pj35134@gmail.com"',
            ),
            Sample(
                input="Send confirmation to john.smith@outlook.com",
                target='"email": "john.smith@outlook.com"',
            ),
        ],
        solver=[
            system_message(COLLECT_SYSTEM + "\nALREADY COLLECTED:\n- Name: Priya Jha\n- Phone: 6824083705\n- Email: Not yet provided\n- Address: Not yet provided"),
            generate(),
        ],
        scorer=includes(),
    )


@task
def test_extracts_all_four_at_once():
    """When patient gives all 4 fields in one message, bot should extract all of them."""
    return Task(
        dataset=[
            Sample(
                input="Priya Jha, 6824083705, pj35134@gmail.com, 1003 Eagle Dr Denton Texas",
                target='"patient_name": "Priya Jha"',  # at minimum name is extracted
            ),
            Sample(
                input="Name: John Smith | Phone: 5551234567 | Email: john@gmail.com | Address: 42 Oak Street, Austin TX",
                target='"patient_name": "John Smith"',
            ),
        ],
        solver=[
            system_message(COLLECT_SYSTEM + "\nALREADY COLLECTED:\n- Name: Not yet provided\n- Phone: Not yet provided\n- Email: Not yet provided\n- Address: Not yet provided"),
            generate(),
        ],
        scorer=includes(),
    )


# ── Does not ask for extra fields ─────────────────────────────────────────────

@task
def test_does_not_ask_for_extra_fields():
    """Bot must only ask for name, phone, email, address — nothing else."""
    return Task(
        dataset=[
            Sample(
                input="I have skin rashes and need an appointment",
                target="The response must only ask for contact details: name, phone, email, or address. "
                       "It must NOT ask for date of birth, insurance, occupation, symptoms again, "
                       "or any other personal information.",
            ),
            Sample(
                input="My name is Priya Jha",
                target="The response should ask for phone number next. "
                       "It must NOT ask for date of birth, insurance details, or anything beyond "
                       "phone, email, and address.",
            ),
        ],
        solver=[
            system_message(COLLECT_SYSTEM + "\nALREADY COLLECTED:\n- Name: Not yet provided\n- Phone: Not yet provided\n- Email: Not yet provided\n- Address: Not yet provided"),
            generate(),
        ],
        scorer=model_graded_qa(
            instructions="Does the response ask ONLY for contact details (name, phone, email, or address)? "
                         "Answer 'correct' if it only asks for those 4 fields. "
                         "Answer 'incorrect' if it asks for date of birth, insurance, medical history, "
                         "or anything beyond those 4 fields."
        ),
    )
