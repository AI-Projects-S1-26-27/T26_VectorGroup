# Rate the explanations (sheet A)

In each case a Connect-4 program (yellow or red, shown below as the player to move) chose a column and gave a reason. Rate the reason from 1 (very bad) to 5 (very good) on three things: **correctness** (is what it says true on this board?), **clarity** (is it easy to understand?), **usefulness** (does it help you understand the move?).

## Item 1
Player to move: **red**. Red moves first. Columns are numbered 1-7 from the left.

⚪⚪⚪⚪⚪⚪⚪
🔴⚪⚪⚪🟡⚪⚪
🟡🔴⚪⚪🟡⚪⚪
🔴🟡⚪🟡🔴⚪⚪
🟡🔴⚪🔴🟡⚪⚪
🟡🔴⚪🟡🔴🔴⚪
1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣

Program's move and reason: *I played column 4 because it takes the centre column, which is part of the most lines of four. Looking 6 plies ahead, my score went from -787 to -612.*

Questions (1-5): Correctness / Clarity / Usefulness

## Item 2
Player to move: **yellow**. Red moves first. Columns are numbered 1-7 from the left.

⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪⚪⚪⚪⚪
⚪⚪🟡⚪⚪⚪⚪
⚪⚪🔴⚪⚪⚪⚪
⚪🔴🔴⚪🟡⚪⚪
⚪🔴🟡⚪🔴⚪🟡
1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣

Program's move and reason: *I played column 7. After looking 5 plies ahead its score is 174.*

Questions (1-5): Correctness / Clarity / Usefulness

## Item 3
Player to move: **red**. Red moves first. Columns are numbered 1-7 from the left.

⚪⚪⚪🔴⚪⚪⚪
⚪⚪⚪🟡🔴⚪⚪
⚪⚪🔴🟡🟡⚪⚪
⚪⚪🟡🟡🔴⚪⚪
⚪⚪🔴🔴🔴🟡⚪
🟡⚪🔴🟡🟡🔴⚪
1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣

Program's move and reason: *I played column 5. There is no direct tactic here, but my network rates the position after it at -0.33 for me, and your stone in column 4, row 3 is a problem for me the most. Looking 9 plies ahead, my score went from -875 to 53.*

Questions (1-5): Correctness / Clarity / Usefulness

## Item 4
Player to move: **red**. Red moves first. Columns are numbered 1-7 from the left.

⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪🟡⚪🔴⚪
⚪⚪⚪🟡⚪🔴⚪
⚪⚪🟡🔴⚪🟡⚪
⚪⚪🔴🟡⚪🔴⚪
1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣

Program's move and reason: *I played column 4. After looking 5 plies ahead its score is 653.*

Questions (1-5): Correctness / Clarity / Usefulness

## Item 5
Player to move: **yellow**. Red moves first. Columns are numbered 1-7 from the left.

⚪⚪⚪⚪⚪⚪⚪
⚪🟡🟡🔴⚪⚪⚪
⚪🔴🔴🟡⚪⚪⚪
⚪🟡🟡🔴⚪🔴⚪
⚪🟡🔴🔴⚪🟡⚪
🔴🟡🔴🟡⚪🔴⚪
1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣

Program's move and reason: *I played column 6. There is no direct tactic here, but my network rates the position after it at -0.97 for me, and your stone in column 4, row 3 is a problem for me the most. Looking 7 plies ahead, my score went from -936 to -938.*

Questions (1-5): Correctness / Clarity / Usefulness

## Item 6
Player to move: **red**. Red moves first. Columns are numbered 1-7 from the left.

⚪⚪⚪🔴⚪⚪⚪
⚪⚪⚪🟡⚪⚪⚪
⚪🔴⚪🟡🔴⚪⚪
⚪🟡⚪🟡🟡⚪🟡
⚪🟡⚪🔴🟡⚪🔴
🔴🔴🟡🟡🔴🔴🔴
1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣

Program's move and reason: *I played column 2. After looking 7 plies ahead its score is -162.*

Questions (1-5): Correctness / Clarity / Usefulness

## Item 7
Player to move: **yellow**. Red moves first. Columns are numbered 1-7 from the left.

