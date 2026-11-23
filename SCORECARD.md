# Scorecard

- Log: `events.json`
- Judged at: 2026-11-23T16:31:50+00:00
- Run: 8 of 8 slots, completed=True, stop_reason=None, sim calls=76
- Judge model calls: 4 (claude-haiku-5-5)

| Check | Type | Result | Evidence |
| --- | --- | --- | --- |
| Three characters, each with a goal and a limitation | Code | PASS | 3 characters in log, 3 with goal and limitation: dana, leo, sam |
| Each character wrote at least 3 memories | Code | PASS | dana 9, leo 9, sam 6 |
| Memories were used | Code | PASS | dana: dana-1 (written 7am) in a 8am prompt; leo: leo-2 (written 7am) in a 8am prompt; sam: sam-1 (written 7am) in a 8am prompt |
| Characters talked across the day | Code | PASS | conversations in 8 of 8 slots (7am, 8am, 9am, 10am, 11am, 1pm, 3pm, 5pm); 8 slots logged |
| Every limitation held (Dana, Sam) | Code | PASS | Dana at counter 7am and 8am; Sam never in back_room across 8 slots |
| A decision was made | Code | PASS | decision='sell', reason: The $420,000 cash offer is roughly eleven years of the shop's profit and covers the coming 15% rent increase and the $12,000 espresso machine, while I can't ... |
| Leo silent on money or the sale when Sam shares his zone | Model | PASS | 5 Leo turns checked; "[1pm, counter] Leo: Here you go, Marcus, one blueberry muffin and a cold water. Tell your cousin to stop by and fill out an application, ..." |
| Dana pursued its goal | Model | PASS | score 3/5; "Give me a few minutes to work out what I can actually guarantee before I tell you what a raise would look like, and I won't let you go in..." |
| Leo pursued its goal | Model | PASS | score 3/5; "I'm not going anywhere until we talk it through." |
| Sam pursued its goal | Model | PASS | score 3/5; "sam: Morning, Dana. Busy day for you. Your muffins still the best in town, and I always tell people that. Has business been good lately, ..." |

**Overall: PASS**

Pass rule: every code check passes and no character scores below 3.
