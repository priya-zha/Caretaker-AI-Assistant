"""
Run all CareDesk evals in one go.

Usage:
    cd caredesk-ai-v2
    python eval/run_all.py

Or run individual test files:
    inspect eval eval/test_routing.py --model anthropic/claude-sonnet-4-6
    inspect eval eval/test_safety.py  --model anthropic/claude-sonnet-4-6
    inspect eval eval/test_tone.py    --model anthropic/claude-sonnet-4-6
    inspect eval eval/test_field_extraction.py --model anthropic/claude-sonnet-4-6
    inspect eval eval/test_cancellation.py     --model anthropic/claude-sonnet-4-6
"""

import subprocess
import sys

MODEL = "anthropic/claude-sonnet-4-6"

EVAL_FILES = [
    ("Routing — urgency & department", "eval/test_routing.py"),
    ("Safety — 911, no diagnosis, no advice", "eval/test_safety.py"),
    ("Tone — empathy, no 'Great!' for pain", "eval/test_tone.py"),
    ("Field extraction — name/phone/email/address", "eval/test_field_extraction.py"),
    ("Cancellation flow", "eval/test_cancellation.py"),
]

print("\n" + "="*60)
print("  CareDesk AI — Inspect Evaluation Suite")
print("="*60 + "\n")

for label, path in EVAL_FILES:
    print(f"Running: {label}")
    print(f"  File : {path}")
    result = subprocess.run(
        ["inspect", "eval", path, "--model", MODEL],
        capture_output=False,
    )
    if result.returncode != 0:
        print(f"  [FAILED] {label}\n")
    else:
        print(f"  [DONE]   {label}\n")

print("="*60)
print("All evals complete. View results: inspect view")
print("="*60 + "\n")
