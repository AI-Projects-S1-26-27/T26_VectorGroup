# Shridali: introduction and search engine

## 1. Introduction and problem

Game-playing programs choose good moves but rarely say why. An engine can tell a
player that a move was bad, but not what it saw that the player missed, and the
player cannot ask why it did not play a different column. For someone trying to
learn from a game, the program is a black box.

Our project builds a Connect-4 agent that plays a strong game and explains each
move in plain English, for example "I played column 4 because it blocks your
three-in-a-row". During a game the human can also ask four kinds of follow-up
question: why this move, why not another column, what would happen if I played
a given column, and who is winning.

The central idea is that a minimax search already knows why it picked a move.
While searching it computes a score for every legal move, the line of play it
expects after each one, and the threats each move creates or blocks. We build
the explanation out of that search output rather than generating text after the
fact, so the explanation reflects what the agent actually calculated.

We chose Connect-4 (7 columns by 6 rows) because it is large enough to have
real tactics (threats, forks, zugzwang) but small enough that an explanation
fits in one or two sentences. The game is also solved, so the agent and its
explanations can be checked against a perfect solver. The scope is the standard
board, one human against the agent, and the four question types above. Open
conversation and other games are out of scope.

Course connection: the agent is a utility-based agent in a fully observable,
deterministic, two-player zero-sum game (adversarial search, unit 4). It
searches with negamax and alpha-beta pruning under a fixed time budget, which
makes it an example of bounded rationality. A hand-written heuristic and a
convolutional network are used as evaluation functions at the search horizon
(units 2 and 5), and a small rule base with forward chaining turns search
results into sentences (unit 3).

## 2. Search engine (board, negamax, iterative deepening)

The search engine is `c4/board.py`, `c4/trace.py`, `c4/evaluator.py`,
`c4/game.py`, `c4/search.py`, `c4/agent.py` and `c4/stub_agent.py`. Rujuta's
move ordering and transposition table plug into it through two optional
arguments, without changes to `search.py`.

### Board

The board is a pair of bitboards in the layout described by Pascal Pons. Each
column uses 7 bits (6 cells and one sentinel bit that is always 0), so the whole
board fits in 49 bits. `position` holds the stones of the player to move and
`mask` holds the stones of both players. Playing a move XORs `position` with
`mask`, which switches the point of view to the other player, and adds one stone
to `mask`. Board objects are immutable, so `play` returns a new board and the
search never has to undo a move.

Four in a row is detected with shifts: shifting by 7 finds horizontal lines, by
6 and 8 finds the two diagonals, and by 1 finds vertical lines. The sentinel bit
stops a line from wrapping from the top of one column into the next. Checking
whether a move wins takes a few bit operations.

### Negamax with alpha-beta

Because the game is zero-sum, one function serves both players. Every score is
from the point of view of the player to move, and the parent negates the child's
score. Alpha-beta pruning skips branches that cannot change the result.

Terminal scores use `WIN_SCORE - plies`, so a quicker win scores higher and a
slower loss scores higher than a quicker one. Outside the proven range, a
position is scored by the evaluator when the depth limit is reached. The
evaluator interface is a single function `evaluate(board)` returning an integer
in [-9999, 9999], which both the hand-written heuristic and the network
implement.

### Iterative deepening and the time limit

`search` searches to depth 1, then 2, and so on, until the time budget is used.
Depth 1 always finishes, so there is always a move to play. If time runs out
inside a deeper iteration, an exception unwinds the search and the unfinished
iteration is thrown away, so the result always comes from a fully completed
depth. The search also stops early when a forced win or loss is proven.

### Exact scores for every root move

Every legal move at the root is searched with a full window, so each root move
gets an exact score and a principal variation instead of only a bound. This
costs some pruning at the root, but it is what lets the explanation layer answer
"why not column c?" with a real score for column c.

### Hooks for ordering and the transposition table

