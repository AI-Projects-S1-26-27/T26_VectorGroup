# Aditya: sentence templates and question answering

## Scope and interfaces

Aditya's modules are `c4/explain/templates.py`, `c4/qa/parser.py` and
`c4/qa/answers.py`, with `tests/test_qa_parser.py` and `tests/test_qa_answers.py`.
They turn what the search and the rules found into English, and answer the four
question types from proposal sections 4.3 and 4.4.

* `templates.render(concepts, facts, trace) -> str` is called by Naman's
  `explain_move`. The other helpers (`fact_phrase`, `column_result`,
  `advantage_text`, `continuation_text`) are used by the answers.
* `answers.answer(question, game, agent=None) -> str` is called by Srikar's
  `web/app.py` for the question box. `question` is typed text or a button payload
  such as `{"intent": "why_not", "column": 5}`; `game` is the `GameState` with the
  saved trace and explanation of the agent's last move.

Nothing here decides a move or changes the game. No language model is used: every
reply is built from fixed templates filled with search results and rule facts.

## Sentence templates

Each fact kind found by Naman's rules has one fixed phrase: win, block, fork,
trap, sacrifice, threat, setup and centre. The order comes from Naman's concept
priorities (`concepts.rank`), so the most important reason is said first. A phrase
is only produced for a fact that a rule actually found, so the agent never gives a
reason it did not have. A fact kind with no template (for example a rule added
later) is skipped instead of crashing.

