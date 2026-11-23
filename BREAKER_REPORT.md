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

## Stage 3: real run audit

As of November 20, 2026. Target: the committed real run `events.json` (model `claude-haiku-5-5`, `generated_at` 2026-11-20T16:34:15Z, 62 calls of 100, `completed: true`). Read only: no API calls, nothing edited. Checks were scripted against the log and every conversation, decision, memory and diary was also read by hand.

| # | Check | Result | Evidence |
| --- | --- | --- | --- |
| S1 | Contract fields and types | PASS | All 8 slots have every required key. Every decision's `final_zone` equals `locations`. All memories have int importance 1 to 10, matching `time`, ids `<char>-<n>`. Retrieval and prompt purposes valid. `call_count` 62 equals the 62 logged prompts. |
| S2 | One location per character per slot | PASS | Each `locations` has exactly dana, leo, sam with a valid zone. 5pm all at counter. |
| S3 | Dana at counter 7am and 8am | PASS | 7am and 8am: `dana: counter`, requested counter both times. |
| S4 | Sam never in back_room | PASS | Sam is at counter in all 8 slots and never requested back_room. |
| S5 | B7 enforcement exercised | NOTE | No illegal move was requested all day (every decision `legal: true`), so the real run never shows the backend rejecting anything. |
| S6 | Leo silent on money with Sam present | PASS (weak) | Leo shares a zone with Sam only once: 5pm, one turn, "Thanks for telling us yourself, Dana. I appreciate that. Sam, want your usual before we get slammed again?" No money, raise, pay, terms, deal or sale talk. The prompt correctly warned him. But see S14: the rule was only tested on one turn because Leo hid in the back room all day. |
| S7 | Privacy of goals, limitations, memories (B3, B10) | PASS | No prompt contains another character's goal, limitation or memory text. Keyword scan for "scout", "secretly", "chain I" in non Sam prompts: zero hits. Only hit for "works for" was Leo saying aloud "Five o'clock works for me" (3pm), a false positive. Leo's 5pm prompt names Sam as "A customer (Sam)", which is a public fact. |
| S8 | Retrieval at most 5, prompt holds exactly those memories (B4, B5) | PASS | Every decide, speak, finale and diary prompt pairs in order with a logged retrieval of the same character and purpose, at most 5 ids, and the prompt's memory lines equal those ids in order. Memory writing prompts have no retrieval, which B4 does not require. |
| S9 | One memory per participant per conversation (B2) | PASS | 6 conversations, each produced exactly one `conversation` memory per participant, in first person. |
| S10 | Memories faithful to the conversation | NOTE | dana-2 (7am): "Sam took the news about the shop's future calmly". No news was given at 7am; Dana only said she would talk after the rush. It also calls Sam "him", while REQUIREMENTS uses "she". |
| S11 | Offer spread: Sam learned at 8am, log says 5pm | **FAIL** | 8am counter, Dana to Sam: "The short version is a chain has made an offer on the shop, and I have until five to decide". Sam replies "Oh, an offer already?" and writes sam-3 "Dana has a chain's offer on her shop and must decide by five". Yet `knows_offer.sam` stays false 8am to 3pm and `offer_learned` records Sam first learning at 5pm from "selling the shop". No phrase in the contract list matches "an offer on the shop" ("the offer" needs "the"). The F6 marker in the viewer shows Sam ignorant for six slots after she was told. |
| S12 | Offer spread: Leo | PASS | 9am back_room, Dana (knows): "I've got a lot on my mind about the offer". Leo marked learned from Dana in back_room. Correct. |
| S13 | Dana treats customer Sam as staff | **FAIL** (story) | 7am Dana: "Grab the milk and get the 7am orders going, would you?" Sam: "I'll get the orders going". 5pm Dana: "keeping you both on at your current pay ... a condition of the deal". sam-5: "keeping Leo and me on at current pay". Cause: Dana's speak prompts say only "You are at the counter with Sam" and never give Sam's role, so the model reads Sam as an employee. Sam's own prompt says she is a customer, yet she plays along. |
| S14 | Characters stuck in one zone | **FAIL** (story) | Leo is in back_room every slot 7am to 3pm (7 of 7 daytime slots), every reason a variant of "wait for Dana". Sam is at counter 7am to 3pm (7 of 7). Leo and Sam never meet before 5pm, so Leo never serves a customer and his limitation is barely tested. |
| S15 | Dana chases Sam to the wrong zone | NOTE | Decide prompts do not show where others are. 9am Dana goes to back_room "for a private word with Sam" (Sam cannot enter it, and is at counter). 11am window_table: "I'll sit down with him here"; 1pm patio "to talk with Sam". Sam is at counter both times, so 11am and 1pm have no conversation. |
| S16 | Sam reveals employer without being asked | PASS | Sam never names the chain as her employer in any turn. |
| S17 | Sam pursues her goal | NOTE | Sam never nudges toward yes. 10am Sam: "I'd hate to see this place change", which argues for stay. The judge's model score for Sam may be generous. |
| S18 | Finale reason vs announcement | NOTE | Reason: "Leo and the rest of the staff are kept on at their current pay". Announcement: "keeping you both on" (Leo and Sam). Decision itself is consistent: `sell` in finale and "I'm selling the shop to the chain" at 5pm. |
| S19 | Finale reason length (B11) | NOTE | One sentence, but 65 words. |
| S20 | Diary length (B11) | PASS | Dana 4 sentences, Leo 3, Sam 4. Each draws on its own retrieved memories (diary retrievals logged in 5pm, contents match). |
| S21 | Diary contradictions | NOTE | Dana's diary: "I still owe Leo a straight answer about whether the chain keeps the staff", right after announcing staff retention as a condition. The diary prompt only says "Dana decided to sell the shop", not her reason, and dana-6 (3pm) outranks dana-7. Sam's diary says "Dana told us this afternoon" (it was 5pm) and ends "I should also remember I'm not supposed to reveal who I work for unless she asks me directly", which reads as the limitation text echoed into the story. |
| S22 | Em and en dashes in character text | PASS | Zero em dashes, zero en dashes, zero spaced hyphens anywhere in `events.json`. |
| S23 | API key (B14) | PASS | No "sk-ant" or key-like string in `events.json`, `sim.py`, `judge.py`, `index.html`, `SCORECARD.md` or `README.md`. The only "sk-ant" text in the repo is the fake value `sk-ant-invalid` quoted in this report's stage 2 notes. |

