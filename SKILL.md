---
name: zugzwang
description: Chess toolkit — play, analyze, coach, or create puzzles. Trigger ONLY on an explicit chess request, then route to ONE mode and read only that file in modes/. PLAYER — play a game vs Claude ("play chess", "I'll play e4", "your move"). ANALYZER — evaluate a single position or find best moves ("analyze this position", "what's best here"). TEACHER — review the user's own games and coach their weaknesses ("review my games", "help me improve", import from Lichess/Chess.com). TACTICIAN — generate puzzles or opening ideas ("give me a tactics puzzle", "show an opening trap"). Board state lives on disk, validated by python-chess. Do NOT trigger for non-chess requests, and do NOT load more than one mode file.
---

# Zugzwang

A chess toolkit with one rule: **the state on disk is the only source of truth.** Never reconstruct a board from memory or chat history — that is the bug this skill exists to prevent. Legality, check, mate, and evaluation come from the scripts, never from your own reasoning.

## Setup (once per session)
```bash
python3 -c "import chess" 2>/dev/null || pip install chess --break-system-packages -q
```
(Individual modes note any extra dependencies, e.g. the analyzer's engine.)

## Routing — pick ONE mode, read only that file

| The user wants to… | Mode | Read |
|--------------------|------|------|
| Play a game against Claude | **player** | `modes/player.md` |
| Analyze a single position / find the best move | **analyzer** | `modes/analyzer.md` |
| Review their own games and improve | **teacher** | `modes/teacher.md` |
| Get puzzles or opening ideas | **tactician** | `modes/tactician.md` |

Load exactly one mode file — that's the whole point of the split, so don't read the others. If the request is ambiguous (e.g. "let's do some chess"), ask which they want before loading a mode. A session can switch modes later; just load the new file then.

## Session memory (keeps token use low)
On the first chess request of a session, write a tiny `.chess/notes.md` so you don't reload this router or a mode file unnecessarily later:
```
# zugzwang
active mode: <player|analyzer|teacher|tactician>
state file: .chess/game.json   |   user color: <white|black> (player mode)
shared engine: scripts/chess_engine.py  (new · state · move <SAN|UCI> · undo · render · pgn; all take --game-file PATH)
```
On a later turn, read `.chess/notes.md` instead of re-reading this router.

## Shared board engine
All modes share `scripts/chess_engine.py` for board truth (one-line JSON output, `.chess/game.json` by default). Verbs: `new --user-color W|B`, `state`, `move <SAN|UCI>`, `undo`, `render`, `pgn`. Each accepts `--game-file PATH` for concurrent games. Mode files reference it as needed.
