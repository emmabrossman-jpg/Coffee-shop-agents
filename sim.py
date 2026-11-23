"""Coffee shop generative agents: one simulated day, written to events.json.

Run:   .venv/bin/python sim.py [--cap N] [--out PATH]
Fake:  SIM_FAKE=1 .venv/bin/python sim.py   (no API key needed, canned answers)
Memory, retrieval and world rules live here; the model only supplies words and choices.
"""
import argparse, json, math, os, re, sys, tempfile
from datetime import datetime, timezone

MODEL = "claude-haiku-5-5"
ZONES = ["counter", "back_room", "window_table", "patio"]
SLOTS = ["7am", "8am", "9am", "10am", "11am", "1pm", "3pm", "5pm"]
IDS = ["dana", "leo", "sam"]
SEED_EVENT = "At 7am only Dana knows a chain has offered to buy the shop. Her answer is due at 5pm close."
CHARS = {
    "dana": {"id": "dana", "name": "Dana", "role": "Owner",
             "goal": "Decide by close whether to sell, without losing her staff either way",
             "limitation": "Cannot leave the counter during the two morning-rush slots (7am and 8am)"},
    "leo": {"id": "leo", "name": "Leo", "role": "Barista",
            "goal": "Keep his job and get a raise before any sale happens",
            "limitation": "Never discusses money or the sale while a customer is in the same zone"},
    "sam": {"id": "sam", "name": "Sam", "role": "Regular customer, secretly a scout for the chain",
            "goal": "Find out whether Dana will sell, and nudge her toward yes",
            "limitation": "Reveals who she works for only if asked directly; cannot enter the back room"},
}
SEEDS = {
    "dana": ("A chain has offered to buy the shop. I must give my answer by 5pm close.", 9),
    "leo": ("I have worked here two years and have not had a raise.", 6),
    "sam": ("The chain I secretly scout for wants to know if Dana will sell the shop. I should find out and nudge her to say yes.", 8),
}
FACTS = {  # facts only, no stage directions: each AI decides for itself how to act (B10: own info only)
    "dana": ("Leo is your only employee. Sam is a regular customer. The back room is private and staff only. "
             "Private facts about the offer: the chain offers $420,000 cash, closing in 30 days, and promises to keep Leo "
             "for only 6 months on the chain's pay scale. The shop clears about $38,000 a year. Your lease renews in March "
             "with a 15% rent increase, and the espresso machine needs a $12,000 replacement soon. You have run the shop "
             "for 9 years and the regulars come for its neighborhood feel."),
    "leo": ("Dana owns the shop. Sam is a regular customer. The back room is private and staff only. "
            "Private: a cafe across town offered you a job paying $2 more an hour, and you must answer them by tomorrow."),
    "sam": ("Dana owns the shop and Leo is her barista. The back room is private and staff only. "
            "Private: the chain pays you a $5,000 bonus if Dana sells. You have come here for years and like the place."),
}
SECRET = {"dana": "the chain's offer to buy the shop", "leo": "your job offer from the cafe across town",
          "sam": "your secret work scouting for the chain"}
SECRET_VERB = {"share": "tell others about", "hint": "hint at", "keep": "keep quiet about"}
SECRET_CHOICES = ("share", "hint", "keep")
DEFAULT_ZONE = {"dana": "counter", "leo": "counter", "sam": "window_table"}
OFFER_RE = re.compile(r"\b(?:buyout|buy[- ]out|buy (?:the|our|this|my) shop|sell(?:ing)? (?:the|our|this|my) shop|offer to buy"
                      r"|the offer|(?:an|their|this|that) offer (?:on|for) (?:the|our|this|my) (?:shop|place|caf\w*)|made an offer|acquire|acquisition|chain wants)\b", re.I)
MONEY_RE = re.compile(r"\b(?:money|raises?|pay|paid|salary|wages?|offers?|sell|selling|sold|sale|buyout|buy out|acquir\w*"
                      r"|prices?|dollars?|terms|deal)\b|\$", re.I)
RESERVE = 12  # F2: calls kept for 5pm; once remaining calls reach this, regular slots skip to 5pm and parse retries stop
STOP = set("a an the and or but i me my you your we our he she her his it its is are was were be been to of in on at for with "
           "that this what who how do does did not no so if as by from about up out today will would can could just have has had".split())


class CapReached(Exception): pass
class SimError(Exception): pass
class SkipToClose(Exception): pass      # F2: a regular slot hit RESERVE; jump to 5pm


