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

## Source

Park, J. S., O'Brien, J. C., Cai, C. J., Morris, M. R., Liang, P., & Bernstein, M. S. (2023). Generative agents: Interactive simulacra of human behavior. *Proceedings of the 36th Annual ACM Symposium on User Interface Software and Technology*. https://doi.org/10.1145/3586183.3606763
