import re
from typing import NamedTuple

MAX_QUESTION_LENGTH = 2000

INJECTION_PATTERNS = [
    # Classic override attempts
    r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?)",
    r"forget\s+(all\s+)?(previous|your)\s+(instructions?|training)",
    r"disregard\s+(all\s+)?(previous|prior)\s+instructions?",
    # DAN / jailbreak
    r"\bDAN\b",
    r"do\s+anything\s+now",
    r"jailbreak",
    r"pretend\s+(you\s+are|to\s+be)\s+(a\s+)?(\w+\s+)?AI\s+(without|with\s+no)",
    # Delimiter injection
    r"</?system>",
    r"\[/?INST\]",
    r"###\s*(system|instruction|prompt)",
    r"<\|im_(start|end)\|>",
    # Role manipulation
    r"you\s+are\s+now\s+(a\s+)?(different|new|other|unrestricted)",
    r"switch\s+to\s+(developer|admin|root|god)\s+mode",
    r"enable\s+(dev|debug|admin|god|unrestricted)\s+mode",
    # Prompt extraction
    r"(show|reveal|print|output|display|tell me)\s+(your|the)\s+(system\s+)?(prompt|instructions?|rules?|training)",
    r"what\s+(is|are)\s+your\s+(system\s+)?(prompt|instructions?|rules?)",
]

_compiled = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


class GuardResult(NamedTuple):
    is_safe: bool
    reason: str | None


def check_prompt_injection(text: str) -> GuardResult:
    if len(text) > MAX_QUESTION_LENGTH:
        return GuardResult(False, f"Question too long (max {MAX_QUESTION_LENGTH} chars)")

    for pattern in _compiled:
        if pattern.search(text):
            return GuardResult(False, "Potential prompt injection detected")

    return GuardResult(True, None)
