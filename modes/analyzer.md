# Analyzer mode

Evaluate a **single position** and report the engine's assessment, best move, and main lines. Unlike player mode, you are not playing a game — you are giving an objective, engine-verified read of one position. The numeric evaluation and the candidate moves come from Stockfish via `scripts/analysis.py`; never assert an eval or "best move" from your own head.

## Engine setup (first analysis of a session)
Analysis needs a UCI engine (Stockfish). Check once; install if missing:
```bash
python3 scripts/analysis.py --fen "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1" --depth 8 >/dev/null 2>&1 \
  || echo "Engine missing — install: winget install Stockfish.Stockfish  (or: brew install stockfish / apt install stockfish)"
```
`analysis.py` auto-detects Stockfish on PATH, via `$STOCKFISH_PATH`, the winget install location, or common unix paths. Pass `--engine PATH` to override.

## Getting the position to analyze
Pick whichever source matches the request:
- **The user gives a FEN** → pass it straight through: `--fen "<FEN>"`.
- **A game is in progress** (player mode, or resuming) → analyze the live position: `python3 scripts/analysis.py --game-file .chess/game.json` (the default file is used if `--game-file` is omitted).
- **The user gives a move sequence** (e.g. a PGN or "after 1.e4 c5 2.Nf3…") → build the position on a scratch game file, then analyze it:
  ```bash
  python3 scripts/chess_engine.py --game-file .chess/analyze.json new --force --user-color white
  # push each move: python3 scripts/chess_engine.py --game-file .chess/analyze.json move "e4"  (repeat)
  python3 scripts/analysis.py --game-file .chess/analyze.json
  ```

## Running the analysis
```bash
python3 scripts/analysis.py --fen "<FEN>" --depth 18 --multipv 3
```
- `--depth` (default 18) — raise to 22–26 for sharp/tactical or critical positions; lower for a quick read.
- `--movetime MS` — search by time instead of depth (e.g. `--movetime 2000`).
- `--multipv N` (default 3) — how many candidate moves to return.

The JSON gives `eval` (White's point of view: `+` good for White, `string` like `+0.40` or `+M3` for forced mate), `best_move_san`, and `lines[]` (each with `move_san`, its `eval`, and `pv_san`, the principal variation in SAN).

## Reporting to the user
1. **State the verdict from the engine numbers:** who stands better and by how much. Rough scale: ±0.0–0.3 ≈ balanced, ±0.5–1.0 a clear edge, ±2+ likely winning, `M` = forced mate. Always anchor to the engine's number, not a vibe.
2. **Give the best move and its line** in SAN (from `lines[0]`), plus one or two alternatives if they're close.
3. **Explain *why* in plain terms** — use your chess judgment to translate the engine line into ideas (a tactic, a weak square, king safety, a better pawn structure). This interpretation is yours; flag it as such, while the eval and move ranking are engine-verified.
4. Keep it tight unless the user asks for a deep dive. Render the board (`chess_engine.py render`/`--game-file`) only if it helps them see it.

## Honesty rule
If no engine is installed and the user declines to install one, you may give a *manual* assessment — but say explicitly it is **not** engine-verified, and don't quote numeric evals or claim a definitive best move.
