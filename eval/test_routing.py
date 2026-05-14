"""
Eval 1 — Routing accuracy
Tests that the symptom bot classifies urgency and department correctly.

Run: inspect eval eval/test_routing.py --model anthropic/claude-sonnet-4-6
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from inspect_ai import task, Task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.solver import generate, system_message
from inspect_ai.scorer import includes

from bots.symptom_bot import SYSTEM as SYMPTOM_SYSTEM


@task
def test_emergency_routing():
    """Obvious emergencies should be classified as EMERGENCY immediately."""
    return Task(
        dataset=MemoryDataset([
            Sample(
                input="I have severe chest pain and can't breathe",
                target="EMERGENCY",
            ),
            Sample(
                input="I think I'm having a stroke, my left side is numb and I can't speak",
                target="EMERGENCY",
            ),
            Sample(
                input="I took a lot of pills, I don't feel well",
                target="EMERGENCY",
            ),
            Sample(
                input="I'm having a heart attack, crushing chest pressure",
                target="EMERGENCY",
            ),
            Sample(
                input="I can't breathe at all, it's getting worse fast",
                target="EMERGENCY",
            ),
        ]),
        solver=[
            system_message(SYMPTOM_SYSTEM),
            generate(),
        ],
        scorer=includes(),
    )


@task
def test_routine_routing():
    """Mild symptoms should be classified as ROUTINE."""
    return Task(
        dataset=MemoryDataset([
            Sample(
                input="I have a small rash on my arm for 2 days, mild itching",
                target="ROUTINE",
            ),
            Sample(
                input="I need a prescription refill for my blood pressure medication",
                target="ROUTINE",
            ),
            Sample(
                input="I have a mild headache since this morning",
                target="ROUTINE",
            ),
            Sample(
                input="I want to book a general checkup",
                target="ROUTINE",
            ),
            Sample(
                input="I have a follow-up appointment needed after my last visit",
                target="ROUTINE",
            ),
        ]),
        solver=[
            system_message(SYMPTOM_SYSTEM),
            generate(),
        ],
        scorer=includes(),
    )


@task
def test_urgent_routing():
    """High fever, severe pain, spreading infections should be URGENT."""
    return Task(
        dataset=MemoryDataset([
            Sample(
                input="I have a fever of 104F since yesterday and it's getting worse",
                target="URGENT",
            ),
            Sample(
                input="I have severe abdominal pain, 8 out of 10, since this morning",
                target="URGENT",
            ),
            Sample(
                input="I have a spreading red infection on my leg, it's getting bigger and warm",
                target="URGENT",
            ),
            Sample(
                input="My eczema is flaring up very badly, I can't sleep from the itching, severity 5 out of 5",
                target="URGENT",
            ),
        ]),
        solver=[
            system_message(SYMPTOM_SYSTEM),
            generate(),
        ],
        scorer=includes(),
    )


@task
def test_department_routing():
    """Specific symptoms should map to the right department."""
    return Task(
        dataset=MemoryDataset([
            Sample(
                input="I have heart palpitations and feel dizzy when I stand",
                target="Cardiology",
            ),
            Sample(
                input="I have eczema flaring up on my hands",
                target="Dermatology",
            ),
            Sample(
                input="I have a skin rash spreading across my chest",
                target="Dermatology",
            ),
            Sample(
                input="I have chest tightness and shortness of breath during exercise",
                target="Cardiology",
            ),
            Sample(
                input="I have a bad cold and sore throat for 3 days",
                target="General Practice",
            ),
        ]),
        solver=[
            system_message(SYMPTOM_SYSTEM),
            generate(),
        ],
        scorer=includes(),
    )
