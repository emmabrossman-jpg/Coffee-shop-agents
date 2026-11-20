# Breaker report

## Stage 2: backend (fake mode)

As of November 20, 2026. Target: `sim.py` as read on that date. All runs used `SIM_FAKE=1`, or no key, or the fake key `sk-ant-invalid` (one rejected HTTP 401 call, no spend). Custom model output came from a harness that imports `sim.py` and monkeypatches `fake_reply`. Nothing in the repo was edited. Scripts and outputs are in the session scratchpad under `breaker/` (`validate.py`, `harness.py`, `cases.py`, `b4b5.py`, `harness.out`).

Methods:
- **Validator**: checks every contract field, plus world rules, the turn limit, Leo's rule, memory ids, importance range, `offer_learned` against the logged turns, and privacy in every prompt. It was run on the baseline, on caps 0 to 61, and on every harness case.
- **Pairing check** (`b4b5.py`): every decide, speak, finale and diary prompt is matched to its retrieval. The memories in the prompt must be exactly the retrieved ids, at most 5, and all from the speaker's own stream.

### Summary

16 FAIL, 21 PASS. No case leaked the key, broke privacy, put a character in two zones, or broke Dana's or Sam's zone limitation.

### Results

| # | Case | How tested | Result |
| --- | --- | --- | --- |
| 1 | API key missing | `env -u ANTHROPIC_API_KEY sim.py --out` | PASS: stderr message, exit 1, valid partial log, `stop_reason: "error: ANTHROPIC_API_KEY not set"` |
| 2 | API key wrong | `ANTHROPIC_API_KEY=sk-ant-invalid` | PASS: exit 2, `error: authentication failed (HTTP 401)`, key appears 0 times in stdout, stderr and log |
| 3 | Model never returns JSON | harness: every reply `"not json at all"` | **FAIL F2** |
| 4 | Some replies are not JSON | every 3rd reply is garbage | PASS: retry, then fallback; contract valid |
| 5 | Code-fenced JSON | every reply wrapped in a json code fence | PASS |
| 6 | JSON with prose around it | `Sure! Here you go: {...} Hope that helps.` | PASS: parsed |
| 7 | Prose with a stray brace, or two JSON objects | `Sure {...} :} bye` / two objects on two lines | **FAIL F11** |
| 8 | Wrong keys | `location`, `line`, `note`, `choice`, `entry` | **FAIL F2** (same cause as case 3) |
| 9 | Wrong types for zone and reason | zone 42, null, object, true; reason a list | PASS: rejected or stringified |
| 10 | importance "high", "7", null | harness | PASS: fallback observation memory, importance 3 |
| 11 | importance 42, -3, 0, 7.9, true | harness | PASS: clamped or cast to 10, 1, 1, 7, 1 |
| 12 | importance NaN, Infinity, 1e400 | harness | **FAIL F1** |
| 13 | Dana leaves the counter at 7am and 8am; Sam asks for back_room | harness: Dana always patio, others always back_room | PASS: rejected with `legal: false`, kept legal |
| 14 | Unknown zones | "rooftop", "", "kitchen; DROP" | PASS: rejected, kept in previous zone |
| 15 | Case and spacing variants | "Back Room", "back room", "window table", "BACK_ROOM", " patio ", "Out" | **FAIL F9**. "BACK_ROOM", " patio " and "Out" pass. |
| 16 | A character in two zones | `locations` checked in every slot of every run | PASS: one key per character in a dict, so this cannot happen |
| 17 | Model always says "out" | harness | PASS: Dana forced to counter at 7am and 8am, shop empty after, 5pm regathers everyone |
| 18 | Leo's money rule, plain words | Leo says "my raise and my pay" with Sam at the counter | PASS: blocked, logged as an observation memory |
| 19 | Leo's money rule, synonyms | Leo says "the chain wanting to buy us and my compensation" with Sam present | **FAIL F4** |
| 20 | Leo's money rule, innocent words | "Happy to help, the espresso is on display, so I'll praise it." | **FAIL F5** |
| 21 | Offer detection | Dana: "Can I offer you a refill? We also sell pastries." | **FAIL F6** |
| 22 | Memory privacy (B3, B10) | Prompts scanned in every run for other characters' goals, limitations and memory texts | PASS. Earlier substring hits were all identical fallback text that sits in both streams. |
| 23 | Retrieval up to 5, only those 5 in the prompt (B4) | pairing check | PASS |
| 24 | Every retrieval logged (B5) | pairing check | PASS. Small artifact: see F12 |
| 25 | 4-turn limit (B9) | validator, all runs | PASS |
| 26 | Empty memory stream when speaking | harness: seed memories removed; also all memory writes disabled | PASS: prompt shows "(no memories yet)", the run completes, contract valid |
| 27 | Call cap mid-day, contract shape | caps 0 to 61, -5 and 500, then the validator | PASS on shape: `finale: null`, `stop_reason: "call_cap"`, every slot has full `locations`. **FAIL F7, F8** |
| 28 | Finale decision variants | "SELL", "Sell", "sell.", "sell " | **FAIL F3** |
| 29 | Very long replies | 100,000-character speak, memory, diary and reason | **FAIL F10** |
| 30 | Empty or None replies (also what a refusal returns) | harness | **FAIL F2** |
| 31 | Empty speak text | `{"text": ""}` | PASS: conversation ends, nothing logged |
| 32 | Whitespace-only memory and diary | harness | PASS: falls back |
| 33 | Diary and turn length | diary "Fine."; turn of 8 sentences | **FAIL F10** |
| 34 | Short or common API key value | `ANTHROPIC_API_KEY` set to "e", "1" or "counter" with fake mode | **FAIL F13** |
| 35 | Contract: prompt purposes | validator | **FAIL F14** |
| 36 | Sam's "reveal only if asked directly" | read the code | **FAIL F15** |
| 37 | Sam's offer knowledge at start | read the code and the log | **FAIL F16** |