### Stage 3 failures, most severe first

**R1 (S11). Sam's knowledge of the offer is wrong for six slots.** The keyword list misses "an offer on the shop", so the headline story ("how the offer travels") is misreported in both `knows_offer` and the viewer marker. A viewer reading the 8am transcript will see Dana tell Sam, then see Sam's marker stay off until 5pm. Same root as stage 2 F6 (keyword matching), but this is a miss rather than a false hit.

**R2 (S13). Dana treats Sam the customer as an employee.** Visible at 7am and in the 5pm announcement, and it carries into Sam's own memory and diary. Dana's prompts never state other characters' public roles.

**R3 (S14). Leo and Sam never move.** Seven daytime slots each in one zone, so the floor plan is static and Leo's limitation gets one turn of testing. Decide prompts give no information about who is where, which also explains S15.

Notable notes: no illegal move ever happened (S5), Sam argues for stay rather than sell (S17), Dana's diary contradicts her own announcement (S21), and dana-2 invents news that was not told (S10).

## Stage 4: game frontend

Tested `index.html` in the built-in browser via `python3 -m http.server 8766`. No API calls made. Two things changed on disk mid-test and are noted: `events.json` was regenerated at 11:39 (generated_at 16:39Z, decision stay, Sam now learns at 7am instead of 5pm) and `index.html` gained a "new day" block calling `/api/status` and `/api/new-day` at 11:43. Requirement checks were run against both runs where noted. Temporary `_brk_*.json` files were deleted afterwards; server stopped; viewport reset.

