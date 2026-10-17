"""Test-only: what Aava must never say aloud (spoken text of the company answers and the feed answer)."""
import re

QUESTIONS = ("Aava, what do you think about this company?", "What is their official score on the report?", "How sure are you?",
             "Who should we meet, and what do we say?", "What is the next move?", "What would change your mind?")
FEED_QUESTION = "Aava, what is new this week?"

# plain substrings (the owner's list, plus the next-step line the old reader spoke for a company with a verdict)
SUBSTRINGS = ("http", "www.", "fallback c", "type 6_", "keyword '", "dataset match", "Question", "[name redacted]",
              "Watch: not enough public evidence")
# patterns: a capability or rule id (C3, C10, rule e), a register id (seven digits, a dash, a check digit), a long dash
PATTERNS = (re.compile(r"\bC\d{1,2}\b"), re.compile(r"\b\d{7}-\d\b"), re.compile(r"\b[Rr]ule [a-g1-9]\b"), re.compile(r"\b[Rr]ow \d+\b"),
            re.compile("[–—]"))


def dirty(text: str) -> list[str]:
    """Everything in `text` that a listener must not hear; empty when the text is clean."""
    return [s for s in SUBSTRINGS if s in text] + [p.pattern for p in PATTERNS if p.search(text)]
