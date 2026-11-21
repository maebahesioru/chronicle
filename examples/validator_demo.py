"""Show the citation contract in ten lines.

Run from the repository root:

    ./.venv/bin/python examples/validator_demo.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chronicle.core.cite import Evidence, enforce, inspect_sentence

EVIDENCE = Evidence(
    shas=["22188d1"],
    paths=["chronicle/html.py"],
    issues=["#12"],
)

GOOD = "The offline player landed in chronicle/html.py at 22188d1."
NO_CITATION = "We refactored everything for clarity and future extensibility."
FABRICATED = "The parser rewrite landed in src/core/parser.py at deadbeef00."


def show(label, sentence):
    verdict = inspect_sentence(sentence, EVIDENCE)
    state = "accepted" if verdict.ok else "rejected"
    print(f"{label:14} {state:9} reason={verdict.reason}")
    if verdict.unknown:
        print(f"{'':14} unknown={[citation.label for citation in verdict.unknown]}")


show("cited", GOOD)
show("no citation", NO_CITATION)
show("fabricated", FABRICATED)

repaired = enforce(
    FABRICATED,
    EVIDENCE,
    regenerate=lambda index, previous: GOOD,
)
print(f"repair loop    kept={repaired.kept} dropped={len(repaired.dropped)} regenerated={repaired.regenerated}")

dropped = enforce(NO_CITATION, EVIDENCE)
print(f"no fallback    kept={dropped.kept} dropped={len(dropped.dropped)} reason={dropped.dropped[0]['reason']}")
