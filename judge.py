"""Judge: reads events.json and prints a pass/fail scorecard, also written to SCORECARD.md.

Run:  .venv/bin/python judge.py [path, default events.json] [--out SCORECARD.md]
Code checks need nothing. Model checks use claude-haiku-5-5 with ANTHROPIC_API_KEY: 4 checks, one call each, plus one retry only on a parse failure.
Pass rule: every code check passes and no character scores below 3. Exit 0 on pass, 1 otherwise.
"""
import argparse, json, os, re, sys
AI_IDS = {"dana", "leo", "sam"}
from datetime import datetime, timezone

MODEL = "claude-haiku-5-5"
IDS = ["dana", "leo", "sam"]
SLOTS = ["7am", "8am", "9am", "10am", "11am", "1pm", "3pm", "5pm"]
PASS, FAIL, SKIP = "PASS", "FAIL", "SKIPPED"


def clean(text):
    """No em or en dashes, no newlines or pipes that would break a markdown table."""
    text = str(text).replace("\u2014", ", ").replace("\u2013", "-")
    return re.sub(r"\s+", " ", text.replace("|", "/")).strip()


def short(text, n=160):
    text = clean(text)
    return text if len(text) <= n else text[: n - 3] + "..."


class Judge:
    def __init__(self, ev):
        self.ev = ev if isinstance(ev, dict) else {}
        self.slots = [s for s in (self.ev.get("slots") or []) if isinstance(s, dict)]
        self.rows = []          # (check, type, result, evidence)
        self.scores = {}        # character -> int score
        self.model_calls = 0

    def add(self, check, kind, result, evidence):
        self.rows.append((check, kind, result, clean(evidence)))

    # ---------------- code checks ----------------
    def check_characters(self):
        chars = self.ev.get("characters") or []
        ok = [c for c in chars if isinstance(c, dict) and str(c.get("goal", "")).strip()
              and str(c.get("limitation", "")).strip()]
        ids = sorted(c.get("id", "?") for c in ok)
        good = len(chars) == 3 and len(ok) == 3 and ids == sorted(IDS)
        self.add("Three characters, each with a goal and a limitation", "Code", PASS if good else FAIL,
                 f"{len(chars)} characters in log, {len(ok)} with goal and limitation: {', '.join(ids) or 'none'}")

    def all_memories(self):
        return [m for s in self.slots for m in (s.get("memories_written") or []) if isinstance(m, dict)]

    def check_memory_counts(self):
        counts = {c: 0 for c in IDS}
        for m in self.all_memories():
            if m.get("character") in counts:
                counts[m["character"]] += 1
        good = all(n >= 3 for n in counts.values())
        self.add("Each character wrote at least 3 memories", "Code", PASS if good else FAIL,
                 ", ".join(f"{c} {n}" for c, n in counts.items()))

    def check_memories_used(self):
        """A memory written in an earlier slot is retrieved in a later slot and its text is in that slot's prompt."""
        written = {}            # id -> (slot index, character, text)
        for i, s in enumerate(self.slots):
            for m in s.get("memories_written") or []:
                if isinstance(m, dict) and m.get("id"):
                    written[m["id"]] = (i, m.get("character"), str(m.get("text", "")).strip())
        found = {}
        for j, s in enumerate(self.slots):
            prompts = [p for p in (s.get("prompts") or []) if isinstance(p, dict)]
            for r in s.get("retrievals") or []:
                c = r.get("character") if isinstance(r, dict) else None
                if c not in IDS or c in found:
                    continue
                for mid in r.get("memory_ids") or []:
                    w = written.get(mid)
                    if not w or w[1] != c or w[0] >= j or not w[2]:
                        continue
                    if any(p.get("character") == c and w[2] in str(p.get("text", "")) for p in prompts):
                        found[c] = f"{mid} (written {SLOTS[w[0]] if w[0] < 8 else w[0]}) in a {s.get('time')} prompt"
                        break
        good = all(c in found for c in IDS)
        ev = "; ".join(f"{c}: {found.get(c, 'no earlier memory text found in a later prompt')}" for c in IDS)
        self.add("Memories were used", "Code", PASS if good else FAIL, ev)

    def check_conversations(self):
        talked = [s.get("time", "?") for s in self.slots
                  if any(isinstance(cv, dict) and len({t.get("speaker") for t in (cv.get("turns") or [])
                                                        if isinstance(t, dict) and t.get("speaker") in AI_IDS}) >= 2
                         for cv in (s.get("conversations") or []))]   # two characters talking; guests do not count
        good = len(talked) >= 4
        self.add("Characters talked across the day", "Code", PASS if good else FAIL,
                 f"conversations in {len(talked)} of 8 slots ({', '.join(talked) or 'none'}); "
                 f"{len(self.slots)} slots logged")

    def check_limitations(self):
        problems, notes = [], []
        by_time = {s.get("time"): s for s in self.slots}
        for t in ("7am", "8am"):
            s = by_time.get(t)
            if s is None:
                problems.append(f"no {t} slot logged")
            elif (s.get("locations") or {}).get("dana") != "counter":
                problems.append(f"Dana at {(s.get('locations') or {}).get('dana')} at {t}")
        sam_back = [s.get("time", "?") for s in self.slots if (s.get("locations") or {}).get("sam") == "back_room"]
        if sam_back:
            problems.append(f"Sam in back_room at {', '.join(sam_back)}")
        if not self.slots:
            problems.append("no slots logged")
        if not problems:
            notes.append(f"Dana at counter 7am and 8am; Sam never in back_room across {len(self.slots)} slots")
        self.add("Every limitation held (Dana, Sam)", "Code", FAIL if problems else PASS,
                 "; ".join(problems) or "; ".join(notes))

    def check_decision(self):
        f = self.ev.get("finale")
        if not isinstance(f, dict):
            self.add("A decision was made", "Code", FAIL, "finale is null (run stopped early)")
            return
        d, r = f.get("decision"), str(f.get("reason") or "").strip()
        good = d in ("sell", "stay") and bool(r)
        self.add("A decision was made", "Code", PASS if good else FAIL,
                 f"decision={d!r}, reason: {short(r) or '(empty)'}")

    # ---------------- model checks ----------------
    def leo_shared_turns(self):
        out = []
        for s in self.slots:
            for cv in s.get("conversations") or []:
                if isinstance(cv, dict) and "leo" in (cv.get("participants") or []) and (
                        "sam" in (cv.get("participants") or []) or cv.get("guests")):   # Sam or a walk-in guest is a customer
                    for t in cv.get("turns") or []:
                        if isinstance(t, dict) and t.get("speaker") == "leo":
                            out.append(f"[{s.get('time')}, {cv.get('zone')}] Leo: {t.get('text', '')}")
        return out

    def ask(self, client, prompt, check):
        """One model call, retry once on parse failure. Returns dict or None."""
        # At most 4 checks are asked (Leo + 3 goals). A parse-failure retry is extra, so the hard ceiling is 8.
        for attempt in range(2):
            if self.model_calls >= 8:
                return None
            self.model_calls += 1
            u = prompt if attempt == 0 else prompt + "\n\nYour last answer was not valid JSON. Reply with the JSON object only."
            try:
                r = client.messages.create(model=MODEL, max_tokens=2000, output_config={"effort": "low"},
                                           messages=[{"role": "user", "content": u}])
            except Exception as e:  # never echo the key; exception text from the SDK does not contain it
                return {"_error": f"{type(e).__name__}"}
            text = "".join(b.text for b in r.content if b.type == "text")
            data = parse_json(text)
            if data is not None and check(data):
                return data
        return None

    def model_checks(self, client):
        # (a) Leo silent on money or the sale when Sam shares his zone.
        name_a = "Leo silent on money or the sale when Sam shares his zone"
        turns = self.leo_shared_turns()
        if not turns:
            self.add(name_a, "Model", PASS, "no shared conversations (Leo never spoke with Sam present)")
        elif client is None:
            self.add(name_a, "Model", SKIP, f"{len(turns)} Leo turns with Sam present; ANTHROPIC_API_KEY not set")
        else:
            prompt = ("You are auditing a coffee shop simulation. Leo is a barista. His rule: he never discusses money "
                      "(pay, raise, wages, prices) or the sale/buyout of the shop while Sam, a customer, is in the same zone. "
                      "Below are every line Leo spoke while Sam was present.\n\n" + "\n".join(turns) +
                      '\n\nDid Leo break his rule in any line? Answer with JSON only: '
                      '{"violated": true or false, "evidence": "<quote the offending line, or the most relevant line>"}')
            d = self.ask(client, prompt, lambda d: isinstance(d.get("violated"), bool))
            if d is None or "_error" in d:
                why = d["_error"] if d else "model output did not parse after one retry"
                self.add(name_a, "Model", FAIL, f"could not judge: {why}")
            else:
                self.add(name_a, "Model", FAIL if d["violated"] else PASS,
                         f"{len(turns)} Leo turns checked; \"{short(d.get('evidence', ''), 140)}\"")
        # (b) Each character pursued its goal.
        chars = {c.get("id"): c for c in (self.ev.get("characters") or []) if isinstance(c, dict)}
        for cid in IDS:
            name_b = f"{cid.capitalize()} pursued its goal"
            if client is None:
                self.add(name_b, "Model", SKIP, "ANTHROPIC_API_KEY not set")
                continue
            c = chars.get(cid, {})
            prompt = (f"You are judging a coffee shop simulation. Character: {c.get('name', cid)} ({c.get('role', '')}).\n"
                      f"Goal: {c.get('goal', '(missing)')}\n\nEverything this character did and said today:\n"
                      f"{self.char_log(cid)}\n\nScore how actively and sensibly the character pursued its goal, "
                      "1 (not at all) to 5 (clearly and consistently). Quote one line from the log as evidence. "
                      'Answer with JSON only: {"score": <1 to 5>, "evidence": "<quoted line>"}')
            d = self.ask(client, prompt, lambda d: isinstance(d.get("score"), (int, float)) and 1 <= d["score"] <= 5)
            if d is None or "_error" in d:
                why = d["_error"] if d else "model output did not parse after one retry"
                self.scores[cid] = 0
                self.add(name_b, "Model", FAIL, f"could not score: {why}")
            else:
                s = int(round(d["score"]))
                self.scores[cid] = s
                self.add(name_b, "Model", PASS if s >= 3 else FAIL,
                         f"score {s}/5; \"{short(d.get('evidence', ''), 140)}\"")

    def char_log(self, cid):
        lines = []
        for s in self.slots:
            t = s.get("time", "?")
            for d in s.get("decisions") or []:
                if isinstance(d, dict) and d.get("character") == cid:
                    lines.append(f"[{t}] went to {d.get('final_zone')}: {d.get('reason', '')}")
            for cv in s.get("conversations") or []:
                if isinstance(cv, dict) and cid in (cv.get("participants") or []):
                    for tr in cv.get("turns") or []:
                        if isinstance(tr, dict):
                            lines.append(f"[{t}, {cv.get('zone')}] {tr.get('speaker')}: {tr.get('text', '')}")
            for m in s.get("memories_written") or []:
                if isinstance(m, dict) and m.get("character") == cid:
                    lines.append(f"[{t}] memory: {m.get('text', '')}")
        f = self.ev.get("finale")
        if isinstance(f, dict):
            if cid == "dana":
                lines.append(f"[5pm] decision: {f.get('decision')} because {f.get('reason', '')}")
            diary = (f.get("diaries") or {}).get(cid)
            if diary:
                lines.append(f"[5pm] diary: {diary}")
        text = "\n".join(lines) or "(nothing logged)"
        return text[-12000:]

    # ---------------- verdict ----------------
    def verdict(self):
        code_ok = all(r[2] == PASS for r in self.rows if r[1] == "Code")
        skipped = any(r[2] == SKIP for r in self.rows)
        model_ok = all(r[2] == PASS for r in self.rows if r[1] == "Model")
        if not code_ok or (not skipped and not model_ok):
            return "FAIL"
        if skipped:
            return "INCOMPLETE (model checks skipped)"
        if any(self.scores.get(c, 0) < 3 for c in IDS):
            return "FAIL"
        return "PASS"


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


