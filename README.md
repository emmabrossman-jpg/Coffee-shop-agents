# Coffee Shop Agents

A one-day simulation of three AI characters in a coffee shop. Each character has a goal, a limitation, and a private memory of what happens to it. They talk across the day, and the owner decides by close whether to sell the shop to a chain.

Inspired by Park et al. (2023), "Generative Agents: Interactive Simulacra of Human Behavior."

## What is here

| File | Purpose |
| --- | --- |
| `REQUIREMENTS.md` | What the simulation must do, and how it is judged |
| `CLAUDE.md` | Build order and rules for Claude Code |
| `sim.py` | Backend: runs the day, holds memory and decisions, writes `events.json` |
| `index.html` | Viewer: replays `events.json` slot by slot |
| `judge.py` | Scorecard: checks that each requirement and each character's limitation held |

`sim.py`, `index.html`, and `judge.py` are added during the build.

## Run it

```
pip install anthropic
export ANTHROPIC_API_KEY=your-key-here
python sim.py
python judge.py
python -m http.server
```

Then open http://localhost:8000 in a browser.

## Run a new day from the page (local only)

```
.venv/bin/python server.py
```

Then open http://localhost:8000 and click **New day**. It runs `sim.py` with your key and replays the fresh day when it finishes (3 to 5 minutes, a few cents). It needs `ANTHROPIC_API_KEY` in `.env` or the environment. Live runs go to `events_live.json` (ignored by git), so the committed demo `events.json` is never overwritten; the **Demo day** link switches back. The button only appears when `server.py` is running, so it does not show on GitHub Pages. To try it for free, start the server with `SIM_FAKE=1`.

## Source

Park, J. S., O'Brien, J. C., Cai, C. J., Morris, M. R., Liang, P., & Bernstein, M. S. (2023). Generative agents: Interactive simulacra of human behavior. *Proceedings of the 36th Annual ACM Symposium on User Interface Software and Technology*. https://doi.org/10.1145/3586183.3606763
