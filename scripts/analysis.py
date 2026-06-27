#!/usr/bin/env python3
"""
Zugzwang analysis helper — engine-backed position evaluation.

Wraps a UCI engine (Stockfish by default) via python-chess to return a
trustworthy evaluation and the top candidate moves for a position. Used by
the analyzer and tactician modes. As with chess_engine.py, the point is that
Claude never invents an evaluation or a "best move" -- the engine reports it.

Engine discovery (first match wins):
    --engine PATH  >  $STOCKFISH_PATH  >  `stockfish` on PATH  >  known
    winget install location  >  common unix paths.
Install Stockfish with:  winget install Stockfish.Stockfish   (Windows)
                         brew install stockfish / apt install stockfish

Usage:
    python3 analysis.py --fen "<FEN>" [--depth 18] [--multipv 3]
    python3 analysis.py --game-file .chess/game.json        # current position
    python3 analysis.py                                     # default game file
    python3 analysis.py --movetime 1000                     # search by time, ms

Output: one-line JSON on stdout. Evaluations are reported from White's point
of view (positive = good for White), plus a human-readable string.
"""

import argparse
import glob
import json
import os
import shutil
import sys
from pathlib import Path

try:
    import chess
    import chess.engine
except ImportError:
    print(json.dumps({"error": "python-chess not installed. Run: pip install chess --break-system-packages"}))
    sys.exit(1)

DEFAULT_GAME_FILE = ".chess/game.json"


def find_engine(explicit=None):
    """Locate a UCI engine binary across platforms; return path or None."""
    candidates = []
    if explicit:
        candidates.append(explicit)
    if os.environ.get("STOCKFISH_PATH"):
        candidates.append(os.environ["STOCKFISH_PATH"])
    on_path = shutil.which("stockfish")
    if on_path:
        candidates.append(on_path)
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        candidates += glob.glob(
            os.path.join(local, "Microsoft", "WinGet", "Packages",
                         "Stockfish.Stockfish*", "**", "stockfish*.exe"),
            recursive=True,
        )
        candidates.append(os.path.join(local, "Microsoft", "WinGet", "Links", "stockfish.exe"))
    candidates += ["/usr/bin/stockfish", "/usr/local/bin/stockfish", "/opt/homebrew/bin/stockfish"]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


def eval_payload(score):
    """Normalize a PovScore to White's POV with a readable string."""
    w = score.white()
    if w.is_mate():
        m = w.mate()
        return {"type": "mate", "mate_in": m, "white_pov_cp": None,
                "string": f"+M{m}" if m > 0 else f"-M{abs(m)}"}
    cp = w.score()
    return {"type": "cp", "mate_in": None, "white_pov_cp": cp,
            "string": f"{cp / 100:+.2f}"}


def resolve_fen(args):
    """Get the FEN to analyze from --fen, or the last position in a game file."""
    if args.fen:
        return args.fen, None
    game_file = args.game_file or DEFAULT_GAME_FILE
    path = Path(game_file)
    if not path.exists():
        return None, (f"No FEN given and no game file at {game_file}. "
                      f"Pass --fen \"<FEN>\" or start a game with chess_engine.py new.")
    with open(path, "r") as f:
        data = json.load(f)
    history = data.get("fen_history")
    if not history:
        return None, f"Game file {game_file} has no positions."
    return history[-1], None


def main():
    parser = argparse.ArgumentParser(description="Engine-backed chess analysis")
    parser.add_argument("--fen", help="FEN to analyze (overrides --game-file)")
    parser.add_argument("--game-file", help=f"Zugzwang game file (default {DEFAULT_GAME_FILE})")
    parser.add_argument("--depth", type=int, default=18, help="Search depth (default 18)")
    parser.add_argument("--movetime", type=int, help="Search time in ms (overrides --depth)")
    parser.add_argument("--multipv", type=int, default=3, help="Number of top moves to return (default 3)")
    parser.add_argument("--engine", help="Path to a UCI engine (else auto-detect Stockfish)")
    args = parser.parse_args()

    fen, err = resolve_fen(args)
    if err:
        print(json.dumps({"error": err}))
        sys.exit(1)

    try:
        board = chess.Board(fen)
    except ValueError as e:
        print(json.dumps({"error": f"Invalid FEN: {e}"}))
        sys.exit(1)

    if board.is_game_over():
        print(json.dumps({
            "fen": board.fen(),
            "note": "Position is terminal; nothing to analyze.",
            "outcome": str(board.outcome().result()) if board.outcome() else None,
        }))
        return

    engine_path = find_engine(args.engine)
    if not engine_path:
        print(json.dumps({
            "error": "No UCI engine found. Install Stockfish (winget install Stockfish.Stockfish, "
                     "brew install stockfish, or apt install stockfish), or pass --engine PATH."
        }))
        sys.exit(1)

    limit = chess.engine.Limit(time=args.movetime / 1000) if args.movetime else chess.engine.Limit(depth=args.depth)
    multipv = max(1, args.multipv)

    try:
        engine = chess.engine.SimpleEngine.popen_uci(engine_path)
    except Exception as e:
        print(json.dumps({"error": f"Could not start engine at {engine_path}: {e}"}))
        sys.exit(1)

    try:
        infos = engine.analyse(board, limit, multipv=multipv)
    except Exception as e:
        engine.quit()
        print(json.dumps({"error": f"Engine analysis failed: {e}"}))
        sys.exit(1)

    if isinstance(infos, dict):  # multipv=1 can return a single dict
        infos = [infos]

    lines = []
    for rank, info in enumerate(infos, start=1):
        pv = info.get("pv", [])
        if not pv:
            continue
        first = pv[0]
        lines.append({
            "rank": rank,
            "move_san": board.san(first),
            "move_uci": first.uci(),
            "eval": eval_payload(info["score"]),
            "depth": info.get("depth"),
            "pv_san": board.variation_san(pv[:8]),
        })

    engine.quit()

    payload = {
        "fen": board.fen(),
        "turn": "white" if board.turn == chess.WHITE else "black",
        "engine": Path(engine_path).name,
        "depth": args.depth if not args.movetime else None,
        "movetime_ms": args.movetime,
        "eval": lines[0]["eval"] if lines else None,
        "best_move_san": lines[0]["move_san"] if lines else None,
        "best_move_uci": lines[0]["move_uci"] if lines else None,
        "lines": lines,
    }
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
