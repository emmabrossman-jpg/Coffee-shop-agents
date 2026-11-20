# Scorecard

- Log: `events.json`
- Judged at: 2026-11-20T16:34:24+00:00
- Run: 8 of 8 slots, completed=True, stop_reason=None, sim calls=62
- Judge model calls: 4 (claude-haiku-5-5)

| Check | Type | Result | Evidence |
| --- | --- | --- | --- |
| Three characters, each with a goal and a limitation | Code | PASS | 3 characters in log, 3 with goal and limitation: dana, leo, sam |
| Each character wrote at least 3 memories | Code | PASS | dana 7, leo 4, sam 5 |
| Memories were used | Code | PASS | dana: dana-1 (written 7am) in a 8am prompt; leo: leo-1 (written 7am) in a 8am prompt; sam: sam-1 (written 7am) in a 8am prompt |
| Characters talked across the day | Code | PASS | conversations in 6 of 8 slots (7am, 8am, 9am, 10am, 3pm, 5pm); 8 slots logged |
| Every limitation held (Dana, Sam) | Code | PASS | Dana at counter 7am and 8am; Sam never in back_room across 8 slots |
| A decision was made | Code | PASS | decision='sell', reason: The chain's offer is the only option on the table that I can make work for the shop's future, and I can make it a condition that Leo and the rest of the staf... |
| Leo silent on money or the sale when Sam shares his zone | Model | PASS | 1 Leo turns checked; "Thanks for telling us yourself, Dana. I appreciate that. Sam, want your usual before we get slammed again?" |
| Dana pursued its goal | Model | PASS | score 4/5; "Leo, Sam, I've made the call. I'm selling the shop to the chain, and I've made keeping you both on at your current pay, with a raise path..." |
| Leo pursued its goal | Model | PASS | score 3/5; "Can you at least tell me now whether the chain's offer includes keeping the current staff, and what you'd need to see from me to support ..." |
| Sam pursued its goal | Model | PASS | score 3/5; "Have you already got a sense of which way you're leaning?" |

**Overall: PASS**

Pass rule: every code check passes and no character scores below 3.