`search` accepts `order_fn(board, moves, tt_move)` and a table object with
`probe` and `store`. Table entries carry a depth, a value, a flag (exact, lower
bound or upper bound) and a best move. Win and loss scores contain the distance
from the root, so they are converted to be relative to the node before storing
and converted back after probing; otherwise a stored win would be wrong when the
same position is reached at a different depth. Table cut-offs are disabled at
the first ply below the root so that root move scores stay exact. The table key
is the exact position key from the two bitboards, not a Zobrist hash, so there
are no hash collisions (the proposal mentioned Zobrist hashing; see Rujuta's
section).

### Trace and agent

Each search returns a `SearchTrace` holding the chosen move, the completed
depth, the node count, the time, the evaluator name, the static score before
searching, and for each legal root move its score, depth and principal
variation. This is the only interface between the search and the explanation
layer. `Agent` runs a search and then asks the explanation layer for a sentence;
if that layer is unavailable it falls back to `score_only_explanation`, which
only reports the score. That fallback is also the baseline for the rating study.

### Verification

- The board's win detection was checked against a brute-force checker over 1,500
  random games.
- Alpha-beta was checked against plain minimax on 25 positions (same score).
- The search was checked on three tactical positions: blocking an opponent's
  win, taking an immediate win, and a forced win in 3 plies.
- The full test suite passes (174 tests on the final run).

### Measured search depth

`python -m eval.measure_search` searches three fixed positions (empty board, an
early position after 6 moves and a later position after 14 moves) for 1 second
each. Because the search is time-limited, results vary by about one ply between
runs. Three runs gave:

| Search | Depth reached | Nodes per second |
|---|---|---|
| Plain alpha-beta, heuristic | 6 to 8 | about 28,000 to 72,000 |
| Alpha-beta + table + ordering, heuristic | 7 to 9 | about 17,000 to 60,000 |
| Alpha-beta + table + ordering, network | 4 to 5 | about 1,100 to 1,500 |

Table and ordering reached the same depth or one ply deeper than plain search in
every position of every run; the gain is small and not the same in each run. They are slower per node,
because of table lookups and sorting, but each node is more useful. A cleaner measure is
Rujuta's node-count experiment at a fixed depth (2.35 times fewer nodes at depth
8, below the 10 times target). The network searches about 3 plies shallower than the
heuristic in the same time because a network forward pass costs much more than the
heuristic.

### A time-limit bug found during evaluation

The first 200-game match between the network and the heuristic used a clock check
every 1024 nodes. That is frequent for the heuristic but not for the network: 1024
network nodes take about 0.8 s, so the network overran its 1 s budget and used
1.3 to 1.7 s per move. That broke the equal-time condition. We changed the check
to every 64 nodes; the network then used 1.01 to 1.06 s per move, and the match
was rerun. Both runs are saved:

| Run | Network wins | Draws | Heuristic wins | Network score |
|---|---|---|---|---|
| 1 (clock checked every 1024 nodes, network overran) | 94 | 11 | 95 | 0.4975 |
| 2 (clock checked every 64 nodes, equal time) | 94 | 10 | 96 | 0.495 (95% Wilson CI 0.426 to 0.564) |

Run 2 is the result for the equal-time experiment. The target of at least 55%
was not met, and the interval includes 0.5, so the match shows no detectable
difference between the two evaluators at equal time.

### Limitations

- The search is time-limited, so depth and node counts change by about a ply
  between runs and with machine load.
- Searching every root move with a full window gives exact scores for the
  explanations but prunes less at the root than a normal alpha-beta search.
- The search depth is only 4 with the network, so the network's evaluation has
  to offset a much shallower search.
- The depth measurements use three positions. They show a trend but are not a
  statistically meaningful sample.

## Individual contribution

Shridali wrote the board and bitboard win detection, the immutable game state,
the trace format, the evaluator interface, negamax with alpha-beta, iterative
deepening with the time limit, the table and ordering hooks, and the agent that
connects the search to the explanation layer, with their tests. She also
measured the search depth, ran the 200-game network against heuristic match, found
the time-check bug and fixed it, and reran the match. Claude was used to draft
this code (see the AI-usage table).