Phrases for a move that was *not* played are worded differently ("About column 1:
it lets you win by playing on top of it in column 1"), so a reason against a move
is not read as a reason for it. Proven results are given in moves, the way the proposal words
them ("column 4 lets me force a win in 3 moves", "after column 1 you can force a
win in 2 moves"), counted from the position the player is looking at. Other scores
are given as numbers with a plain label: below 50 "roughly balanced", 50 to 250 a
slight edge, above 250 a clear edge. These labels are for the player and are not
win probabilities. The expected line shows at most six moves.

## Question matching

`parse_question` normalises the text (Unicode NFKC, lower case, single spaces) and
matches keyword patterns for four intents: why (`why did you play there?`,
`explain your move`), why not (`why not column 5?`, `why didn't you play 6`),
what if (`what if I play column 3?`, `what happens if I go in 1?`) and who is
winning (`who's ahead`, `am I winning?`). Exactly one intent must match; a message
with two questions gets a short reply asking for one at a time.

Columns can be written as digits (`5`, `col5`, `c5`, `5th`), number words
(`column five`, `fifth column`, or a lone number word as in `why not five?`), or
names (`the middle one`, `leftmost`, `the last column`). A number word that is not
next to "column" is only used when nothing else names a column, so "what if I play
column 3 first?" is column 3, and "the middle one" is column 4, not column 1.
Decimals, several columns, and columns outside 1 to 7 are rejected with a reason.
The player counts columns 1 to 7 and the code 0 to 6; the conversion happens once,
in `answers.py`. Two ambiguous forms are redirected instead of guessed: "why did
you play column 5?" (the agent may have played elsewhere) and "what if you play
3?" (the what-if question is about the player's own move). Every rejected or
off-topic message gets the same help reply, which lists the four questions.

## Answering the four questions

* **Why** returns the explanation already made for the agent's last move, so the
  answer always matches the sentence shown on the board.
* **Why not column c** reads the saved trace from before the agent's move and
  compares the search results for the chosen column and column c, then gives the
  rule facts about column c and its expected line. Shridali's search scores every
  first move with a full window, so both results are always exact; the answer
  still checks the `exact` flag and says it only has a bound if a different search
  ever sets it, but that does not happen with the current search. Asking about
  the column that was played gives the why answer; a column that was full gives a
  short reply.
* **What if I play c** plays c on a copy of the board and runs one new search, so
  the real game is never changed. An immediate win or a full board is answered
  directly without searching.
* **Who is winning** reuses the saved search when the agent has just moved and
  searches the current position otherwise. A proven result is given as "I can /
  you can force a win in n moves", counted from now; otherwise the score and its
  label, marked as an estimate.

Every unusual situation has its own short reply: game over (who won), no agent
move yet, a saved trace that no longer matches the board, the player asking
"what if" while it is the agent's turn, and a failed search (logged, never shown
as an error to the player).

Example replies, from a game against the heuristic agent (0.5 s per move) after
six moves, with the agent's last move in column 4:

| Question | Reply |
|-|-|
| why did you play there? | I played column 4 because it takes the centre column, which is part of the most lines of four. Looking 7 plies ahead, my score went from -11 to 34. |
| why not column 1? | I chose column 4 instead of column 1. After looking 7 plies ahead, column 4 scores 34, while column 1 scores -7. Expected line: ... |
| what if I play column 6? | If you play column 6, I would play column 3. After looking 7 plies ahead its score is 275. Expected line: ... This is a what-if search; your game has not changed. |
| who is winning? | After looking 7 plies ahead, the position looks roughly balanced. My score is 34. That is an estimate, not a proven result. |
| why not column 9? | Columns must be between 1 and 7. (help reply) |

## Tests

`tests/test_qa_parser.py` and `tests/test_qa_answers.py` have 29 test functions
with 164 sub-cases: every question form and column spelling above, the rejected
forms, all four answers on hand-built traces (including proven wins and losses
counted in moves), the unusual situations, and that a what-if search leaves the
game unchanged. On main (`d889af7`) the full suite passes: 174 tests.

## Robustness check (proposal 4.5)

The proposal target is that at least 95% of over 100 unusual or badly formed
questions get a sensible reply, each in under two seconds. Mani's
`eval/robustness.py` asks 120 questions in 13 categories (the four types and
their paraphrases, column spellings, invalid columns, typos, off-topic, empty and
junk input, several questions at once) in four game situations (mid-game, start,
full column, game over), and checks that each reply is a short plain answer of the
expected kind.

Final check on main `d889af7`, agent at 1 s per move. The full results (every
question, reply, category and time) are saved in `results/robustness/heuristic/`
and `results/robustness/network/`, as `robustness.csv` and `robustness.json`.

| Evaluator | Sensible | Under 2 s | Slowest reply | Target |
|-|-|-|-|-|
| Heuristic | 120/120 (100%) | 120/120 | 1.02 s | met |
| Network, round 1 (`models/round1.pt`) | 120/120 (100%) | 120/120 | 1.16 s | met |

Every category was 100% in both runs. Replies that only read the saved trace come
back almost at once (median 0.00 s); the slowest are the what-if and
who-is-winning replies that run a new 1 s search.

"Sensible" is not the same as "answered". Of the 120 replies, 46 were real answers
and 74 were the help reply or a short reason (for example "Columns must be between
1 and 7"). That split is what the check expects for off-topic, junk, invalid and
game-over questions, but it also includes real misspellings (below).

## Limitations

* Matching is by keywords, so it does not handle misspellings: "wyh did you play
  there", "why nott column 5" and "wat if i play col 3" get the help reply (5 of the
  13 typo questions). Paraphrases outside the patterns, such as "can you win?" or
  "what's the score", also get the help reply. These count as sensible (the player
  is told what to ask) but are not answered.
* One question per message, English only.
* The score labels (50 and 250) were chosen by hand and are the same for both
  evaluators.
* In the web app, `web/app.py` does not set `game.agent`, so in a game against the
  network the what-if search (and who is winning before the agent's first move)
  uses a 0.5 s heuristic agent instead of the game's engine. The robustness script
  sets `game.agent` itself, so it does not show this. The fix is one line in
  `Session.new_game` (`self.game.agent = self.agent`), which is Srikar's file and
  has been passed to him.
* The robustness check above used the round 1 network. It should be re-run with
  the final network (`--model models/nn_latest.pt`) once that file is shared;
  the question handling does not depend on the evaluator, so the result is not
  expected to change.

## Reproducing

From the repo root:

    python -m pytest -q tests/test_qa_parser.py tests/test_qa_answers.py
    python -m eval.robustness --out results/robustness/heuristic
    python -m eval.robustness --evaluator network --model models/round1.pt --out results/robustness/network

Each run writes `robustness.csv` and `robustness.json` to its `--out` folder. For
the final network, use `--model models/nn_latest.pt`.
