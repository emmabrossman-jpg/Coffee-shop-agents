# Coffee Shop Generative Agents - Requirements

As of November 20, 2026 - Emma Brossman

## Goal and scope

The build is a one-day simulation of three AI characters in a coffee shop who remember what happens to them, talk to each other, and reach a decision by closing time. It follows the memory-stream idea in Park et al. (2023), cut down to fit a one-hour build.

The assignment asks for three things, and each one is a hard requirement:

- A small community of AI agents (three here).
- Agents remember what happens to them.
- Agents talk with each other over a simulated day.

Out of scope for the hour: reflection (agents summarizing memories into higher-level beliefs), multi-day runs, a database, embeddings, user accounts, and any hosting beyond GitHub Pages.

## World

The world is one independent coffee shop on the day its owner must answer a buyout offer from a chain.

- **Zones (4):** counter, back room, window table, patio.
- **Clock:** 8 time slots, from 7am open to 5pm close.
- **Seeded event:** at 7am, only the owner knows about the offer. The answer is due at close.
- **Movement:** each slot, every character present picks one zone. A character is in exactly one zone or out of the shop.
- **Perception:** characters only see and hear what happens in their own zone.
- **Conversation:** characters sharing a zone talk for at most 4 turns in total per slot.
- **Finale (5pm):** all three meet at the counter. The owner announces sell or stay, and each character writes a short diary entry about the day.

The point to watch is how the offer travels: who knows about it by close, who told them, and how the three diaries differ.

## Characters

Each character has one goal and one limitation. The goals conflict on purpose, and each limitation is written so the judge can check it in the log.

| Character | Role | Goal | Limitation |
| --- | --- | --- | --- |
| Dana | Owner | Decide by close whether to sell, without losing her staff either way | Cannot leave the counter during the two morning-rush slots (7am and 8am) |
| Leo | Barista | Keep his job and get a raise before any sale happens | Never discusses money or the sale while a customer is in the same zone |
| Sam | Regular customer, secretly a scout for the chain | Find out whether Dana will sell, and nudge her toward yes | Reveals who she works for only if asked directly; cannot enter the back room |

These three are defaults. Names, goals, and limitations can change without touching any other section.

## Backend requirements

The backend is one Python script, `sim.py`, that runs the day and writes everything to one file, `events.json`. Memory and decisions live in the backend; the language model only supplies words and choices when asked.

**Memory**

- B1. Each character has its own memory stream: a list of entries with a timestamp, the text, and an importance score from 1 to 10.
- B2. After every conversation, each participant writes its own one-line memory of it, from its own point of view. Two characters in the same conversation may record it differently.
- B3. Memories are private. No character can read another's stream.
- B4. Before a character speaks or decides, the backend retrieves its top 5 memories, scored by recency + importance + keyword overlap with the current situation. Only those 5 go into the prompt.
- B5. Every retrieval is logged: which memories were pulled, for which character, in which slot.

**Decisions**

- B6. Each slot, each character makes one decision with one model call: which zone to go to and why, given its goal, its limitation, and its retrieved memories.
- B7. The backend, not the model, enforces limitations and world rules. If the model picks an illegal move (Dana leaving the counter at 7am, Sam entering the back room), the backend rejects it and keeps the character in a legal zone.
- B8. The model must answer in JSON. If the answer does not parse, retry once, then fall back to a safe default (stay in place, say nothing).

**Conversations**

- B9. Characters in the same zone take turns, 4 turns maximum per zone per slot.
- B10. Each turn's prompt contains: who the character is, its goal, its limitation, its 5 retrieved memories, and the conversation so far. It never contains another character's goal or memories.

**Finale and output**

- B11. At 5pm, Dana decides sell or stay with a one-sentence reason, and each character writes a diary entry of 3 to 4 sentences from its own memories.
- B12. `events.json` holds, per slot: locations, decisions with reasons, conversations, memories written, and memories retrieved. It ends with the decision and the three diaries.
- B13. Hard cap of 100 model calls per run (a full day needs about 85 at most). The script stops cleanly and writes a partial log if the cap is hit.
- B14. The API key is read from an environment variable. It never appears in code, in the log, or in a commit.

## Front end requirements

The front end is one static file, `index.html`, that replays `events.json`. It makes no model calls and has no build step, so GitHub Pages can serve it as is.

- F1. A floor plan of the four zones, showing which characters are in each zone for the current slot.
- F2. The conversation for the current slot, as a chat transcript.
- F3. One panel per character showing its goal, its limitation, and its memory stream up to the current slot, with the memories it just retrieved highlighted.
- F4. Next and previous buttons, plus a clock showing the current slot.
- F5. A final screen with Dana's decision and the three diaries side by side.
- F6. A marker on each character showing whether it knows about the offer yet, so the spread of the secret is visible at a glance.

