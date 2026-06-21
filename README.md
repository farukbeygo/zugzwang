# Zugzwang — Chess Skill for Claude Code

A Claude Code skill that lets you play a full game of chess directly in your terminal, with Claude as your opponent or analysis partner.

**The core idea:** Claude's in-context memory of a chess position is unreliable over long games. This skill externalizes all board state to disk and validates every move with a real chess library — so the game never desyncs, even after 60+ moves.

## Features

- Play as White or Black against Claude, or just have Claude analyze a position
- Full move validation via `python-chess` — no illegal moves ever accepted
- Undo any move
- Export the game as PGN (paste into lichess, chess.com, etc.)
- Resumable across sessions — board state survives context resets
- Brief, optional move commentary from Claude
- Token-light by design: a tightly scoped trigger, a condensed skill body, and a small `.chess/notes.md` cheat-sheet so resuming a game doesn't reload the whole skill

## Requirements

- Python 3 with the `python-chess` library:
  ```bash
  pip install chess
  ```

## Installation

1. Copy `SKILL.md` and the `scripts/` folder into your Claude Code skills directory, or drop them alongside your project.
2. Register the skill in your `.claude/settings.json` if needed (depends on your Claude Code version).

## Usage

The skill only activates on an explicit chess request, so it stays out of the way the rest of the time. Just talk naturally to Claude:

- `"Let's play chess"` — starts a new game
- `"I'll play e4"` — makes a move
- `"Analyze this position"` — Claude comments on the current board
- `"Show me the board"` — renders the current position
- `"Undo that"` — takes back the last move
- `"Export the PGN"` — get the full game record
- `"Let's continue our game"` — resumes a game in progress

Claude will handle the rest — fetching state, validating moves, picking its own reply, and showing the board after each turn.

## Example: the Najdorf

Ask Claude to *"play the Najdorf and show me the board"* and it sets up the position move by move, validating each one, then renders it:

```
8  r n b q k b . r
7  . p . . p p p p
6  p . . p . n . .
5  . . . . . . . .
4  . . . N P . . .
3  . . N . . . . .
2  P P P . . P P P
1  R . B Q K B . R
   a b c d e f g h
```

*(uppercase = White, lowercase = Black; White to move)*

This is the **Najdorf Variation** of the Sicilian Defense, reached after **1.e4 c5 2.Nf3 d6 3.d4 cxd4 4.Nxd4 Nf6 5.Nc3 a6**. The defining move is **5...a6** — it denies White's pieces the b5 square and prepares Black's queenside expansion with ...b5, ...Bb7, hitting the e4 pawn. White's main tries from here:

- **6.Be2** — the quiet, classical main line
- **6.Bg5** — the sharp Najdorf, pinning the f6-knight
- **6.Be3** — the English Attack, aiming for f3, g4, and a kingside pawn storm

## How it works

All game logic runs through `scripts/chess_engine.py`, a thin wrapper around `python-chess`. Claude calls it as a subprocess and reads JSON output. The board state is stored in `.chess/game.json` in your working directory.

```
scripts/chess_engine.py new --user-color white
scripts/chess_engine.py state
scripts/chess_engine.py move "e4"
scripts/chess_engine.py undo
scripts/chess_engine.py render
scripts/chess_engine.py pgn
```

## Why "Zugzwang"?

In chess, *zugzwang* is the situation where every move available makes your position worse — you're compelled to move but would rather not. Named after the bug this skill was built to fix: Claude being *forced* to guess a board position from memory and inevitably blundering.

## License

MIT