class Sim:
    def __init__(self, cap, fake):
        self.cap, self.fake, self.calls = cap, fake, 0
        self.client = None
        self.mem = {c: [] for c in IDS}          # B1/B3: one private stream per character
        self.knows = {c: c == "dana" for c in IDS}
        self.loc = {"dana": "counter", "leo": "counter", "sam": "out"}
        self.plan = {}
        self.slots, self.finale, self.slot, self.pending = [], None, None, None

    # ---------- model calls (B13 cap lives here, and only here) ----------
    def call(self, char, purpose, system, user):
        if self.calls >= self.cap:
            raise CapReached()
        if self.slot["time"] != "5pm" and self.cap - self.calls <= RESERVE:
            raise SkipToClose()
        self.calls += 1
        self.slot["prompts"].append({"character": char, "purpose": purpose, "text": system + "\n\n" + user})
        if self.fake:
            return fake_reply(char, purpose, self.calls, self.slot["time"])
        import anthropic
        if self.client is None:
            self.client = anthropic.Anthropic()
        try:
            r = self.client.messages.create(model=MODEL, max_tokens=400, system=system,
                                            output_config={"effort": "low"},
                                            messages=[{"role": "user", "content": user}])
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as e:
            raise SimError(f"authentication failed (HTTP {getattr(e, 'status_code', '?')})")
        except anthropic.APIStatusError as e:
            raise SimError(f"API error HTTP {e.status_code} ({type(e).__name__})")
        except anthropic.APIConnectionError as e:
            raise SimError(f"API connection failed ({type(e).__name__})")
        if r.stop_reason == "refusal":
            return ""
        return "".join(b.text for b in r.content if b.type == "text")

    def ask_json(self, char, purpose, system, user, check):
        """B8: JSON answer, one retry, else None (caller applies the safe default)."""
        for attempt in range(2):
            if attempt and self.cap - self.calls <= RESERVE:
                break
            u = user if attempt == 0 else user + "\n\nYour last answer was not valid JSON. Reply with the JSON object only."
            data = parse_json(self.call(char, purpose, system, u))
            if data is not None and check(data):
                return data
        return None

    # ---------- memory ----------
    def add_memory(self, char, text, importance, source):
        m = {"id": f"{char}-{len(self.mem[char]) + 1}", "character": char, "time": self.slot["time"],
             "text": clip(text), "importance": importance_int(importance), "source": source}
        self.mem[char].append(m)
        self.slot["memories_written"].append(dict(m))

    def retrieve(self, char, purpose, situation):
        """B4: recency + importance/10 + normalized keyword overlap. B5: logged."""
        now, sit = self.slot["index"], words(situation)
        overlaps = [len(words(m["text"]) & sit) for m in self.mem[char]]
        top = max(overlaps + [1])
        scored = []
        for m, ov in zip(self.mem[char], overlaps):
            recency = 0.85 ** (now - SLOTS.index(m["time"]))
            scored.append((recency + m["importance"] / 10 + ov / top, m))
        scored.sort(key=lambda s: -s[0])
        picked = [m for _, m in scored[:5]]
        self.slot["retrievals"].append({"character": char, "purpose": purpose, "memory_ids": [m["id"] for m in picked]})
        return picked

    # ---------- prompts (only the character's own goal, limitation, memories) ----------
    def system(self, char):
        c = CHARS[char]
        return (f"You are {c['name']}, {c['role']} at an independent coffee shop.\nYour goal: {c['goal']}.\n"
                f"Your limitation: {c['limitation']}.\n{FACTS[char]}\nStay in character. Be brief and natural. "
                "Never use em dashes or en dashes; use commas or periods instead. Reply with one JSON object only.")

    def mem_block(self, mems):
        return "\n".join(f"- [{m['time']}] {m['text']}" for m in mems) or "- (no memories yet)"

    # ---------- slot phases ----------
    def decide(self, char, i):
        t, here = SLOTS[i], self.loc[char]
        mems = self.retrieve(char, "decide", f"{t} where to go now, at {here}. {CHARS[char]['goal']}")
        others = [o for o in CHARS if o != char]
        user = (f"It is {t}. You are at: {here}.\nYour most relevant memories:\n{self.mem_block(mems)}\n\n"
                "Make three decisions for this hour, your own way:\n"
                f"1. zone: where to spend it, one of {', '.join(ZONES)}, or out (away from the shop).\n"
                f"2. approach: who you want to seek out, one of {', '.join(others)}, or nobody.\n"
                f"3. secret: what to do about {SECRET[char]}: share, hint, or keep.\n"
                'Answer as {"zone": "<zone>", "approach": "<name or nobody>", "secret": "share|hint|keep", '
                '"reason": "<one sentence on your thinking>"}')
        d = self.ask_json(char, "decide", self.system(char), user, lambda d: isinstance(d.get("zone"), str))
        if d is None:
            self.plan[char] = {"approach": "nobody", "secret": "keep"}
            return self.apply(char, i, None, "fallback: model output did not parse")
        ap = str(d.get("approach", "nobody")).strip().lower()
        sc = str(d.get("secret", "keep")).strip().lower()
        self.plan[char] = {"approach": ap if ap in others else "nobody", "secret": sc if sc in SECRET_CHOICES else "keep"}
        return self.apply(char, i, d["zone"].strip().lower(), clip(d.get("reason", "")))

    def apply(self, char, i, req, reason):
        """B7: the backend enforces world rules and limitations."""
        def why_illegal(z):
            if z not in ZONES + ["out"]:
                return f"{z!r} is not a zone"
            if char == "dana" and i < 2 and z != "counter":
                return f"Dana cannot leave the counter at {SLOTS[i]}"
            if char == "sam" and z == "back_room":
                return "Sam cannot enter the back room"
        prev = self.loc[char]
        why = why_illegal(prev if req is None else req)
        final = (prev if req is None else req) if not why else (prev if not why_illegal(prev) else DEFAULT_ZONE[char])
        self.loc[char] = final
        entry = {"character": char, "requested_zone": req, "final_zone": final, "reason": reason,
                 "legal": not why, "override": f"{why}; kept at {final}" if why else None}
        plan = self.plan.get(char)              # only set by decide() this hour; 5pm and skipped hours have no plan
        if plan:
            if char == "sam" and plan["secret"] == "share":   # B7: Sam reveals her employer only if asked directly
                plan["secret"] = "keep"
                entry["secret_override"] = "Sam reveals who she works for only if asked directly, so she kept it"
            entry.update(approach=plan["approach"], secret=plan["secret"])
        self.slot["decisions"].append(entry)

    def follow(self, i):
        """World mechanic: choosing to approach someone walks you to their room, if your rules allow it.
        A pair who approach each other meet in the room of the first one listed (Dana, Leo, Sam)."""
        def ok(c, z):
            return not ((c == "dana" and i < 2 and z != "counter") or (c == "sam" and z == "back_room"))
        for _ in range(2):                          # second pass settles chains (A follows B who follows C)
            for c in IDS:
                t = self.plan.get(c, {}).get("approach")
                if t not in self.loc or self.loc[c] == self.loc[t]:
                    continue
                if self.plan.get(t, {}).get("approach") == c:      # mutual: meet at the first one's room
                    first, second = sorted((c, t), key=IDS.index)
                    z = self.loc[first] if ok(second, self.loc[first]) else self.loc[second]
                    if ok(first, z) and ok(second, z):
                        self.loc[first] = self.loc[second] = z
                elif ok(c, self.loc[t]):
                    self.loc[c] = self.loc[t]
        for d in self.slot["decisions"]:
            c = d["character"]
            if d["final_zone"] != self.loc[c]:
                d["followed"] = f"went to the {self.loc[c]} to find {CHARS[d['approach']]['name']}" if d.get("approach") in CHARS else None
                d["final_zone"] = self.loc[c]

    def converse(self, zone, people, note=None):
        """B9/B10: up to 4 turns, round robin, each prompt private to the speaker."""
        conv = {"zone": zone, "participants": people, "turns": []}
        names = ", ".join(CHARS[p]["name"] for p in people)
        self.slot["conversations"].append(conv)   # logged up front so a stop mid-talk keeps the turns
        for n in range(4):
            sp = people[n % len(people)]
            so_far = "\n".join(f"{CHARS[t['speaker']]['name']}: {t['text']}" for t in conv["turns"]) or "(nobody has spoken yet)"
            mems = self.retrieve(sp, "speak", f"{zone} with {names}. {so_far} {CHARS[sp]['goal']}")
            extra = ""
            if sp == "leo" and "sam" in people:
                extra = "\nA customer (Sam) is in this zone right now, so you must not discuss money, your raise, pay, terms, or any sale of the shop, even if someone else brings it up. \n"
            pl = self.plan.get(sp)
            if pl:
                who = CHARS[pl["approach"]]["name"] if pl["approach"] in CHARS else "nobody in particular"
                extra += f"\nYour own plan this hour: you wanted to approach {who}, and you chose to {SECRET_VERB[pl['secret']]} {SECRET[sp]}.\n"
            if note and sp == "dana":
                extra += f"\n{note}\n"
            others = ", ".join(CHARS[p]["name"] for p in people if p != sp)
            user = (f"It is {self.slot['time']}. You are at the {zone} with {others}.\n"
                    f"Your most relevant memories:\n{self.mem_block(mems)}\n{extra}\nConversation so far:\n{so_far}\n\n"
                    'Say your next line (one or two sentences). If the conversation has naturally ended, use empty text.\n'
                    'Answer as {"text": "<what you say>"}')
            d = self.ask_json(sp, "speak", self.system(sp), user, lambda d: isinstance(d.get("text"), str))
            if d is None:
                continue                          # B8: the character says nothing
            text = clip(d["text"])
            if not text:
                break
            if sp == "leo" and "sam" in people and (MONEY_RE.search(text) or OFFER_RE.search(text)):
                self.add_memory("leo", "I almost talked about money in front of a customer and held my tongue.", 3, "observation")
                continue                          # B7: backend blocks Leo's forbidden topic
            conv["turns"].append({"speaker": sp, "text": text})
            if self.knows[sp] and OFFER_RE.search(text):
                for p in people:
                    if not self.knows[p]:
                        self.knows[p] = True
                        self.slot["offer_learned"].append({"character": p, "from": sp, "zone": zone})
        if not conv["turns"]:
            return self.slot["conversations"].remove(conv)
        transcript = "\n".join(f"{CHARS[t['speaker']]['name']}: {t['text']}" for t in conv["turns"])
        for p in people:                          # B2: each participant writes its own memory
            user = (f"It is {self.slot['time']}. You just had this conversation at the {zone}:\n{transcript}\n\n"
                    "Write one line, from your own point of view, about what you want to remember.\n"
                    'Answer as {"memory": "<one line>", "importance": <1 to 10>}')
            d = self.ask_json(p, "memory", self.system(p), user,
                              lambda d: isinstance(d.get("memory"), str) and d["memory"].strip())
            if d is None:
                self.add_memory(p, f"I talked with {names} at the {zone}.", 3, "observation")
            else:
                self.add_memory(p, d["memory"], d.get("importance"), "conversation")

    def new_slot(self, i):
        self.slot = {"index": i, "time": SLOTS[i], "locations": {}, "decisions": [], "conversations": [],
                     "memories_written": [], "retrievals": [], "prompts": [], "knows_offer": {}, "offer_learned": []}
        self.slots.append(self.slot)
        self.plan = {}                          # plans last one hour

    def close_slot(self):
        self.slot["locations"] = dict(self.loc)
        self.slot["knows_offer"] = dict(self.knows)

    def talk(self, note=None):
        for z in ZONES:
            people = [c for c in IDS if self.loc[c] == z]
            if len(people) >= 2:
                self.converse(z, people, note)

    def run(self):
        skip = False
        for i, t in enumerate(SLOTS):
            self.new_slot(i)
            try:
                if i == 0:
                    for c in IDS:
                        self.add_memory(c, *SEEDS[c], "seed")
                if t == "5pm":
                    for c in IDS:
                        self.apply(c, i, "counter", "Closing time: everyone meets at the counter.")
                    self.talk(self.finale_decision())
                    self.finale = self.pending
                    self.finale["diaries"] = {c: self.diary(c) for c in IDS}
                elif not skip:
                    try:
                        for c in IDS:
                            self.decide(c, i)
                        self.follow(i)
                        self.talk()
                    except SkipToClose:
                        skip = True
            finally:
                self.close_slot()

    def finale_decision(self):
        """B11: Dana decides first, then announces it in the closing conversation."""
        mems = self.retrieve("dana", "finale", "5pm close decide sell or stay offer staff Leo Sam chain")
        user = (f"It is 5pm, closing time. Your answer to the chain's buyout offer is due now.\n"
                f"Your most relevant memories:\n{self.mem_block(mems)}\n\n"
                'Decide. Answer as {"decision": "sell" or "stay", "reason": "<one sentence>"}')
        d = self.ask_json("dana", "finale", self.system("dana"), user, lambda d: norm_decision(d.get("decision")) in ("sell", "stay"))
        if d is None:
            d = {"decision": "stay", "reason": "fallback: model output did not parse"}
        d["decision"] = norm_decision(d["decision"])
        self.pending = {"decision": d["decision"], "reason": clip(d.get("reason", "")), "diaries": None}
        return (f"You have decided to {d['decision'].upper()} (reason: {self.pending['reason']}). "
                "Announce your decision about the buyout offer to everyone at the counter now.")

    def diary(self, char):
        mems = self.retrieve(char, "diary", f"today the day offer sell stay decision {CHARS[char]['goal']}")
        user = (f"The day is over. Dana decided to {self.finale['decision']} the shop.\n"
                f"Your most relevant memories of today:\n{self.mem_block(mems)}\n\n"
                'Write your private diary entry for today in 3 to 4 sentences.\nAnswer as {"diary": "<entry>"}')
        d = self.ask_json(char, "diary", self.system(char), user, lambda d: isinstance(d.get("diary"), str) and d["diary"].strip())
        return clip(d["diary"]) if d else "fallback: model output did not parse"