Locally, it opens by running `python -m http.server` in the project folder and visiting the local address in a browser.

## Breaker and judge

The breaker finds failures and the judge decides whether a run counts. Both run only after `sim.py` works end to end.

**Breaker** - a Claude Code subagent that attacks the simulation and reports what failed, without fixing it. Its findings are saved to `BREAKER_REPORT.md`. Minimum cases:

- The API key is missing or wrong.
- The model returns text that is not valid JSON.
- A character ends up in two zones, or in a zone its limitation forbids.
- A character's prompt contains another character's private memories or goal.
- The call cap is reached mid-day.
- A character has an empty memory stream when asked to speak.

**Judge** - a script, `judge.py`, that reads `events.json` and prints a pass or fail scorecard, also saved to `SCORECARD.md`.

| Check | How it is tested | Type |
| --- | --- | --- |
| Three characters exist, each with a goal and a limitation | Count in the log | Code |
| Each character wrote at least 3 memories | Count per stream | Code |
| Memories were used | At least one retrieved memory per character appears in a later prompt | Code |
| Characters talked across the day | Conversations in at least 4 of 8 slots | Code |
| Every limitation held | Dana at the counter at 7am and 8am; Sam never in the back room; Leo silent on money when Sam shares his zone | Code, plus one model call for Leo |
| A decision was made | Sell or stay recorded at 5pm with a reason | Code |
| Each character pursued its goal | One model call per character, scored 1 to 5 with quoted evidence | Model |

A run passes when every code check passes and no character scores below 3.

## Tech stack and APIs

The build needs exactly one paid service: a chat-model API key. Everything else is free.

| Need | Choice | Why |
| --- | --- | --- |
| Language model API | Anthropic API with a small, fast model (`claude-haiku-5-5`) | This is the characters' brain. A small model keeps a 100-call run quick and cheap |
| API key | Created at console.anthropic.com, stored as the environment variable `ANTHROPIC_API_KEY` | A Claude.ai or Claude Code subscription is separate from API access; the script needs its own key with billing enabled |
| Language | Python 3.10 or later | Matches the plan to build in Python |
| Library | The official Python SDK (`pip install anthropic`) | The only install required |
| Memory storage | Python lists in memory, saved to `events.json` | Three characters and one day produce under 100 memories; a database adds setup and no benefit |
| Memory retrieval | Keyword overlap, scored in plain Python | Avoids a second service |
| Front end | One HTML file with plain JavaScript | No framework, no build step |
| Tracking and viewing | This GitHub repo, with GitHub Pages serving `index.html` and a saved `events.json` | History shows each build step; anyone with the link can replay the day |
| Build tool | Claude Code, using its default subagents | Runs the backend and front end builders in parallel, then the breaker and judge |

Not needed: a vector database, an embeddings API, LangChain or another agent framework, or paid hosting.

The one upgrade worth knowing about is embeddings. The original paper scores relevance by meaning rather than shared keywords (Park et al., 2023), which requires an embeddings API from a second provider. It is a sound next step after the demo works, and a poor use of the first hour.

Set a spend limit in the provider console before the first run. The call cap in B13 limits a single run, and the console limit covers everything else.

## Build order and time budget

The hour works only if the data contract comes first and testing comes last. Each step ends with a commit and a push.

1. **Contract (5 min).** Claude Code writes `CONTRACT.md`, the exact shape of `events.json`. Both builders work against it.
2. **Backend and front end in parallel (25 min).** One subagent builds `sim.py`; another builds `index.html` against a hand-written sample log.
3. **First real run (5 min).** Run the day, open the viewer, and read one full conversation.
4. **Breaker and judge in parallel (15 min).** The breaker reports failures; the judge script produces the scorecard.
5. **Fix and rerun (10 min).** Fix what failed, rerun, and commit the passing `events.json` as the demo copy.

If time runs short, cut in this order: F6, F5, the breaker's last two cases, then the model-scored judge check. The code checks and B1 through B5 are the last things to cut, because they are the assignment.

## Open decisions

- [ ] Is an Anthropic API key with billing set up?
- [ ] Is Claude Code installed and signed in on the laptop being used?
- [ ] Keep Dana, Leo, and Sam as written, or replace their goals and limitations?
- [ ] Does the demo run live in class, or replay the saved `events.json`? A saved run removes the risk of an API failure in front of the room.

## Source

Park, J. S., O'Brien, J. C., Cai, C. J., Morris, M. R., Liang, P., & Bernstein, M. S. (2023). Generative agents: Interactive simulacra of human behavior. *Proceedings of the 36th Annual ACM Symposium on User Interface Software and Technology*. https://doi.org/10.1145/3586183.3606763
