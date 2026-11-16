# Report outline (Glass Box, Team 26 Vector Group)

Each owner drafts their own section in docs/report/<name>.md; Mani assembles.

1. Introduction and problem (Shridali): why explain moves, why Connect-4, scope
2. Search engine (Shridali, Rujuta): bitboards, negamax + alpha-beta, iterative deepening, ordering, table. Figure: results/plots/node_counts.png
3. Learned evaluator (Sriyanth, Veer): network, self-play rounds, training. Figure: results/plots/training_round*.png
4. Explanation layer (Naman, Aditya): facts, rules, templates, four question types. Table: claim-check accuracy
5. Interface (Srikar): screenshots
6. Evaluation (Mani): match results, solver agreement, claim correctness, rating study, robustness. Figures: match_*.png, solver_agreement.png, explanation_ratings.png. Report every target as met or not met, with the confidence interval
7. Limitations and honest negatives (all): e.g. if the network is no stronger than the heuristic, say so (the proposal commits to this)
8. AI-usage disclosure: copy from docs/AI_USAGE.md
References: from the proposal, plus any added
