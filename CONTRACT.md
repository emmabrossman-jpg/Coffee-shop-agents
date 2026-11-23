# events.json contract

`sim.py` writes `events.json`. `index.html` and `judge.py` read it. This file is the only agreement between them. `sample_events.json` is a hand-written example that follows it.

## Fixed values

- Character ids: `dana`, `leo`, `sam`.
- Zone ids: `counter`, `back_room`, `window_table`, `patio`. A character not in the shop has location `out`.
- Slots (8, in order): `7am`, `8am`, `9am`, `10am`, `11am`, `1pm`, `3pm`, `5pm`. Slot `5pm` is the finale: everyone is at the counter.
- Memory ids: `<character>-<n>`, numbered from 1 per character (for example `dana-1`, `dana-2`).

## Top level

```json
{
  "meta": { ... },
  "world": { ... },
  "characters": [ ... ],
  "slots": [ ... ],
  "finale": { ... } | null
}
```

### meta

| Field | Type | Meaning |
| --- | --- | --- |
| `model` | string | Model id used, e.g. `claude-haiku-5-5` |
| `generated_at` | string | ISO 8601 timestamp |
| `call_count` | int | Model calls made in this run |
| `call_cap` | int | The cap used for this run: 100, unless lowered with `--cap` for testing |
| `completed` | bool | `true` if all 8 slots and the finale ran |
| `stop_reason` | string or null | `null` when completed; otherwise `call_cap` or `error: <message>` (never containing the API key) |

### world

```json
{
  "shop": "Independent coffee shop",
  "zones": ["counter", "back_room", "window_table", "patio"],
  "slots": ["7am", "8am", "9am", "10am", "11am", "1pm", "3pm", "5pm"],
  "seed_event": "At 7am only Dana knows a chain has offered to buy the shop. Her answer is due at 5pm close."
}
```

### characters

One object per character, always three:

```json
{ "id": "dana", "name": "Dana", "role": "Owner", "goal": "...", "limitation": "..." }
```

### slots

An array with one object per slot that ran, in order. A partial run (call cap or error) has fewer than 8.

```json
{
  "index": 0,
  "time": "7am",
  "locations": { "dana": "counter", "leo": "counter", "sam": "out" },
  "decisions": [ Decision, ... ],
  "conversations": [ Conversation, ... ],
  "memories_written": [ Memory, ... ],
  "retrievals": [ Retrieval, ... ],
  "prompts": [ Prompt, ... ],
  "knows_offer": { "dana": true, "leo": false, "sam": false },
  "offer_learned": [ { "character": "leo", "from": "dana", "zone": "back_room" } ]
}
```

- `locations` is the state after decisions are applied. Every character appears exactly once.
- If too few calls remain for the 5pm slot (12 kept in reserve), the remaining daytime slots are skipped: they appear with empty `decisions` and `conversations` and unchanged `locations`.
- `knows_offer` is the state at the end of the slot. Once `true`, it stays `true`. Dana is `true` from slot 0.
- `offer_learned` lists who first learned of the offer in this slot and who they heard it from (empty list if nobody). The backend sets it when a character hears a conversation turn that mentions the offer (whole-word, case-insensitive phrases: buyout, buy out, buy the shop, sell the shop, selling the shop, offer to buy, the offer, an offer on (or for) the shop, made an offer, acquire, acquisition, chain wants) spoken by someone who already knows.

#### Decision

```json
{
  "character": "sam",
  "requested_zone": "back_room",
  "final_zone": "window_table",
  "reason": "Model's one-sentence reason for the choice",
  "approach": "dana",
  "secret": "keep",
  "legal": false,
  "override": "Sam cannot enter the back room; kept at window_table"
}
```

`legal` is `false` when the backend rejected the model's choice (B7). `override` is `null` when `legal` is `true`. A parse failure that fell back to the safe default has `legal: true`, `requested_zone: null`, and `reason: "fallback: model output did not parse"`.

Each hour every character makes three decisions in one call: `final_zone` (where to go), `approach` (a character id to seek out, or `nobody`), and `secret` (`share`, `hint` or `keep`) about its own secret: Dana the chain's offer, Leo the rival job offer, Sam that she scouts for the chain. Invalid values fall back to `nobody` and `keep`. Sam choosing `share` is overridden to `keep` (she reveals her employer only if asked directly) and the decision gets an optional `secret_override` string; `legal` and `override` still refer only to the zone. Plans last one hour: the 5pm entries and hours skipped by the call cap have no `approach` or `secret`. After everyone decides, a character who chose to approach someone walks to that person's room if its rules allow it (a pair who approach each other meet in the room of whichever comes first in Dana, Leo, Sam order). When that changes `final_zone`, the decision gets an optional `followed` string such as "went to the counter to find Dana". Older logs without `approach`, `secret` and `followed` are still valid.

#### Conversation

```json
{
  "zone": "counter",
  "participants": ["dana", "leo"],
  "turns": [
    { "speaker": "dana", "text": "..." },
    { "speaker": "leo", "text": "..." }
  ]
}
```

At most 4 turns per conversation, and at most one conversation per zone per slot. Only zones with 2 or more characters have a conversation. A turn whose model output failed to parse is omitted (the character says nothing).

#### Memory

```json
{ "id": "leo-3", "character": "leo", "time": "9am", "text": "Dana told me...", "importance": 7, "source": "conversation" }
```

`source` is one of `seed` (written before the day starts, logged in slot 0), `conversation` (B2, one per participant per conversation), or `observation` (anything else the backend records). `importance` is an int from 1 to 10.

#### Retrieval

```json
{ "character": "leo", "purpose": "decide", "memory_ids": ["leo-3", "leo-1"] }
```

`purpose` is one of `decide`, `speak`, `finale`, `diary`. Up to 5 ids, best first (B4, B5). Retrievals made during the finale are logged in the `5pm` slot.

#### Prompt

```json
{ "character": "leo", "purpose": "speak", "text": "full prompt text sent to the model" }
```

`purpose` is one of `decide`, `speak`, `memory`, `finale`, `diary`. One entry per model call, so judge and breaker can check that prompts contain only the speaker's own goal and memories (B10). Never includes the API key.

### finale

`null` if the run stopped early. Otherwise:

```json
{
  "decision": "stay",
  "reason": "One sentence from Dana.",
  "diaries": { "dana": "3 to 4 sentences.", "leo": "...", "sam": "..." }
}
```
