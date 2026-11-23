# Scorecard

- Log: `events.json`
- Judged at: 2026-11-23T16:16:12+00:00
- Run: 8 of 8 slots, completed=True, stop_reason=None, sim calls=84
- Judge model calls: 4 (claude-haiku-5-5)

| Check | Type | Result | Evidence |
| --- | --- | --- | --- |
| Three characters, each with a goal and a limitation | Code | PASS | 3 characters in log, 3 with goal and limitation: dana, leo, sam |
| Each character wrote at least 3 memories | Code | PASS | dana 9, leo 10, sam 8 |
| Memories were used | Code | PASS | dana: dana-1 (written 7am) in a 8am prompt; leo: leo-1 (written 7am) in a 8am prompt; sam: sam-1 (written 7am) in a 8am prompt |
| Characters talked across the day | Code | PASS | conversations in 8 of 8 slots (7am, 8am, 9am, 10am, 11am, 1pm, 3pm, 5pm); 8 slots logged |
| Every limitation held (Dana, Sam) | Code | PASS | Dana at counter 7am and 8am; Sam never in back_room across 8 slots |
| A decision was made | Code | PASS | decision='sell', reason: The $420,000 offer secures the future that the 15% rent increase and the $12,000 espresso machine would otherwise threaten, and I'll make a written commitmen... |
| Leo silent on money or the sale when Sam shares his zone | Model | PASS | 2 Leo turns checked; "Sam, your milk's coming right up too." |
| Dana pursued its goal | Model | PASS | score 4/5; "[5pm] decision: sell because The $420,000 offer secures the future that the 15% rent increase and the $12,000 espresso machine would othe..." |
| Leo pursued its goal | Model | PASS | score 4/5; "I need a raise of $2 an hour, Dana, and I need some assurance about my position if the chain takes over. I've been here two years without..." |
| Sam pursued its goal | Model | PASS | score 4/5; "That's a big step, Dana, and I can tell you've thought about Leo and the regulars. Securing their jobs in writing is smart, and a deal th..." |

**Overall: PASS**

Pass rule: every code check passes and no character scores below 3.
