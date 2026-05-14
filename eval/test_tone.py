"""
Eval 3 — Tone and empathy
Tests that the bot responds with appropriate warmth and never uses
dismissive language like "Great!" or "Perfect!" when patients report pain.

Run: inspect eval eval/test_tone.py --model anthropic/claude-sonnet-4-6
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from inspect_ai import task, Task
from inspect_ai.dataset import Sample
from inspect_ai.solver import generate, system_message
from inspect_ai.scorer import model_graded_qa

from bots.symptom_bot import SYSTEM as SYMPTOM_SYSTEM


# ── No "Great!" for pain ──────────────────────────────────────────────────────

@task
def test_no_positive_response_to_pain():
    """Bot must not say 'Great!', 'Perfect!', or 'Wonderful!' when patient reports pain or high severity."""
    return Task(
        dataset=[
            Sample(
                input="My pain is 5 out of 5, it's unbearable",
                target="The response must NOT contain words like 'Great', 'Perfect', 'Wonderful', 'Excellent', or 'Fantastic'. "
                       "It should be empathetic — something like 'I'm sorry to hear that' or 'Thank you for letting me know'.",
            ),
            Sample(
                input="The rash is spreading and getting worse, I'm very worried",
                target="The response must be reassuring and empathetic. "
                       "It must NOT use words like 'Great!' or 'Perfect!' in response to this distressing news.",
            ),
            Sample(
                input="I've had this headache for 5 days straight, severity 4 out of 5",
                target="The response must NOT say 'Great!' or 'Perfect!' after hearing about 5 days of pain. "
                       "It should express empathy.",
            ),
            Sample(
                input="I can barely walk, the knee pain is a 5 out of 5",
                target="The response must be empathetic and must NOT use celebratory language like 'Great!' or 'Excellent!'.",
            ),
        ],
        solver=[
            system_message(SYMPTOM_SYSTEM),
            generate(),
        ],
        scorer=model_graded_qa(
            instructions="Does the response avoid saying 'Great!', 'Perfect!', 'Wonderful!', 'Excellent!', "
                         "or similar positive exclamations in reaction to the patient reporting pain or distress? "
                         "Answer 'correct' if the tone is appropriately empathetic. "
                         "Answer 'incorrect' if it uses any cheerful exclamation after hearing about pain."
        ),
    )


# ── Empathy check ─────────────────────────────────────────────────────────────

@task
def test_empathy_for_anxious_patients():
    """Bot should be warm and reassuring when patients express fear or anxiety."""
    return Task(
        dataset=[
            Sample(
                input="I'm really scared, I've never had chest pain like this before",
                target="The response should acknowledge the patient's fear and be reassuring. "
                       "It should not be cold or clinical. It should express care.",
            ),
            Sample(
                input="I'm worried about my child, they have a very high fever",
                target="The response should be empathetic and acknowledge the parent's concern. "
                       "It should be warm and reassuring while gathering information.",
            ),
            Sample(
                input="I don't know what's wrong with me, I feel terrible",
                target="The response should be gentle and reassuring. "
                       "It should not immediately fire a series of clinical questions — "
                       "it should first acknowledge how the patient feels.",
            ),
        ],
        solver=[
            system_message(SYMPTOM_SYSTEM),
            generate(),
        ],
        scorer=model_graded_qa(
            instructions="Is the response appropriately empathetic and warm toward a patient who is scared or anxious? "
                         "Answer 'correct' if the bot acknowledges the patient's feelings before asking clinical questions. "
                         "Answer 'incorrect' if the response is cold, robotic, or jumps straight to clinical questions "
                         "without any acknowledgment of the patient's emotional state."
        ),
    )


# ── One question at a time ────────────────────────────────────────────────────

@task
def test_one_question_at_a_time():
    """Bot must ask only one question per response, not a list of questions."""
    return Task(
        dataset=[
            Sample(
                input="I have a rash",
                target="The response should ask exactly ONE follow-up question. "
                       "It should NOT ask multiple questions at once like "
                       "'What does it look like? How long have you had it? Is it spreading?'",
            ),
            Sample(
                input="I've been feeling unwell",
                target="The response should ask ONE focused question to understand what's wrong. "
                       "It must not bombard the patient with multiple questions in one message.",
            ),
            Sample(
                input="I have pain in my stomach",
                target="The response should ask ONE clarifying question — "
                       "either about severity, duration, location, or nature of pain — not all at once.",
            ),
        ],
        solver=[
            system_message(SYMPTOM_SYSTEM),
            generate(),
        ],
        scorer=model_graded_qa(
            instructions="Does the response ask only ONE question? "
                         "Answer 'correct' if there is exactly one question in the reply_to_patient field. "
                         "Answer 'incorrect' if there are two or more questions asked at once."
        ),
    )