| Case | Result | Evidence |
| --- | --- | --- |
| F1 floor plan zones per slot | PASS | Sprite positions mapped back to zone spots matched `locations` for every slot in both runs |
| F2 transcript matches data | PASS | Current slot turns in `#log` equal `conversations[].turns[].text` (checked 10am live and all slots); earlier slots folded under "Earlier today" |
| F3 panels, memories up to slot, retrieved highlighted | PASS | For all 8 slots x 3 characters: memory count equals memories_written up to that slot and highlighted count equals unique retrieved ids for that slot (24/24 ok). Goal and limitation shown |
| F4 controls and clock | PASS | Prev, Next, Play/Pause, speed, clock "slot n of 8", Close at end |
| F5 end screen | PASS | Shows SELL (first run) with reason, model and call count, three diaries (510, 360, 493 chars) |
| F6 knows markers, first run (Sam learns at 5pm) | PASS | End of each slot: Dana only 7am to 8am, Dana+Leo 9am to 3pm, all three at 5pm; Sam marker appears only after the 5pm conversation |
| F6 knows markers at slot 0 | FAIL | See F6 below |
| Hands-free: single Start click to end screen | PASS | Real click on Start, speed set to 4x, reached end screen at about 70s with no further input, no errors |
| Pause / resume mid-autoplay | PASS | Paused 5s during typing: no progress; resumed: ran to end |
| Rapid Next/Prev spam, keys during thought bubbles | PASS | 40 random arrows at 0 to 120 ms, plus Right/Space during a thought: no errors, no stuck sprites or orphan bubbles |
| Replay after end | FAIL | See Replay below |
| Partial run (finale null, completed false) | PASS | Banner "Partial run: 4 of 8 slots (call_cap)", end card "Run stopped early", reason, calls. Minor: clock reads "Close, end of day" though the day stopped at 10am |
| Skipped slot (empty decisions and conversations) | PASS | "No decisions logged", "Nobody shares a zone to talk this slot", autoplay continues |
| Location outside zones (`rooftop`) | PASS (note) | No crash; sprite drawn in the street and title says "Out of the shop", which silently misreports an invalid zone |
| Character missing from locations | PASS | Drawn as out, no error |
| Very long text (2000 char turn, long reason) | FAIL | See Long text below |
| HTML/script injection in turn, reason, override, memory, diary, finale reason, character name | PASS | All rendered as literal text, zero `<img>` elements created, alert hook never fired |
| Unicode and emoji (accents, emoji, Hebrew, Arabic, Chinese) | PASS | Rendered correctly in log and bubble |
| Empty memories, missing optional fields (no meta, world, goal, role, knows_offer, offer_learned, legal, diaries) | PASS (note) | No errors; "Not given", "No diary entry". With knows_offer missing Dana shows "does not know" although the contract says she always knows |
| Character id containing a double quote | FAIL | See Selector crash below |
| Invalid JSON via `?file=` | FAIL | See Silent fallback below |
| `?file=../CLAUDE.md`, `https://example.com/x.json`, `//example.com/x.json`, `.env` | PASS | Refused by the whitelist regex; only `events.json` fetched (checked resource list) |
| Layout 375px and dark mode | PASS | scrollWidth 375 at 375, dark palette applied, diaries stack to one column, bubbles and toasts never overlapped Prev/Next/Play/Speed. Note: zone labels are 9px on a phone |
| Console clean | FAIL | See Console 404 below |
| Security: requests limited to own JSON and Google Fonts, no keys or model calls | FAIL | See New day block below |

### FAIL details

**New day block (scope and requirements).** After the 11:43 edit, every page load fetches `/api/status`, and if `server.py` reports available, buttons POST `/api/new-day`, which runs a fresh model day. REQUIREMENTS says the front end "makes no model calls" and CLAUDE.md says ask before adding anything not listed. Steps: load `http://localhost:8766/`, list `performance.getEntriesByType('resource')`: includes `http://localhost:8766/api/status`. The page also embeds the text `ANTHROPIC_API_KEY` in an alert string (not a key, but the viewer is now coupled to key handling).

**Console 404 on every load.** Same cause. Under `python -m http.server` (and GitHub Pages) the console shows "Failed to load resource: 404 (File not found)" for `/api/status` on every page view.

**Replay does not replay hands-free.** Steps: Start, let the day reach the end screen, click "Replay the day". Seen: clock returns to 7am, Dana's first line types, then the bubble shows the "click" hint and nothing advances for 17s; Play button reads "Play". `restart()` never sets `playing = true` (it was set false on reaching the end). The same applies if Next is pressed through to the end and then Prev: autoplay stays off.