### Failures, most severe first

**F1. A NaN or Infinity importance crashes the run, and no log is written.** Code bug. High.
- Input: memory reply `{"memory": "I remember.", "importance": NaN}` (also `Infinity` or `1e400`). Python's `json.loads` accepts all three.
- Observed: `int(importance)` in `add_memory` raises `ValueError` or `OverflowError`. `main()` only catches `CapReached` and `SimError`, so the run dies with a traceback and writes no `events.json`. Every call already spent is lost.
- The same path applies to any unexpected exception, such as an SDK error that is not one of the three caught classes, or a bad `--out` directory (which only fails at the very end).

**F2. If the model keeps failing, the day cannot finish within 100 calls.** Design gap: B8's retry doubles the cost of every call, and B13 does not allow for it. Medium-high.
- Input: every reply is non-JSON, empty, None (a refusal returns `""`), or has wrong keys.
- Observed: `completed=false`, `stop_reason: "call_cap"`, 100 calls, stopped in the 5pm slot, `finale: null`. A normal day already uses up to 81 calls (the `leo_money` case used exactly 81), so a failure rate of about 20% is enough to stop the finale from running.

**F3. Any capitalized "sell" quietly becomes "stay".** Code bug. Medium, because it flips the headline result.
- Input: finale reply `{"decision": "Sell", "reason": "Good money."}` (also "SELL", "sell.", "sell ").
- Observed: `finale.decision: "stay"`, `reason: "fallback: model output did not parse"`. The check is `d.get("decision") in ("sell", "stay")` and never lowercases or strips the value. Dana then announces the opposite of what the model chose.

**F4. Leo's money rule can be dodged with other words.** Design gap: the keyword filter is the only enforcement. Medium.
- Input: Leo says "Dana, about the chain wanting to buy us and my compensation, can we talk?" with Sam at the counter.
- Observed: the turn is kept in the conversation. `MONEY_RE` has no match for "buy us", "compensation", "chain" or "deal". The judge's model call for Leo may fail the run even though the code check passes.

**F5. Leo's money rule blocks harmless words.** Code bug, because the regex matches inside other words. Medium-low.
- Input: Leo says "Happy to help, the espresso is on display, so I'll praise it." with Sam present.
- Observed: every such Leo turn is dropped ("praise" contains "raise"). Other false hits: "repay", "wholesale", "seller", "prepay". Each block also writes a "held my tongue" memory, and that case wrote 8 of them, which crowds Leo's stream.