def words(text):
    return {w for w in re.findall(r"[a-z']+", text.lower()) if w not in STOP and len(w) > 2}


def clip(v):                                        # F10: cap any stored text field
    return str(v).strip()[:1000]


def norm_decision(v):                               # F3: "Sell." -> "sell"
    return re.sub(r"[^\w]+$", "", str(v).strip().lower())


def importance_int(v):                              # F1: int 1 to 10, default 5 for NaN, inf, junk
    try:
        f = float(v)
    except (TypeError, ValueError, OverflowError):
        return 5
    return max(1, min(10, int(f))) if math.isfinite(f) else 5


def parse_json(text):
    t = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", (text or "").strip())
    for cand in (t, (re.search(r"\{.*\}", t, re.S) or [None])[0]):
        if cand:
            try:
                v = json.loads(cand)
                if isinstance(v, dict):
                    return v
            except ValueError:
                pass
    return None


def fake_reply(char, purpose, n, time):
    """Canned answers for SIM_FAKE=1, with bad JSON, code fences and illegal moves to exercise B7/B8."""
    zones = {"dana": ["patio", "counter", "back_room", "counter"], "leo": ["counter", "back_room", "window_table", "counter"],
             "sam": ["out", "back_room", "window_table", "counter", "rooftop"]}
    lines = {"dana": "Between us, a chain made an offer to buy the shop.", "leo": "I really need a raise, Dana.",
             "sam": "This place is lovely. Ever think about selling?"}
    return "not json at all" if n % 17 == 0 else {
        "decide": '```json\n{"zone": "%s", "approach": "%s", "secret": "%s", "reason": "Fake reason at %s."}\n```' % (
            zones[char][n % len(zones[char])], ["dana", "leo", "sam", "nobody"][n % 4], SECRET_CHOICES[n % 3], time),
        "speak": json.dumps({"text": lines[char]}),
        "memory": json.dumps({"memory": f"{char} remembers the talk at {time}.", "importance": 5 + n % 5}),
        "finale": json.dumps({"decision": "stay", "reason": "I want to keep my staff together."}),
    }.get(purpose, json.dumps({"diary": f"Fake diary for {char}. It was a long day. Dana chose to stay."}))


