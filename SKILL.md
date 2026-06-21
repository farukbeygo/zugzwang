---
name: zugzwang
description: Chess-playing skill — play a full game of chess with the user, with Claude as an opponent or analysis partner. Use this whenever the user wants to play chess, start a chess match, make a chess move, resume a chess game, or asks Claude to analyze/comment on a chess position. Critically, ALWAYS use this skill for chess gameplay rather than tracking the board from memory or chat history — long games can exceed context and cause Claude to misremember the position and play illegal or blunder moves. This skill keeps the authoritative board state (FEN/PGN) on disk and validates every move with a real chess library, so the game never desyncs. Trigger on phrases like "let's play chess," "I'll play e4," "what's the position," "make your move," or "show me the board," even mid-game.
---

# Zugzwang

A chess-playing skill built around one rule: **the board state on disk is the only truth.** Claude's own memory of "what the position looks like" is never trusted, no matter how recent the last move was. This is what prevents the classic failure mode of long chess games — Claude losing track of the board after many turns and playing an illegal or nonsensical move.

## Why this matters

Context windows are long but not infinite, and chat history is lossy in subtle ways — pieces get "moved" in Claude's head incorrectly, captures get forgotten, castling rights get misremembered. A chess game can run 40+ moves. Re-deriving the board from the full move history in the chat, every turn, by reasoning alone, is exactly the kind of repetitive bookkeeping a model is unreliable at over long stretches.

So this skill externalizes that bookkeeping entirely into `scripts/chess_engine.py`, a small wrapper around the `python-chess` library. Claude never hand-computes legality, check, checkmate, or stalemate. The script does, every time, from the FEN on disk.

## Setup (first use only)

Check the dependency once per session:

```bash
python3 -c "import chess" 2>/dev/null || pip install chess --break-system-packages -q
```

## Game file location

The game lives at `.chess/game.json` in the user's current working directory by default. If the user is working in a specific project, keep it there so it's easy to find later. All commands below take an optional `--game-file PATH` if the user wants a non-default location (e.g. multiple concurrent games).

## The core loop — follow this exactly every single turn

This is the part that fixes the forgetting problem. Do not skip steps or rely on what you remember the board looking like.

### 1. Starting a new game

Ask the user which color they want (default: let them choose; if they don't care, they're White). Then:

```bash
python3 scripts/chess_engine.py new --user-color white
```

(or `black`). This returns the starting FEN, board render, and legal moves for whoever moves first. Show the user the board (use the `"board"` field, a plain-text ASCII render — cheap and unambiguous) and ask for their move if they're White, or announce yours if you're White.

### 2. Before announcing or playing ANY move (yours or the user's)

**Always re-fetch state first.** Never assume you remember whose turn it is or what the position looks like:

```bash
python3 scripts/chess_engine.py state
```

This returns the current FEN, whose turn it is, the full legal move list in SAN, move count, and game status (ongoing/check/checkmate/stalemate/draw). Read this output, not your memory of the chat, to decide what's happening.

### 3. When the user gives a move

Apply it directly — the script is the legality check, you don't need to pre-validate it yourself:

```bash
python3 scripts/chess_engine.py move "e4"
```

Accepts SAN (`Nf3`, `exd5`, `O-O`, `Qxh7+`) or UCI (`g1f3`). If illegal or unparseable, the script returns an `"error"` field plus the current legal move list — relay this to the user clearly (e.g. "That's not legal right now — your king is in check" or "I don't see that move; did you mean Nf3?") rather than guessing what they meant.

If it succeeds, you get back the new FEN, board render, and status. **Check the `"status"` field before doing anything else** — if it's `"checkmate"`, `"stalemate"`, or a draw variant, the game is over; announce the result, don't continue as if play continues.

### 4. When it's Claude's turn to move

After applying the user's move (step 3), if the game isn't over and it's now your turn:

1. Run `state` (or use the output from the `move` call you just made) to see the current FEN and your legal moves.
2. Reason about which move to play using your own chess judgment — consider material, king safety, development, tactics, threats. You're choosing the move; the script only tells you what's *legal*, not what's *good*.
3. Pick a move **from the `legal_moves_san` list returned by the script** — don't invent a move and hope it's legal.
4. Play it:
   ```bash
   python3 scripts/chess_engine.py move "Nf3"
   ```
5. Give brief commentary on your move (see Commentary section below), then show the resulting board to the user.

### 5. Undo

If the user wants to take back a move ("undo that", "wait, let me redo that"):

```bash
python3 scripts/chess_engine.py undo
```

This pops the last move off the stack (whoever made it) and restores the prior FEN. Only undo one move at a time per call; call it twice if both sides need to take back a full round.

### 6. Showing the board

If the user just wants to see the position without moving (`"show me the board"`, `"what's the position"`):

```bash
python3 scripts/chess_engine.py render
```

This prints a plain-text board oriented from the user's side (flipped automatically if they're playing Black). Cheaper than full `state` JSON when they just want a look.

### 7. Ending / exporting

When the game ends (checkmate/stalemate/draw/resignation) or the user asks for the game record:

```bash
python3 scripts/chess_engine.py pgn
```

Returns a standard PGN string. Offer this to the user if they want to save or replay the game elsewhere (e.g. lichess.org's "paste PGN" analysis board).

## Commentary style

Keep it short — a sentence or two per move, not a full annotation. Good moments to comment:
- Why you chose your move (a developing move, a threat, a defensive necessity)
- Flagging if the user's move hangs material, misses a tactic, or walks into check
- Noting when the position reaches a recognizable opening or a critical moment

Avoid long-winded analysis unless the user explicitly asks for deeper commentary (engine-eval style breakdowns, "explain your reasoning in depth," post-game review). Default to brief; expand on request.

## Token efficiency notes

- Prefer `render` over `state` when only the visual board matters and you don't need the legal-move list.
- Don't re-print the full move history every turn — the script tracks it; only mention recent moves in chat unless the user asks for the full game log (use `pgn` for that).
- Don't ask the script for `legal` separately right before `move` — the `move` and `state` commands already include the legal move list in their output.

## Multiple or resumed games

If `.chess/game.json` already exists and the user asks to start a new game, the `new` command will refuse unless given `--force` — surface this to the user ("There's already a game in progress, want me to overwrite it or finish it first?") rather than silently forcing it.

If the user returns after a break ("let's continue our game," "what was the position again?"), just run `state` — the file persists across the whole session and beyond, since it's on disk, not in context.

## Future compatibility note

This skill currently executes all chess logic via the local `chess_engine.py` script. The command surface (`new`, `state`, `legal`, `move`, `undo`, `render`, `pgn`) is intentionally a thin, stable verb set — if a chess MCP server (e.g. for playing real games on Lichess) becomes available later, the same verbs and flow apply; only the execution layer changes (an MCP tool call instead of a bash command), not how you reason about turns or state.