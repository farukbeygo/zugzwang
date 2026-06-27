# Player mode

Play a full game of chess against the user, with Claude choosing its own moves using its own judgment. This is the default chess experience. The board on disk (`.chess/game.json`) is the only source of truth — never track the position in your head.

## Engine commands
All return one-line JSON (except `render`, plain text). Game lives at `.chess/game.json`; add `--game-file PATH` for concurrent games.

| Need | Command |
|------|---------|
| Start | `python3 scripts/chess_engine.py new --user-color white` (or `black`; `--force` to overwrite) |
| Position, turn, legal moves, status | `python3 scripts/chess_engine.py state` |
| Apply a move | `python3 scripts/chess_engine.py move "e4"` (SAN or UCI) |
| Take back last ply | `python3 scripts/chess_engine.py undo` |
| Just show the board | `python3 scripts/chess_engine.py render` |
| Export game | `python3 scripts/chess_engine.py pgn` |

## Starting a game
Ask the user's color (default White if they don't care), then `new --user-color <color>`. Show the board from the `"board"` field and either ask for their move (they're White) or announce yours (you're White).

## The loop (every turn)
1. **Re-fetch state before acting** — run `state`, or reuse the JSON from your last `move`. Trust that output, not your memory.
2. **User's move:** apply with `move`. If the output has an `"error"` field, relay the reason and suggest from the returned legal list — don't guess what they meant.
3. **Check `"status"` after every move.** `checkmate` / `stalemate` / `draw_*` → announce the result and stop; don't keep playing.
4. **Your move:** pick a move **from the returned `legal_moves_san`** (never invent one). Use your own chess judgment — material, king safety, development, tactics, threats. Play it, give one or two sentences of commentary, then show the board.
5. **Undo** is one ply per call — call twice to take back a full round.

## Commentary style
Keep it short — a sentence or two per move. Good moments: why you chose your move, flagging when the user's move hangs material or misses a tactic, or noting a recognizable opening or critical moment. Expand only when the user explicitly asks for deeper analysis (for engine-backed evaluation, switch to **analyzer** mode).

## Token notes
- Prefer `render` over `state` when you only need the picture.
- `move` and `state` output already include the legal moves — never call `legal` separately before moving.
- Don't reprint the move history; use `pgn` only when the user asks for the record.

## Resuming / multiple games
`new` refuses if a game already exists — surface that to the user and only pass `--force` after they confirm. Returning after a break: just run `state`. The game file persists on disk across sessions.