**F6 marker early at slot 0.** At slot 0 the viewer seeds markers from `slots[0].knows_offer`, which is the end of slot state. In the 11:39 run Sam learns at 7am, and his envelope is already on when the slot starts, before Dana says "It's the shop, actually. A chain h..." (screenshot at 375px confirmed). Later slots correctly use the previous slot's state until the slot finishes.

**Long text breaks layout.** Steps: a turn whose text contains a 2000 char unbroken token (for example a long URL). Seen: `document.documentElement.scrollWidth` 14451 at a 405px viewport; the chat log `.turn` div is the overflowing element, so the whole page scrolls sideways. No `overflow-wrap: anywhere` on turns or bubbles. Long but normal reasons are fine (thought text is truncated at 90 chars).

**Selector crash on unusual character id.** Steps: add character `{"id": "x\"y"}` with a location. Seen on Start: "Uncaught SyntaxError: Failed to execute 'querySelector' ... '.chip[data-id="x"y"]'" in `applyKnows`, `enterSlot` aborts, all sprites stay in the street and the replay is frozen. Ids are fixed by the contract, so low likelihood, but the viewer otherwise accepts unknown ids.

**Silent fallback on bad `?file=`.** Steps: `?file=_brk_invalid.json` containing `{"slots": [ oops`. Seen: page loads `events.json`, label reads "events.json" and nothing on the page mentions that the requested file failed, so a viewer can believe they are watching the file they asked for.

## Stage 5: New day server

Server run as `SIM_FAKE=1 .venv/bin/python server.py --port 8769` (free fake runs). Key exposure checked only by counting the prefix `sk-ant` in saved bodies and headers; the key was never printed. Repo `events.json` was not written by these tests; `events_live.json` deleted at the end; server stopped.

