"""Question matching: keyword patterns for 4 question types + column.   OWNER: Aditya

No language model. parse_question(text) -> Question(intent, column) with the column
as the user means it (1-7). answers.py converts it to 0-6.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from enum import Enum


class Intent(str, Enum):
    WHY = "why"
    WHY_NOT = "why_not"
    WHAT_IF = "what_if"
    WHO_WINNING = "who_winning"


def valid_column(column) -> bool:
    """Columns typed by the user are 1..7 (the agent's code uses 0..6)."""
    return type(column) is int and 1 <= column <= 7


HELP = ('Ask "why did you play there?", "why not column 5?", '
        '"what if I play column 3?", or "who is winning?". Columns are 1 to 7.')


class QuestionError(ValueError):
    pass


@dataclass(frozen=True)
class Question:
    intent: Intent
    column: int | None = None

    def __post_init__(self):
        try:
            object.__setattr__(self, "intent", Intent(self.intent))
        except (TypeError, ValueError) as exc:
            raise QuestionError(HELP) from exc
        needs_column = self.intent in (Intent.WHY_NOT, Intent.WHAT_IF)
        if needs_column and not valid_column(self.column):
            raise QuestionError("Choose one column from 1 to 7. " + HELP)
        if not needs_column and self.column is not None:
            raise QuestionError("This question does not take a column. " + HELP)


WORDS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
         "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
         "ten": 10, "first": 1, "second": 2, "third": 3, "fourth": 4,
         "fifth": 5, "sixth": 6, "seventh": 7}
WORD = "|".join(WORDS)
DIGITS = r"(?<!\w)(-?\d+)(?:st|nd|rd|th)?(?!\w)"
# A number WORD only counts next to "column"/"col"/"c" ("column five", "fifth column"),
# so "what if I play column 3 first?" is column 3, not 3 and 1. Digits count anywhere.
WORD_NEXT_TO_COLUMN = (r"\b(?:col(?:umn)?\.?|c)\s+(" + WORD + r")\b|"
                       r"\b(" + WORD + r")\s+col(?:umn)?\b")
ALIASES = {"middle": 4, "center": 4, "centre": 4, "leftmost": 1, "rightmost": 7,
           "last": 7}


def _column(text: str) -> int:
    if re.search(r"\d\s*[.,]\s*\d|\-\s+\d", text) or \
            re.search(r"\b(?:" + WORD + r"|\d+)\s+point\s+(?:" + WORD + r"|\d+)\b", text):
        raise QuestionError("Use one whole-number column from 1 to 7. " + HELP)
    values = []
    numeric_text = text
    for token, column in ALIASES.items():
        # In "the middle one", 'one' is a pronoun, not column 1.
        pattern = r"\b" + token + r"(?:\s+(?:one|column))?\b"
        if re.search(pattern, numeric_text):
            values.append(column)
            numeric_text = re.sub(pattern, " ", numeric_text)
    for match in re.finditer(WORD_NEXT_TO_COLUMN, numeric_text):
        values.append(WORDS[match.group(1) or match.group(2)])
    for match in re.finditer(DIGITS, numeric_text):
        values.append(int(match.group(1)))
    if not values:
        raise QuestionError("Specify a column, for example 'column 5'. " + HELP)
    if any(not valid_column(value) for value in values):
        raise QuestionError("Columns must be between 1 and 7. " + HELP)
    if len(set(values)) != 1:
        raise QuestionError("Ask about one column at a time. " + HELP)
    return values[0]


def parse_question(text: str) -> Question:
    if not isinstance(text, str) or not text.strip() or len(text) > 500:
        raise QuestionError(HELP)
    text = unicodedata.normalize("NFKC", text).lower().replace("’", "'")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\b(col(?:umn)?|c)\.?(?=\d)", r"\1 ", text)  # col5 -> col 5
    # Reject multiple questions, including attempts to hide an invalid column.
    matches = []
    if re.search(r"\bwhy\s+not\b|\bwhy\s+(?:didn't|didnt|did not)\s+you\b|"
                 r"\bwhy\s+did\s+you\s+not\b", text):
        matches.append(Intent.WHY_NOT)
    if re.search(r"\bwhat\s+if\b|\bwhat\s+(?:would\s+)?happens?\s+if\b", text):
        matches.append(Intent.WHAT_IF)
    if re.search(r"\bwho(?:'s|\s+is)?\s+(?:currently\s+)?winning\b|"
                 r"\bwho(?:'s|\s+is)\s+ahead\b|\bwho\s+(?:will|is\s+going\s+to)\s+win\b|"
                 r"\bhow\s+(?:am\s+i|are\s+we)\s+doing\b|"
                 r"\bwho\s+has\s+the\s+(?:advantage|edge)\b|"
                 r"\b(?:am\s+i\s+winning|are\s+you\s+winning)\b", text):
        matches.append(Intent.WHO_WINNING)
    if re.search(r"\bwhy\s+(?:did\s+you\s+(?:play|choose|pick|move)|"
                 r"this\s+move|that\s+move|there)\b|"
                 r"\bwhy\s+did\s+you\s+do\s+(?:that|this|it)\b|"
                 r"\bexplain\s+(?:your|that|this|the)\s+move\b|"
                 r"\b(?:your|the)\s+reason(?:ing|s)?\b", text) or text.rstrip(" ?.! ") == "why":
        matches.append(Intent.WHY)
    if not matches:
        raise QuestionError("I can only answer a few kinds of questions. " + HELP)
    if len(matches) > 1:
        raise QuestionError("Ask one supported question at a time. " + HELP)
    intent = matches[0]
    if intent == Intent.WHAT_IF and re.search(r"\bif\s+(?:you|the\s+ai)\b", text):
        raise QuestionError('For my alternative moves, ask "why not column 5?". '
                            'For your next move, ask "what if I play column 3?".')
    if intent in (Intent.WHY_NOT, Intent.WHAT_IF):
        return Question(intent, _column(text))
    # "Why did you play column 5?" is ambiguous when 5 wasn't the last move.
    if intent == Intent.WHY and re.search(r"\b(?:col(?:umn)?\.?\s*|[0-9])", text):
        raise QuestionError('For the last move, ask "why did you play there?". '
                            'For another column, ask "why not column 5?".')
    return Question(intent)
