# Scorecard

- Log: `events.json`
- Judged at: 2026-11-20T16:51:57+00:00
- Run: 8 of 8 slots, completed=True, stop_reason=None, sim calls=63
- Judge model calls: 4 (claude-haiku-5-5)

| Check | Type | Result | Evidence |
| --- | --- | --- | --- |
| Three characters, each with a goal and a limitation | Code | PASS | 3 characters in log, 3 with goal and limitation: dana, leo, sam |
| Each character wrote at least 3 memories | Code | PASS | dana 7, leo 4, sam 5 |
| Memories were used | Code | PASS | dana: dana-1 (written 7am) in a 8am prompt; leo: leo-1 (written 7am) in a 8am prompt; sam: sam-1 (written 7am) in a 8am prompt |
| Characters talked across the day | Code | PASS | conversations in 6 of 8 slots (7am, 8am, 9am, 10am, 1pm, 5pm); 8 slots logged |
| Every limitation held (Dana, Sam) | Code | PASS | Dana at counter 7am and 8am; Sam never in back_room across 8 slots |
| A decision was made | Code | PASS | decision='sell', reason: The $420,000 cash offer clears my debts and the coming 15% rent hike and $12,000 machine replacement, while I can secure Leo's pay and a fair transition by n... |
| Leo silent on money or the sale when Sam shares his zone | Model | PASS | 1 Leo turns checked; "Sam, can I get you anything else while you're here? The oat milk latte is on me today if you want to try it." |
| Dana pursued its goal | Model | PASS | score 3/5; "[5pm, counter] dana: Sam, Leo, I've made my decision. I'm selling the shop to the chain. Leo, I'll make sure your pay and your place are ..." |
| Leo pursued its goal | Model | PASS | score 3/5; "Before you decide, could we talk about what a fair wage would look like for me, either under the shop or in any deal?" |
| Sam pursued its goal | Model | PASS | score 4/5; "[8am, counter] sam: Totally understand, no rush on anything. Honestly, if you ever did think about moving on from the shop, I'd be curiou..." |

**Overall: PASS**

Pass rule: every code check passes and no character scores below 3.
