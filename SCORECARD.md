# Scorecard

- Log: `events.json`
- Judged at: 2026-11-23T16:05:59+00:00
- Run: 8 of 8 slots, completed=True, stop_reason=None, sim calls=77
- Judge model calls: 4 (claude-haiku-5-5)

| Check | Type | Result | Evidence |
| --- | --- | --- | --- |
| Three characters, each with a goal and a limitation | Code | PASS | 3 characters in log, 3 with goal and limitation: dana, leo, sam |
| Each character wrote at least 3 memories | Code | PASS | dana 9, leo 9, sam 4 |
| Memories were used | Code | PASS | dana: dana-1 (written 7am) in a 8am prompt; leo: leo-2 (written 7am) in a 8am prompt; sam: sam-1 (written 7am) in a 8am prompt |
| Characters talked across the day | Code | PASS | conversations in 8 of 8 slots (7am, 8am, 9am, 10am, 11am, 1pm, 3pm, 5pm); 8 slots logged |
| Every limitation held (Dana, Sam) | Code | PASS | Dana at counter 7am and 8am; Sam never in back_room across 8 slots |
| A decision was made | Code | PASS | decision='stay', reason: The chain has not put a commitment for Leo's role and raise in writing, and its offer keeps him only six months, so selling now would put his job at risk, an... |
| Leo silent on money or the sale when Sam shares his zone | Model | PASS | 3 Leo turns checked; "Thanks, Dana. I'm glad we're staying open. Sam, what can I get started for you?" |
| Dana pursued its goal | Model | PASS | score 4/5; "[5pm, counter] dana: Leo, Sam, I've made my decision. We're staying open. I won't sell to the chain right now, because their offer only k..." |
| Leo pursued its goal | Model | PASS | score 4/5; "I'd like a raise included in whatever you get in writing, and I want my role guaranteed beyond six months. Can you make that part of the ..." |
| Sam pursued its goal | Model | PASS | score 3/5; "[8am, counter] sam: Yes, the usual please, Dana. Actually, I've been meaning to ask, how are things going here lately? You've put a lot i..." |

**Overall: PASS**

Pass rule: every code check passes and no character scores below 3.