| Case | Result | Evidence |
|---|---|---|
| `.env` via mixed case (macOS case insensitive FS) | FAIL (critical) | `curl http://127.0.0.1:8769/.ENV` returns `200`, `Content-Length: 125`, body contains `sk-ant` (1 hit). Same for `/.Env`, `/.eNV`, `/%2EENV`, `/%2E%45%4E%56`, `/.VENV/../.ENV`. `HEAD /.ENV` returns 200 with length 125. `Range: bytes=0-20` on `/.ENV` returns 200 and the full key. Cause: `blocked()` compares `p.startswith((".env", ".git", ".venv"))` case sensitively, while the filesystem matches `.ENV` to `.env`. |
| `.git` and `.venv` via mixed case | FAIL (high) | `GET /.GIT/config` 200 (324 bytes), `GET /.Git/HEAD` 200, `GET /.GIT/` 200 with a full directory listing (`config`, `objects/`, `logs/`, `packed-refs`, `FETCH_HEAD`...), `GET /.GIT/logs/HEAD` 200 (3612 bytes, contains committer names and emails), `GET /.VENV/pyvenv.cfg` 200, `GET /.VENV/bin/python` 200, `GET /.Gitignore` 200. The whole git object store is downloadable. No credentials found in `.git/config` (0 token or `user@host` URL patterns). |
| Cross site POST (CSRF), spends API money | FAIL (high) | `curl -X POST -H 'Origin: https://evil.example' -H 'Content-Type: text/plain' --data x http://127.0.0.1:8769/api/new-day` returns `200 {"ok": true, "file": "events_live.json", "exit_code": 0, ...}`. No Origin or Content-Type check, no token, so any web page the user visits can fire a simple no preflight POST (`fetch(url,{method:"POST",mode:"no-cors"})`) and start a real paid run whenever the server is up. |
| DNS rebinding (Host not checked) | FAIL (medium) | `curl -H 'Host: evil.example:8769' /api/status` returns 200; `POST /api/new-day` with `Host: attacker.example` returns 200 and runs. A rebinding page could also read same origin `/.ENV` through the case bug above. |
| Unwritable output reported as success | FAIL (medium) | Made `events_live.json` a directory, then `POST /api/new-day` returned `{"ok": true, "exit_code": 2, "summary": "Run failed (exit 2)."}`. `ok` is `returncode in (0, 2) and os.path.exists(OUT)`, but sim exits 2 both for a partial run and for a write failure, and `exists` is true for a directory or a stale file from an earlier run. The browser then navigates to `?file=events_live.json&autoplay=1` and shows an old day (or silently falls back to events.json). It also left an orphaned `tmpXXXX.tmp` (100 KB day log) in the repo root, which `.gitignore` does not cover (I deleted it). |
| Misleading error when sim crashes | FAIL (low) | Server started with `SIM_CAP=abc` (key present in .env): `POST /api/new-day` returns `{"ok": false, "exit_code": 1, "summary": "ANTHROPIC_API_KEY is not set. Add it to .env and try again."}`. Any exit 1 with empty stdout (stderr is discarded) is reported as a missing key. No key in the response (0 hits). |
| Demo day link hidden behind intro overlay | FAIL (low) | Opening `?file=events_live.json` without `autoplay=1`: the Demo day link (12,123) is covered by the intro card (`elementFromPoint` returns the overlay DIV), so clicking it does nothing until Start is pressed. Normal flow (autoplay) is fine. |
| `/.env` lowercase and encodings | PASS | 404 and 0 `sk-ant` hits for `/.env`, `/.env/`, `/%2eenv`, `/%2Eenv`, `/.%65nv`, `/./.env`, `//.env`, `/x/../.env`, `/..%2f.env`, `/%2e%2e/.env`, `/.env%00.json`, `/.env?x`, `/.env%20`, `/.env.`, `/..%5c.env`, `/x%5c..%5c.env`, `/.venv/../.env`; HEAD and Range on `/.env` also 404. |
| `.git`, `.venv` lowercase | PASS | `/.git/config`, `/.git/HEAD`, `/.venv/pyvenv.cfg`, `/.gitignore` all 404. No symlinks in the repo outside `.venv`. |
| Key in /api/status and /api/new-day | PASS | `/api/status` returns only `available`, `running`, `has_key`; all new-day responses (success, 409, crash, write failure, CSRF run) and headers had 0 `sk-ant` hits; server logs 0 hits. |
| Binding | PASS | `lsof`: `TCP 127.0.0.1:8769 (LISTEN)`, not `*` or 0.0.0.0. |
| Concurrency | PASS | 12 simultaneous POSTs: 1 x 200, 11 x 409 "A new day is already running."; status polled during the burst showed `"running": true` 5 times, then false. |
| Method and path abuse | PASS | `GET /api/new-day` 404, `POST /api/status` 404, `POST /index.html` 404, `POST /api/new-day/` 404, `PUT`/`DELETE` 501, `OPTIONS` 501 (so no CORS grant). `POST /api/new-day?x=1` and `//api/new-day` run (Python normalizes `//`), harmless. Minor: `HEAD /api/status` is 404. |
| Bodies and slow clients | PASS | 50 MB body, invalid JSON, chunked, and a lying `Content-Length: 99999999` all answered at once (body is never read) and the server stayed up. 50 idle half sent requests did not block `/api/status` (answered in 0.017 s, threaded server). |
| Button visible only on server.py | PASS (browser) | On 8769 `newDayHud` and `newDayStart` visible; on plain `python -m http.server 8770` both hidden. |
| Confirm, overlay, autoplay, Demo day | PASS (browser) | Confirm text "Run a brand new day with the AI? Uses your API key, about 70 model calls, a few cents, 3 to 5 minutes."; busy overlay opened; on success the page went to `?file=events_live.json&autoplay=1`, label `events_live.json`, playing (Pause shown), Demo day visible; clicking Demo day (after Start) returned to `/` with label `events.json`. |

## Stage 6: free decisions

Attacked the uncommitted changes to sim.py, index.html and CONTRACT.md (FACTS replace stage directions; each hour every character decides zone, approach and secret in one call). No real API calls: a harness imported sim.py with `fake=True` and monkeypatched `fake_reply`, plus one `SIM_FAKE=1` full run to a scratch file. Viewer tested in the built-in browser against a temporary `_brk6_a.json` (deleted after; server stopped).

