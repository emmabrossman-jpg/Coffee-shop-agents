# Scorecard

- Log: `events.json`
- Judged at: 2026-11-20T16:58:04+00:00
- Run: 8 of 8 slots, completed=True, stop_reason=None, sim calls=68
- Judge model calls: 4 (claude-haiku-5-5)

| Check | Type | Result | Evidence |
| --- | --- | --- | --- |
| Three characters, each with a goal and a limitation | Code | PASS | 3 characters in log, 3 with goal and limitation: dana, leo, sam |
| Each character wrote at least 3 memories | Code | PASS | dana 8, leo 4, sam 6 |
| Memories were used | Code | PASS | dana: dana-1 (written 7am) in a 8am prompt; leo: leo-1 (written 7am) in a 8am prompt; sam: sam-1 (written 7am) in a 8am prompt |
| Characters talked across the day | Code | PASS | conversations in 7 of 8 slots (7am, 8am, 9am, 10am, 11am, 1pm, 5pm); 8 slots logged |
| Every limitation held (Dana, Sam) | Code | PASS | Dana at counter 7am and 8am; Sam never in back_room across 8 slots |
| A decision was made | Code | PASS | decision='sell', reason: At $420,000 cash, the offer is roughly eleven years of the shop's $38,000 annual profit, which covers the $12,000 machine and the 15% lease hike with room to... |
| Leo silent on money or the sale when Sam shares his zone | Model | PASS | 1 Leo turns checked; "Sure, Dana. Sam's here, so let's keep it to the counter for now. Sam, can I get you anything else while you wait?" |
| Dana pursued its goal | Model | PASS | score 4/5; "[5pm] decision: sell because At $420,000 cash, the offer is roughly eleven years of the shop's $38,000 annual profit, which covers the $1..." |
| Leo pursued its goal | Model | PASS | score 4/5; "I'd like a raise of $2 an hour, effective now, and I'd like it in writing before any sale is finalized." |
| Sam pursued its goal | Model | PASS | score 4/5; "[10am, counter] sam: Usual's perfect, Dana, thanks. Something on your mind? You've got that look like the shop's keeping you up. If you e..." |

**Overall: PASS**

Pass rule: every code check passes and no character scores below 3.