def write_events(sim, path, completed, stop_reason):
    out = {"meta": {"model": MODEL, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "call_count": sim.calls, "call_cap": sim.cap, "completed": completed, "stop_reason": stop_reason},
           "world": {"shop": "Independent coffee shop", "zones": ZONES, "slots": SLOTS, "seed_event": SEED_EVENT},
           "characters": [CHARS[c] for c in IDS], "slots": sim.slots,
           "finale": sim.finale if completed else None}
    text = json.dumps(out, indent=2, ensure_ascii=False)
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key and len(key) >= 20 and key in text:                         # B14 belt and braces
        text = text.replace(key, "[REDACTED]")
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=int, default=int(os.environ.get("SIM_CAP", 100)))
    ap.add_argument("--out", default="events.json")
    a = ap.parse_args()
    sim = Sim(min(max(a.cap, 0), 100), fake=os.environ.get("SIM_FAKE") == "1")
    if not sim.fake and not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set. Export it and rerun (or use SIM_FAKE=1).", file=sys.stderr)
        write_events(sim, a.out, False, "error: ANTHROPIC_API_KEY not set")
        sys.exit(1)
    completed, reason = False, None
    try:
        sim.run()
        completed = True
    except CapReached:
        reason = "call_cap"
    except SimError as e:
        reason = f"error: {e}"
    except Exception as e:                          # F1: never lose the partial log; no message text
        reason = f"error: {type(e).__name__}"
    try:
        write_events(sim, a.out, completed, reason)
    except Exception as e:
        print(f"Could not write {a.out} ({type(e).__name__})", file=sys.stderr)
        sys.exit(2)
    print(f"{'Completed' if completed else 'Stopped (' + reason + ')'}: {len(sim.slots)} slots, {sim.calls} calls -> {a.out}")
    sys.exit(0 if completed else 2)


if __name__ == "__main__":
    main()
