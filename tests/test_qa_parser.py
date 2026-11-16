"""Tests for the question parser (c4/qa/parser.py).            OWNER: Aditya"""
import unittest

from c4.qa.parser import Intent, QuestionError, parse_question


class ParserTests(unittest.TestCase):
    def test_supported_questions_and_column_aliases(self):
        cases = [("WHY DID YOU PLAY THERE?!", Intent.WHY, None),
                 ("Why this move?", Intent.WHY, None),
                 ("why", Intent.WHY, None),
                 ("Why not col. 5?", Intent.WHY_NOT, 5),
                 ("Why didn’t you play column five?", Intent.WHY_NOT, 5),
                 ("Why did you not choose the middle one?", Intent.WHY_NOT, 4),
                 ("what if I play the centre?", Intent.WHAT_IF, 4),
                 ("what if I play the middle one?", Intent.WHAT_IF, 4),
                 ("what if I play the rightmost column?", Intent.WHAT_IF, 7),
                 ("what happens if I play the first column?", Intent.WHAT_IF, 1),
                 ("what would happen if I played column seven?", Intent.WHAT_IF, 7),
                 ("Who's winning?", Intent.WHO_WINNING, None),
                 ("who is currently winning?", Intent.WHO_WINNING, None),
                 ("am I winning?", Intent.WHO_WINNING, None)]
        for text, intent, column in cases:
            with self.subTest(text=text):
                question = parse_question(text)
                self.assertEqual((question.intent, question.column), (intent, column))

    def test_invalid_ambiguous_and_unsupported_questions(self):
        cases = [None, 12, "", "   ", "hello", "tell me a joke", "what if?",
                 "why not column zero?", "why not column 8?", "why not column -1?",
                 "what if I play 4.4?", "what if I play - 1?",
                 "why not 2 or 5?", "why not centre column 5?",
                 "who is winning and why not column 3?",
                 "what if you play column 3?",
                 "why did you play column 5?", "x" * 501]
        for text in cases:
            with self.subTest(text=text):
                with self.assertRaises(QuestionError):
                    parse_question(text)

    def test_robustness_corpus(self):
        """Over 100 question variants with explicit expected parse outcomes."""
        cases = []
        words = ("one", "two", "three", "four", "five", "six", "seven")
        for column, word in enumerate(words, 1):
            for prefix, intent in (("why not", Intent.WHY_NOT),
                                   ("what if I play", Intent.WHAT_IF)):
                for token in (str(column), word):
                    for suffix in ("?", "!!!", ""):
                        cases.append((f"{prefix} column {token}{suffix}", intent, column))
        for invalid in ("0", "8", "9", "-1", "99", "zero", "eight", "nine", "ten"):
            for prefix in ("why not", "what if I play"):
                cases.append((f"{prefix} column {invalid}?", None, None))
        for text in ("banana", "why not?", "what if I play?", "who won the election?",
                     "why not 1 and 7?", "what if 2 or 6?", "who is winning? why there?",
                     "what if column 4.4?", "what if column 3,3?", "   "):
            cases.append((text, None, None))
        self.assertGreaterEqual(len(cases), 100)
        for text, intent, column in cases:
            with self.subTest(text=text):
                if intent is None:
                    with self.assertRaises(QuestionError):
                        parse_question(text)
                else:
                    result = parse_question(text)
                    self.assertEqual((result.intent, result.column), (intent, column))

    def test_phrasings_added_after_review(self):
        cases = [("what if I played col5", Intent.WHAT_IF, 5),
                 ("why not column5?", Intent.WHY_NOT, 5),
                 ("what if c3", Intent.WHAT_IF, 3),
                 ("who's ahead?", Intent.WHO_WINNING, None),
                 ("who will win?", Intent.WHO_WINNING, None),
                 ("how am I doing?", Intent.WHO_WINNING, None),
                 ("explain your move", Intent.WHY, None),
                 ("why did you do that?", Intent.WHY, None)]
        for text, intent, column in cases:
            with self.subTest(text=text):
                q = parse_question(text)
                self.assertEqual((q.intent, q.column), (intent, column))