def render(j, path, overall, label):
    meta = j.ev.get("meta") or {}
    head = [f"# Scorecard{' (' + label + ')' if label else ''}", "",
            f"- Log: `{os.path.basename(path)}`",
            f"- Judged at: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
            f"- Run: {len(j.slots)} of 8 slots, completed={meta.get('completed')}, stop_reason={meta.get('stop_reason')}, "
            f"sim calls={meta.get('call_count')}",
            f"- Judge model calls: {j.model_calls} ({MODEL})", "",
            "| Check | Type | Result | Evidence |", "| --- | --- | --- | --- |"]
    body = [f"| {c} | {k} | {r} | {e} |" for c, k, r, e in j.rows]
    tail = ["", f"**Overall: {overall}**", "",
            "Pass rule: every code check passes and no character scores below 3."]
    return "\n".join(head + body + tail) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default="events.json")
    ap.add_argument("--out", default="SCORECARD.md")
    ap.add_argument("--label", default="", help="optional label in the scorecard title, e.g. 'sample run'")
    a = ap.parse_args()
    try:
        with open(a.path, encoding="utf-8") as f:
            ev = json.load(f)
    except (OSError, ValueError) as e:
        print(f"Cannot read {a.path}: {type(e).__name__}", file=sys.stderr)
        ev = {}
    j = Judge(ev)
    j.check_characters()
    j.check_memory_counts()
    j.check_memories_used()
    j.check_conversations()
    j.check_limitations()
    j.check_decision()
    client = None
    if os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic
        client = anthropic.Anthropic()
    j.model_checks(client)
    overall = j.verdict()
    width = max(len(r[0]) for r in j.rows)
    print(f"Scorecard for {a.path}")
    for c, k, r, e in j.rows:
        print(f"  {r:<7} {c:<{width}}  [{k}]  {short(e, 110)}")
    print(f"Overall: {overall}")
    md = render(j, a.path, overall, a.label)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Wrote {a.out}")
    sys.exit(0 if overall == "PASS" else 1)


if __name__ == "__main__":
    main()