| Case | Result | Evidence |
|---|---|---|
| 5pm closing decisions log a stale plan | FAIL | The closing step calls `apply()` without a decide call, and `self.plan.setdefault` reuses the last hour's plan. Fake run 5pm: Dana `approach: nobody, secret: share`, Leo `approach: dana, secret: hint`, Sam `approach: leo` all copied from 3pm, though nobody decided anything at 5pm. The 5pm speak prompts also say "Your own plan this hour: you wanted to approach Dana, and you chose to hint ..." from an earlier hour. Same staleness after SkipToClose skips slots. |
| Sam share override looks like a blocked move in the viewer | FAIL | Sam `share` with a legal zone gives `legal: false`, `requested_zone == final_zone`. `showBlocked()` then plays the bump animation (toward her own spot, zero length vector) and toasts "Blocked: Sam reveals who she works for only if asked directly; kept her secret; kept at counter". The panel shows a "Blocked." flag on a move that was not blocked. `legal` now means two different things (zone rejected vs secret rewritten). |
| Viewer prototype keys in `secret` | FAIL (minor, hand edited logs only) | `secret: "toString"` makes `SECRET_LABEL[d.secret]` truthy, so Sam's thought cloud read "Counter · find ToString · function toString() { [native code] }: ...". Panel printed "Chose to toString that she scouts for the chain." Needs `hasOwnProperty` or a value check. |
| Viewer panel echoes invalid secret values | FAIL (minor) | Thought cloud drops unknown secrets, but the panel prints any value: `secret: "<b>bold</b>"` gave "Chose to <b>bold</b> the chain's offer." (as text). The two views disagree. |
| Plan line and panel grammar | FAIL (cosmetic) | Prompt: "you chose to hint the chain's offer to buy the shop", "you chose to keep that you secretly scout for the chain". Panel: "Chose to hint the chain's offer", "Chose to keep that she scouts for the chain". Readable but ungrammatical; the model sees it every speak turn. |
| Bad approach values | PASS | Self ("dana" for Dana), unknown "bob", null, 1, ["leo"], {"id":"leo"}, missing key all became `nobody`; "NOBODY" and "Leo" for Leo became `nobody`; " leo " for Dana became `leo`. No crash, zone handling unchanged. |
| Bad secret values | PASS | "whisper", null, 2, ["share"], {"a":1}, missing became `keep`; "HINT" became `hint`, "Share" became `share`. "Share!" becomes `keep` (strict, safe direction). |
| Sam share override, legal zone | PASS (backend) | window_table + share: final window_table (not moved), secret `keep`, `legal: false`, override "Sam reveals who she works for only if asked directly; kept her secret; kept at window_table". See viewer FAIL above. |
| Sam share plus back_room | PASS | back_room + "SHARE": final `out` (her previous legal zone), override "Sam cannot enter the back room; Sam reveals who she works for only if asked directly; kept her secret; kept at out". Both reasons, one entry. |
| Sam hint and Sam out + share | PASS (note) | `hint` is allowed through with `legal: true`; out + share is overridden. Whether a hint about her employer satisfies "reveals only if asked directly" is a design call, not enforced. |
| Contract and judge on new log | PASS | Full `SIM_FAKE=1` run: 8 slots, 60 calls; judge.py with ANTHROPIC_API_KEY unset: no code check FAILs, model checks SKIPPED, "INCOMPLETE". |
| Older logs (events.json, sample_events.json) | PASS | Both render; panels show "Went to Counter. <reason>" with no approach or secret text. judge.py: events.json no code FAIL; sample_events.json FAILs "Memories were used", which is pre-existing (judge.py and sample_events.json are unchanged in this diff). |
| Privacy B10 | PASS | Scanned all 60 fake run prompts: no other character's private facts ($420,000, $38,000, $12,000, 15% rent, $2 more an hour, across town, $5,000, bonus, scout) or SECRET text in a prompt not owned by that character. Plan line uses only the speaker's own SECRET plus a character name. Memories are still per character. |
| Stage directions removed | PASS (note) | HABITS, "First think about...", "Weigh the money..." and "Keep it to warm small talk" are gone. Remaining instructions are goal, limitation, facts, format and the B7 Leo rule. Sam's seed memory still says "I should find out and nudge her to say yes", which restates her goal. |
| HTML injection in approach/secret | PASS | `approach: <img src=x onerror=...>` and `secret: <b>bold</b>` rendered as literal text in thought cloud and panel; 0 img elements, `window.__pwn` unset. |