⚪⚪⚪🟡⚪🟡🟡
⚪⚪🔴🟡⚪🔴🔴
🔴⚪🔴🔴⚪🟡🟡
🟡⚪🟡🟡⚪🔴🟡
🟡⚪🔴🔴⚪🟡🔴
🔴⚪🔴🟡⚪🔴🔴
1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣

Program's move and reason: *I played column 5 because it looks worse at first sight, but the search score is higher. I can force a win in 6 moves.*

Questions (1-5): Correctness / Clarity / Usefulness

## Item 8
Player to move: **red**. Red moves first. Columns are numbered 1-7 from the left.

⚪⚪⚪⚪🟡⚪⚪
⚪⚪⚪⚪🔴⚪⚪
⚪⚪🟡⚪🟡🔴⚪
⚪⚪🔴⚪🟡🟡⚪
⚪🔴🔴⚪🔴🟡⚪
🔴🟡🟡⚪🔴🔴🟡
1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣

Program's move and reason: *I played column 4. After looking 6 plies ahead its score is 861.*

Questions (1-5): Correctness / Clarity / Usefulness

## Item 9
Player to move: **yellow**. Red moves first. Columns are numbered 1-7 from the left.

⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪🟡🔴🟡⚪
⚪⚪🔴🔴🟡🔴⚪
⚪🟡🟡🔴🔴🔴🟡
1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣

Program's move and reason: *I played column 4 because it takes the centre column, which is part of the most lines of four. Looking 5 plies ahead, my score went from 399 to 139.*

Questions (1-5): Correctness / Clarity / Usefulness

## Item 10
Player to move: **red**. Red moves first. Columns are numbered 1-7 from the left.

⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪🟡🟡⚪⚪
⚪⚪⚪🔴🔴🟡🔴
🟡🔴⚪🟡🔴🔴🟡
1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣

Program's move and reason: *I played column 4. After looking 7 plies ahead its score is -346.*

Questions (1-5): Correctness / Clarity / Usefulness

## Item 11
Player to move: **yellow**. Red moves first. Columns are numbered 1-7 from the left.

⚪⚪⚪⚪⚪⚪⚪
⚪⚪🔴⚪🟡⚪🟡
⚪🟡🟡⚪🔴⚪🔴
⚪🔴🔴⚪🟡⚪🟡
⚪🟡🟡⚪🔴⚪🔴
⚪🟡🔴🔴🟡🔴🔴
1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣

Program's move and reason: *I played column 4 because it sets up a threat in column 1, row 2 for later and it takes the centre column, which is part of the most lines of four. Looking 7 plies ahead, my score went from -906 to -409.*

Questions (1-5): Correctness / Clarity / Usefulness

## Item 12
Player to move: **yellow**. Red moves first. Columns are numbered 1-7 from the left.

⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪⚪⚪⚪⚪
⚪🟡⚪🔴⚪⚪⚪
⚪🔴⚪🟡⚪⚪⚪
⚪🟡⚪🔴🔴⚪🟡
🟡🔴⚪🟡🔴⚪🔴
1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣

Program's move and reason: *I played column 4. After looking 5 plies ahead its score is -28.*

Questions (1-5): Correctness / Clarity / Usefulness

## Item 13
Player to move: **yellow**. Red moves first. Columns are numbered 1-7 from the left.

⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪🔴⚪⚪⚪
⚪⚪⚪🟡⚪⚪⚪
⚪🟡⚪🔴⚪⚪⚪
🟡🔴🔴🔴🟡⚪⚪
1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣

Program's move and reason: *I played column 2. There is no direct tactic here, but my network rates the position after it at +0.72 for me, and my stone in column 4, row 3 helps me the most. Looking 4 plies ahead, my score went from 818 to 232.*

Questions (1-5): Correctness / Clarity / Usefulness

## Item 14
Player to move: **yellow**. Red moves first. Columns are numbered 1-7 from the left.

⚪⚪⚪⚪⚪⚪⚪
⚪🔴⚪⚪⚪⚪⚪
⚪🟡🟡🔴⚪⚪⚪
⚪🔴🔴🟡⚪🟡🔴
🟡🟡🔴🔴⚪🔴🟡
🔴🟡🟡🔴⚪🔴🟡
1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣

Program's move and reason: *I played column 3. After looking 5 plies ahead its score is 73.*

Questions (1-5): Correctness / Clarity / Usefulness

## Item 15
Player to move: **red**. Red moves first. Columns are numbered 1-7 from the left.

⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪⚪⚪⚪⚪
⚪⚪🔴⚪⚪⚪⚪
⚪⚪🔴⚪⚪⚪⚪
🔴⚪🟡⚪⚪⚪⚪
🔴⚪🟡🟡🟡🔴🟡
1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣

Program's move and reason: *I played column 2 because it blocks your four-in-a-row. Looking 8 plies ahead, my score went from 286 to -615.*

Questions (1-5): Correctness / Clarity / Usefulness

## Item 16
Player to move: **yellow**. Red moves first. Columns are numbered 1-7 from the left.

⚪⚪⚪⚪⚪⚪⚪
⚪⚪🟡⚪⚪⚪⚪
⚪⚪🔴⚪⚪⚪⚪
⚪🟡🔴⚪⚪⚪⚪
🟡🔴🟡⚪🔴⚪🟡
🔴🟡🔴🔴🟡⚪🔴
1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣

Program's move and reason: *I played column 5. After looking 5 plies ahead its score is -961.*

Questions (1-5): Correctness / Clarity / Usefulness

## Item 17
Player to move: **red**. Red moves first. Columns are numbered 1-7 from the left.

⚪⚪⚪⚪⚪⚪⚪
⚪🟡⚪⚪⚪⚪⚪
⚪🔴⚪⚪⚪⚪⚪
⚪🟡🔴⚪⚪⚪⚪
🟡🔴🟡🔴⚪🟡🔴
🔴🟡🟡🔴⚪🔴🟡
1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣

Program's move and reason: *I played column 5 because it completes four in a row and wins the game. I can force a win in 1 move.*

Questions (1-5): Correctness / Clarity / Usefulness

## Item 18
Player to move: **yellow**. Red moves first. Columns are numbered 1-7 from the left.

⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪⚪⚪⚪⚪
⚪🟡⚪⚪⚪⚪⚪
⚪🔴🔴⚪⚪⚪⚪
🟡🔴🔴🟡🔴🟡⚪
1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣

Program's move and reason: *I played column 4. After looking 6 plies ahead its score is -360.*

Questions (1-5): Correctness / Clarity / Usefulness

## Item 19
Player to move: **red**. Red moves first. Columns are numbered 1-7 from the left.

⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪🟡⚪⚪⚪
⚪⚪🟡🔴🟡⚪⚪
⚪⚪🔴🔴🔴🟡⚪
🟡⚪🔴🟡🔴🟡🔴
1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣

Program's move and reason: *I played column 5 because it looks worse at first sight, but the search score is higher, it threatens to win in column 2 next move and it sets up a threat in column 6, row 5 for later. I can force a win in 2 moves.*

Questions (1-5): Correctness / Clarity / Usefulness

## Item 20
Player to move: **yellow**. Red moves first. Columns are numbered 1-7 from the left.

⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪⚪⚪⚪⚪
🟡⚪🔴🟡⚪⚪⚪
🔴🟡🟡🔴🟡⚪⚪
🔴🔴🟡🟡🔴🔴🔴
1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣

Program's move and reason: *I played column 4. After looking 5 plies ahead its score is 826.*

Questions (1-5): Correctness / Clarity / Usefulness

## Item 21
Player to move: **red**. Red moves first. Columns are numbered 1-7 from the left.

⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪⚪🟡⚪⚪
⚪⚪⚪🟡🔴⚪⚪
⚪⚪⚪🔴🟡⚪🔴
🔴⚪🟡🔴🔴🟡🟡
1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣

Program's move and reason: *I played column 3. There is no direct tactic here, but my network rates the position after it at -0.06 for me, and your stone in column 5, row 4 is a problem for me the most. Looking 5 plies ahead, my score went from -119 to -99.*

Questions (1-5): Correctness / Clarity / Usefulness

## Item 22
Player to move: **red**. Red moves first. Columns are numbered 1-7 from the left.

⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪⚪⚪🟡⚪
⚪⚪⚪⚪⚪🔴🟡
🟡⚪⚪🔴🔴🟡🔴
1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣

Program's move and reason: *I played column 4. After looking 5 plies ahead its score is 955.*

Questions (1-5): Correctness / Clarity / Usefulness

## Item 23
Player to move: **yellow**. Red moves first. Columns are numbered 1-7 from the left.

⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪⚪⚪⚪⚪
⚪⚪🟡⚪⚪⚪⚪
🔴⚪🔴⚪⚪⚪⚪
🟡🔴🔴🔴🟡🟡⚪
1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣

Program's move and reason: *I played column 2 because it sets up a threat in column 4, row 4 for later. Looking 5 plies ahead, my score went from -398 to 341.*

Questions (1-5): Correctness / Clarity / Usefulness

## Item 24
Player to move: **red**. Red moves first. Columns are numbered 1-7 from the left.

⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪⚪⚪🔴⚪
⚪⚪🔴⚪🟡🟡🟡
⚪🔴🟡⚪🔴🟡🔴
1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣

Program's move and reason: *I played column 2. After looking 4 plies ahead its score is -778.*

Questions (1-5): Correctness / Clarity / Usefulness

## Item 25
Player to move: **yellow**. Red moves first. Columns are numbered 1-7 from the left.

⚪⚪⚪🔴⚪⚪⚪
⚪⚪⚪🟡🟡⚪⚪
⚪⚪⚪🟡🟡⚪⚪
⚪⚪🔴🔴🔴⚪⚪
⚪⚪🟡🔴🔴🟡⚪
⚪🔴🔴🟡🟡🔴⚪
1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣

Program's move and reason: *I played column 3 because it blocks your four-in-a-row and it sets up a threat in column 2, row 4 for later. I am losing by force, and this move delays it the longest.*

Questions (1-5): Correctness / Clarity / Usefulness

## Item 26
Player to move: **red**. Red moves first. Columns are numbered 1-7 from the left.

⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪⚪⚪⚪⚪
⚪🟡⚪⚪⚪⚪⚪
🔴🔴⚪🟡⚪⚪⚪
🟡🔴⚪🟡🔴🟡🔴
1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣

Program's move and reason: *I played column 4. After looking 5 plies ahead its score is -40.*

Questions (1-5): Correctness / Clarity / Usefulness

## Item 27
Player to move: **yellow**. Red moves first. Columns are numbered 1-7 from the left.

⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪🟡⚪⚪⚪
⚪⚪🟡🔴⚪⚪⚪
⚪⚪🔴🔴⚪⚪⚪
🔴⚪🔴🟡⚪⚪⚪
🟡🔴🟡🔴🔴🟡🟡
1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣

Program's move and reason: *I played column 6. There is no direct tactic here, but my network rates the position after it at -0.51 for me, and your stone in column 2, row 1 is a problem for me the most. Looking 5 plies ahead, my score went from -733 to -439.*

Questions (1-5): Correctness / Clarity / Usefulness

## Item 28
Player to move: **red**. Red moves first. Columns are numbered 1-7 from the left.

⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪⚪⚪⚪⚪
🟡⚪⚪⚪⚪⚪⚪
🔴⚪🔴⚪⚪🟡⚪
🔴🟡🟡🔴⚪🔴⚪
🟡🔴🟡🟡⚪🔴⚪
1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣

Program's move and reason: *I played column 2. I can force a win in 3 moves.*

Questions (1-5): Correctness / Clarity / Usefulness

## Item 29
Player to move: **yellow**. Red moves first. Columns are numbered 1-7 from the left.

⚪⚪⚪⚪⚪⚪⚪
⚪⚪⚪⚪⚪⚪⚪
⚪⚪🔴🔴🔴⚪⚪
⚪⚪🔴🔴🟡⚪⚪
⚪⚪🟡🟡🔴🟡⚪
⚪⚪🔴🟡🔴🟡🟡
1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣

Program's move and reason: *I played column 4 because it takes the centre column, which is part of the most lines of four. Looking 5 plies ahead, my score went from -930 to -983.*

Questions (1-5): Correctness / Clarity / Usefulness

## Item 30
Player to move: **yellow**. Red moves first. Columns are numbered 1-7 from the left.

⚪⚪⚪🟡🔴⚪⚪
🔴⚪⚪🔴🟡⚪⚪
🔴🔴⚪🟡🟡⚪⚪
🟡🟡⚪🔴🔴⚪⚪
🟡🔴⚪🔴🟡⚪⚪
🔴🔴🟡🟡🔴⚪🟡
1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣

Program's move and reason: *I played column 6. After looking 6 plies ahead its score is -925.*

Questions (1-5): Correctness / Clarity / Usefulness