**F6. Offer spread fires on everyday shop talk.** Contract gap: the keyword list comes from CONTRACT.md. Medium, because it makes the F6 marker in the viewer wrong.
- Input: Dana says "Can I offer you a refill? We also sell pastries." at 7am.
- Observed: `offer_learned: [{leo from dana}, {sam from dana}]` in slot 0, although nobody mentioned the buyout. The regexes also have no word boundaries, so "acquaintance" does not match but "seller" or "upsell" would.

**F7. When the cap hits mid-conversation, the log says someone learned the offer from a conversation it does not contain.** Code bug. Medium-low.
- Input: `--cap 4`, `5`, `6`, `13`, `14` or `15`.
- Observed: for example, cap 4 gives slot 0 `offer_learned: [{"character": "sam", "from": "dana", "zone": "counter"}]` and `knows_offer.sam: true`, but `conversations: []`. `knows` and `offer_learned` are updated per turn, while the conversation is only appended after the turn loop, so the cap exception drops the spoken turns.

**F8. `meta.call_cap` reports the `--cap` value, not 100.** Contract gap or code bug. Low.
- Input: `--cap 10`.
- Observed: `"call_cap": 10`. CONTRACT.md says "Always 100". Either the contract should say "the cap used" or the code should log 100. A judge that checks for 100 would fail every capped test run.

**F9. Natural spellings of zones are rejected instead of normalized.** Design gap. Low.
- Input: Leo or Dana asks for "Back Room", "back room" or "window table".
- Observed: `legal: false`, `override: "'back room' is not a zone; kept at counter"`. The move is safe but wrong, and it counts as an illegal move in the log. Only `.strip().lower()` is applied; spaces are not mapped to underscores.

**F10. Length rules are not enforced.** Design gap. Low.
- Input: a 100,000-character speak, memory, diary or reason; diary "Fine."; a turn of 8 sentences.
- Observed: all stored as given. The fake run wrote a 38 MB `events.json` with prompts up to 700,000 characters. With the real model, `max_tokens=2000` limits this, but "one or two sentences", "3 to 4 sentences" (B11) and "one sentence" reasons are only requests in the prompt.

**F11. A stray brace or a second JSON object defeats the parser.** Code bug. Low.
- Input: `Sure {"zone": "patio", "reason": "sun"} :} bye`, or two JSON objects on separate lines.
- Observed: `requested_zone: null`, fallback after a retry. The greedy `\{.*\}` runs to the last brace. It is safe, but it costs calls and makes F2 more likely.

**F12. A retrieval is logged with no prompt when the cap hits between the two.** Code bug, minor log artifact. Low.
- Input: `--cap 0`, `6`, `15` and others.
- Observed: the last slot has one more retrieval than its prompts. `retrieve()` runs before `call()` checks the cap. The judge's "memories were used" check is not affected.

**F13. A short key value corrupts `events.json`.** Code bug. Low, since real keys are long.
- Input: `ANTHROPIC_API_KEY=e` (or `1`) with `SIM_FAKE=1`.
- Observed: `JSONDecodeError`, because the blanket `text.replace(key, "[REDACTED]")` rewrites `true` and numbers. With the value `counter`, every location becomes `"[REDACTED]"`.

**F14. Prompt purpose "memory" is not in the contract.** Contract gap. Low.
- Observed: B2 memory-writing calls are logged with `purpose: "memory"`, but CONTRACT.md lists only decide, speak, finale and diary (for Retrieval). Prompt purposes are never listed, so a strict reader could reject them.

**F15. Sam's "reveals who she works for only if asked directly" is not enforced by the backend.** Design gap: B7 says the backend enforces limitations. Low-medium.
- Observed: there is no check on Sam's turns, so only the prompt guards it. This is hard to check by code; a model-scored judge check, or a keyword check on "chain" in Sam's turns when nobody asked, would cover it.

**F16. Sam's seed memory says the chain wants to buy, but `knows_offer.sam` starts false.** Design gap. Low.
- Observed: Sam's seed is "The chain I secretly scout for wants to know if Dana will sell the shop". The viewer marker will still show Sam as not knowing until Dana mentions it. The contract fixes only Dana as true at slot 0, so either the contract or the seed should change.
