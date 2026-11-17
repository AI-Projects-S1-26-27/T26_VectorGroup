# AI usage disclosure

Every member fills in their own row. Be specific: which tool, for what, and what you
checked or changed yourself.

|Member|Files|AI tool used|What it was used for|What the member checked or changed|
|-|-|-|-|-|
|Mani Vardhan|eval/solver.py, eval/stats.py, eval/match.py, eval/solver\_agreement.py, eval/robustness.py, eval/plots.py, eval/user\_study/\*, tests for these|Claude (Anthropic)|Drafted these evaluation scripts and their tests from the proposal's section 4.5 and the repo's interfaces|Verified eval/solver.py against brute-force alpha-beta, checked match symmetry and CI calculations, aligned eval/plots.py with round1.json, and ran pytest (30 passed).|
|Shridali Singh|||||
|Rujuta Deshmukh|c4/eval_heuristic.py, c4/ordering.py, c4/tt.py, eval/node_counts.py, tests for these, docs/report/rujuta.md, node-count results and plot|OpenAI Codex|Inspected the existing board/search/trace interfaces; drafted the heuristic, table, benchmark, tests, documentation, and experiment summary; checked the existing ordering implementation|Personally ran pytest in the terminal (53 passed before merging; 68 passed and 2 skipped after updating main). Codex ran interface, symmetry, bounds, ordering, table, warm-cache integration, seeded-sample and CSV tests. Experiment measurements and later suite results are recorded in the report/results; these automated checks are not claimed as a separate manual code review.|
|Naman Jain|c4/explain/facts.py, rules.py, concepts.py, explain.py, eval/claim\_check.py, tests/test\_explain.py|Claude (Anthropic)|Drafted the board facts, rules, concept tree, explain\_move, the claim checker and tests from proposal sections 4.3 and 4.5 and the trace interface|Ran eval/claim\_check.py on 500 positions (1622/1622 claims correct), ran the full pytest suite (140 passed), and checked sample explanations from the heuristic agent|
|Aditya Kumar Somani|||||
|Veer Parekh|c4/selfplay/generate.py, c4/selfplay/dataset.py, tests/test\_selfplay\_generate.py, tests/test\_selfplay\_dataset.py, docs/report/veer.md, round 2 self-play data|Claude (Anthropic)|Wrote the self-play generator, the dataset loader/encoder and their tests from proposal section 4.2 and the repo's interfaces; generated the round 2 data (5,000 games with the round 1 network); drafted the report section; drafted the reviews of PR #9 and PR #6 posted from Veer's account|Checks were run by Claude: full test suite at merge (47 passed, 20 new), generator tested with Rujuta's heuristic, table and ordering and end to end with Sriyanth's network (generate, train, network self-play), and all 5,000 round 2 games replayed to confirm legal moves and correct labels. Veer directed the work and handed the round 2 data to Sriyanth, who used it for the round 2 network (77.2% vs 75.3% winner accuracy).|
|Sriyanth Varma M|c4/nn/model.py, train.py, evaluator.py, saliency.py, tests/test\_nn.py|Claude (Anthropic)|Drafted the network, training script, evaluator and saliency code and their tests from proposal section 4.2 and the repo's interfaces|Ran the tests (14 passed), generated round 1 data (20k games), trained v1 (test MSE 0.66 vs 0.91 baseline, 75% winner accuracy) and v2 on round 1 + Veer's round 2 (test MSE 0.59 vs 0.88, 77%), and checked the network engine in the web app |
|CH J Srikar|||||



