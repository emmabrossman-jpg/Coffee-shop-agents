# Build instructions for Claude Code

Build exactly what `REQUIREMENTS.md` specifies. It is the source of truth. Ask before adding anything it does not list.

## Constraints

- Keep it simple: plain Python and the `anthropic` SDK only. `sim.py` stays under about 300 lines.
- Model: `claude-haiku-5-5`. Key: read from the `ANTHROPIC_API_KEY` environment variable.
- Never write an API key into any file, log, or commit. `.gitignore` already excludes `.env`.
- The viewer is `index.html` at the repo root so GitHub Pages can serve it with `events.json`.

## Build order

Work in these steps. After each step, commit with a message naming the step, then push to `main`.

1. **Contract.** You, alone: write `CONTRACT.md` defining the schema of `events.json`, plus a small hand-written `sample_events.json` that follows it.
2. **Build.** Spawn two subagents in parallel:
   - BACKEND builds `sim.py` to requirements B1 through B14.
   - FRONTEND builds `index.html` to requirements F1 through F6, working against `sample_events.json`. It loads `events.json` when present and falls back to the sample.
3. **First run.** Run `sim.py`, confirm `events.json` matches the contract, and confirm the viewer loads it.
4. **Test.** Spawn two subagents in parallel:
   - BREAKER attacks the simulation using the cases in `REQUIREMENTS.md` and writes `BREAKER_REPORT.md`. It reports failures and does not fix them.
   - JUDGE builds `judge.py` to the scorecard table in `REQUIREMENTS.md` and writes `SCORECARD.md`.
5. **Fix.** Fix what the breaker and judge found, rerun, and commit the passing `events.json` and final `SCORECARD.md`.

When finished, show the final scorecard and the command to open the viewer locally.
