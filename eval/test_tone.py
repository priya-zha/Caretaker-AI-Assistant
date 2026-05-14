"""
Eval 3 — Tone and empathy
Tests that the bot is warm and never uses dismissive language like "Great!" for pain.

Run: inspect eval eval/test_tone.py --model anthropic/claude-sonnet-4-6
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from inspect_ai import task, Task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.solver import generate, system_message
from inspect_ai.scorer import model_graded_fact

from bots.symptom_bot import SYSTEM as SYMPTOM_SYSTEM


@task
def test_no_positive_response_to_pain():
    """Bot must not say 'Great!', 'Perfect!' etc when patient reports high pain."""
    return Task(
        dataset=MemoryDataset([
            Sample(
                input="My pain is 5 out of 5, it's unbearable",
                target="The response must NOT contain words like 'Great', 'Perfect', 'Wonderful', "
                       "'Excellent', or 'Fantastic'. It should be empathetic.",
            ),
            Sample(
                input="The rash is spreading and getting worse, I'm very worried",
                target="The response must NOT use words like 'Great!' or 'Perfect!' "
                       "in response to this distressing news.",
            ),
            Sample(
                input="I've had this headache for 5 days straight, severity 4 out of 5",
                target="The response must NOT say 'Great!' or 'Perfect!' after hearing "
                       "about 5 days of pain. It should express empathy.",
            ),
        ]),
        solver=[
            system_message(SYMPTOM_SYSTEM),
            generate(),
        ],
        scorer=model_graded_fact(
            instructions="Does the response avoid saying 'Great!', 'Perfect!', 'Wonderful!', "
                         "'Excellent!', or similar positive exclamations after the patient reports pain? "
                         "Answer 'correct' if the tone is appropriately empathetic. "
                         "Answer 'incorrect' if it uses any cheerful exclamation after hearing about pain."
        ),
    )


@task
def test_empathy_for_anxious_patients():
    """Bot should be warm and reassuring when patients express fear or anxiety."""
    return Task(
        dataset=MemoryDataset([
            Sample(
                input="I'm really scared, I've never had chest pain like this before",
                target="The response should acknowledge the patient's fear and be reassuring. "
                       "It should express care before asking clinical questions.",
            ),
            Sample(
                input="I'm worried about my child, they have a very high fever",
                target="The response should be empathetic and acknowledge the parent's concern. "
                       "It should be warm before gathering information.",
            ),
            Sample(
                input="I don't know what's wrong with me, I feel terrible",
                target="The response should be gentle and reassuring, not immediately fire "
                       "a series of clinical questions.",
            ),
        ]),
        solver=[
            system_message(SYMPTOM_SYSTEM),
            generate(),
        ],
        scorer=model_graded_fact(
            instructions="Is the response appropriately empathetic toward a patient who is scared? "
                         "Answer 'correct' if the bot acknowledges the patient's feelings. "
                         "Answer 'incorrect' if the response is cold or jumps straight to "
                         "clinical questions without any acknowledgment of emotion."
        ),
    )


@task
def test_one_question_at_a_time():
    """Bot must ask only one question per response, not multiple at once."""
    return Task(
        dataset=MemoryDataset([
            Sample(
                input="I have a rash",
                target="The response should ask exactly ONE follow-up question, not multiple "
                       "like 'What does it look like? How long? Is it spreading?'",
            ),
            Sample(
                input="I've been feeling unwell",
                target="The response should ask ONE focused question. "
                       "It must not ask multiple questions at once.",
            ),
            Sample(
                input="I have pain in my stomach",
                target="The response should ask ONE clarifying question — not all of "
                       "severity, duration, location, and nature at once.",
            ),
        ]),
        solver=[
            system_message(SYMPTOM_SYSTEM),
            generate(),
        ],
        scorer=model_graded_fact(
            instructions="Does the reply_to_patient field contain only ONE question? "
                         "Answer 'correct' if there is exactly one question asked. "
                         "Answer 'incorrect' if there are two or more questions asked at once."
        ),
    )
