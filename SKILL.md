---
name: zugzwang
description: Play or analyze a game of chess. Trigger ONLY when the user explicitly asks to play chess, make or take back a chess move, resume a game, see the board, or analyze a chess position — e.g. "play chess", "let's play", "I'll play e4", "what's the position", "undo", "analyze this position". Board state lives on disk and every move is validated by python-chess, so long games never desync. Do NOT trigger for anything that is not an explicit chess request.
---

# Zugzwang

Chess with one rule: **the game file on disk is the only source of truth.** Never reconstruct the board from memory or chat history — that is the exact bug this skill exists to prevent. All legality, check, mate, and draw logic comes from `scripts/chess_engine.py` (a `python-chess` wrapper), never from your own reasoning.

## Setup (once per session)
```bash
python3 -c "import chess" 2>/dev/null || pip install chess --break-system-packages -q
```

## Session memory (do this first — keeps token use low)
On the first chess request of a session, write a tiny `.chess/notes.md` so you don't reload this whole skill later:
```
# zugzwang
cmds: new --user-color W|B · state · move <SAN|UCI> · undo · render · pgn   (all take --game-file PATH)
state file: .chess/game.json   |   user color: <white|black>
resume: python3 scripts/chess_engine.py state
```
On a later turn, or when resuming, read `.chess/notes.md` + run `state` instead of re-reading this file.

## Commands
All return one-line JSON (except `render`, plain text). Game lives at `.chess/game.json`.

| Need | Command |
|------|---------|
| Start | `python3 scripts/chess_engine.py new --user-color white` (or `black`; `--force` to overwrite) |
| Position, turn, legal moves, status | `python3 scripts/chess_engine.py state` |
| Apply a move | `python3 scripts/chess_engine.py move "e4"` (SAN or UCI) |
| Take back last ply | `python3 scripts/chess_engine.py undo` |
| Just show the board | `python3 scripts/chess_engine.py render` |
| Export game | `python3 scripts/chess_engine.py pgn` |

## The loop (every turn)
1. **Re-fetch state before acting** — run `state`, or reuse the JSON from your last `move`. Trust that output, not your memory.
2. **User's move:** apply with `move`. If the output has an `"error"` field, relay the reason and suggest from the returned legal list — don't guess what they meant.
3. **Check `"status"` after every move.** `checkmate` / `stalemate` / `draw_*` → announce the result and stop; don't keep playing.
4. **Your move:** pick a move **from the returned `legal_moves_san`** (never invent one), play it, give one or two sentences of commentary, then show the board.
5. **Undo** is one ply per call — call twice to take back a full round.

## Token notes
- Prefer `render` over `state` when you only need the picture.
- `move` and `state` output already include the legal moves — never call `legal` separately before moving.
- Don't reprint the move history; use `pgn` only when the user asks for the record.

## Resuming / multiple games
`new` refuses if a game already exists — surface that to the user and only pass `--force` after they confirm. Returning after a break: just run `state`. Use `--game-file PATH` for concurrent games.
