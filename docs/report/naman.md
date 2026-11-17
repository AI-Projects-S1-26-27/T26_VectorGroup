# Naman: explanation layer and claim checking

## Scope and interfaces

Naman's modules are `c4/explain/facts.py`, `c4/explain/rules.py`,
`c4/explain/concepts.py`, `c4/explain/explain.py` and `eval/claim_check.py`,
with their tests in `tests/test_explain.py`. They only read Shridali's
`SearchTrace`; the search writes the trace and the explanation layer adds facts
to it. `c4/agent.py` calls two functions:

* `detect_facts(trace)` fills `MoveInfo.facts` for every legal root move.
* `explain_move(trace)` returns the `Explanation` for the chosen move.

Sentence wording is Aditya's (`c4/explain/templates.py`). His question answers
("why not column c?", "what if I play c?") reuse the same facts, so every answer
is built from the same rule results.

## Board facts

Facts are computed on a plain 6x7 array (`Board.to_array()`, row 0 = bottom,
+1 = the side we are explaining for, -1 = the other side), not on bitboards, so
each rule can be read and checked by hand.

* The 69 possible lines of four: 24 horizontal, 21 vertical and 12 in each
  diagonal direction, generated once and asserted to be 69.
* For each line: how many stones each side has and which cells are empty.
* Playable cells: the empty cell a stone would land in for each non-full column.
* Threat cells: empty cells where one side would complete four (three own stones
  and an empty cell in a line with no opponent stone). Gravity is ignored here;
  whether a threat can be played next move is a separate fact.
* Row parity, counted the human way (bottom row = row 1, odd). Allis (1988) shows
  odd threats favour the first player and even threats the second.

## Rules and forward chaining

Each rule is a production: it reads the board facts for one root move, the
search trace and the facts derived so far (the working memory), and may add new
facts. All rules are fired repeatedly until no rule adds anything new
(forward chaining, T1 Ch. 7 and 9). All facts are about the side making the root
move.

| Fact | Fires when |
|---|---|
| win | playing the column wins at once |
| block | the opponent has a playable threat in the cell this move fills |
| threat | the move creates a new threat cell for us (detail: playable, or odd/even row) |
| trap | after the move, the opponent can win in the cell directly above it |
| centre | the move is in the centre column |
| sacrifice | the static score drops after the move, but the search score is higher than before |
| fork (derived) | two or more playable threat facts at once |
| setup (derived) | a threat fact that is not playable yet, i.e. a threat for later |

Fork and setup are derived rules: they fire only on threat facts produced by
another rule, which is what makes this chaining rather than a list of
independent checks. If a move wins, no other rule fires for it. Every fact
stores its cells, with the target cell first, so each claim can be checked
independently afterwards.

The sacrifice rule compares two scores, so it must use the same evaluator that
scored the trace: the heuristic for heuristic traces and the network for
network traces. If that evaluator is not available, the rule is skipped rather
than mixing scales.

## Concept hierarchy

The fact kinds are organised as categories (T1 Ch. 10) in a small is-a tree:

```
concept
├── tactic
│   ├── attack   : win, fork, threat, setup
│   ├── defence  : block
│   └── danger   : trap
├── strategy     : sacrifice
└── positional   : centre, saliency
```

Each leaf has a priority (win 100, block 90, fork 80, trap 70, sacrifice 60,
threat 50, setup 40, centre 10). An explanation reports at most the top three
concepts that actually fired, highest priority first. A threat that cannot be
played yet is reported as a setup, not as a threat.

## From facts to a sentence

`explain_move` takes the chosen move's facts, picks the top one to three
concepts, and passes those facts to Aditya's templates, which add a score
clause. Examples from the heuristic agent:

* "I played column 1 because it blocks your four-in-a-row. Looking 7 plies
  ahead, my score went from -249 to 30." (moves 1 2 1 2 1)
* "I played column 1 because it completes four in a row and wins the game.
  I can force a win in 1 move." (moves 1 2 1 2 1 2)

Every phrase comes from a fact that a rule found, so the agent cannot claim a
reason it did not have. If no rule fires (a quiet positional move):

* with the network evaluator, Sriyanth's occlusion saliency
  (`c4/nn/saliency.py`) names the stone that changed the network's score most;
* otherwise the agent gives Shridali's score-only sentence, which is also the
  baseline in the rating study.

## Claim checking (proposal 4.5)

Target: at least 98% of the threats, blocks and forks the agent claims are
correct, on 500 positions.

`eval/claim_check.py` generates 500 random legal, unfinished positions (4 to 30
random moves, seed 0), runs the rules on every legal root move, and re-checks
every claim by actually playing moves with `Board.wins_by_playing`, without
using `facts.py`:

* win: the move wins at once;
* block: the opponent would win by playing the same column now;
* trap: after the move, the opponent wins by playing the same column;
* fork: after the move, we have at least two immediately winning columns;
* threat and setup: placing our stone in the target cell makes four, and the
  cell is playable exactly when the fact says it is.

Command:

```
python -m eval.claim_check --out results/claim_check.json
```

| Claim | Correct / claims | Accuracy |
|---|---:|---:|
| win | 198 / 198 | 100% |
| block | 193 / 193 | 100% |
| threat | 849 / 849 | 100% |
| fork | 30 / 30 | 100% |
| setup | 295 / 295 | 100% |
| trap | 57 / 57 | 100% |
| **All** | **1622 / 1622** | **100%** |

The **98% target was met**. The saved summary is `results/claim_check.json`.

## Testing

`tests/test_explain.py` covers the 69 lines, threat and playable cells, row
parity, the hierarchy and ranking, each rule on a hand-built position (win,
block, fork with centre, trap, setup with parity, sacrifice with and without an
evaluator), the explanation sentence, the score-only fallback, the saliency
fallback, the agent end-to-end, and a small claim-check run. The full suite
(174 tests) passed on 2026-11-17.

## Limitations

* Fork is conservative: it counts only threats created by this move. An older
  threat that the move makes playable is not counted, so forks can be missed
  but never falsely claimed.
* Sacrifice and centre are not brute-force checked. Centre is trivially true;
  sacrifice depends on evaluator scores, so it has no single correct answer to
  check against. In a 60-position sample with the heuristic agent, sacrifice
  never fired, so it rarely appears in explanations.
* The checker's positions come from random play, not human games, and it checks
  facts on every legal move, not only on the move the agent chose.
* The checker uses `Board.wins_by_playing` from Shridali's tested board code, so
  it is independent of `facts.py` but not of the board.
* The saliency fallback was tested with an untrained network only. Its wording
  should be checked with the trained network before the demo.
* Quiet moves with the heuristic evaluator get only a score sentence; the rules
  explain tactics well but say little about purely positional moves.

Code, test and report drafting used Claude (Anthropic). See Naman's entry in
`docs/AI_USAGE.md`.
