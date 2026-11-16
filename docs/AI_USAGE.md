# AI usage disclosure

Every member fills in their own row. Be specific: which tool, for what, and what you
checked or changed yourself.

| Member | Files | AI tool used | What it was used for | What the member checked or changed |
|---|---|---|---|---|
| Mani Vardhan | eval/solver.py, eval/stats.py, eval/match.py, eval/solver_agreement.py, eval/robustness.py, eval/plots.py, eval/user_study/*, tests for these | Claude (Anthropic) | Drafted these evaluation scripts and their tests from the proposal's section 4.5 and the repo's interfaces | Verified eval/solver.py against brute-force alpha-beta, checked match symmetry and CI calculations, aligned eval/plots.py with round1.json, and ran pytest (30 passed).
| Shridali Singh | | | | |
| Rujuta Deshmukh | | | | |
| Naman Jain | c4/explain/facts.py, rules.py, concepts.py, explain.py, eval/claim_check.py, tests/test_explain.py | Claude (Anthropic) | Drafted the board facts, rules, concept tree, explain_move, the claim checker and tests from proposal sections 4.3 and 4.5 and the trace interface | Ran eval/claim_check.py on 500 positions (1622/1622 claims correct), ran the full pytest suite (140 passed), and checked sample explanations from the heuristic agent |
| Aditya Kumar Somani | | | | |
| Veer Parekh | | | | |
| Sriyanth Varma M | | | | |
| CH J Srikar | | | | |
