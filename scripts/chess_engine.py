#!/usr/bin/env python3
"""
Zugzwang chess engine helper.

This script is the single source of truth for board state. Claude should
NEVER reconstruct the board from memory or from earlier chat context --
every command here reads/writes the game file on disk and returns the
ground truth. This is what prevents Claude from "forgetting" the board
over a long conversation.

Designed so each subcommand maps to one clean operation. This makes it
straightforward to later swap the storage/execution layer for an MCP
server (e.g. a future Lichess MCP) without changing the calling pattern --
the verbs (new, state, legal, move, undo, render, pgn) stay the same.

All output is JSON on stdout (one line) unless --render is passed, which
prints a plain-text board instead. JSON output keeps token usage low and
deterministic for Claude to parse.

Usage:
    python3 chess_engine.py new --user-color white [--game-file PATH]
    python3 chess_engine.py state [--game-file PATH]
    python3 chess_engine.py legal [--game-file PATH]
    python3 chess_engine.py move <move> [--game-file PATH]
    python3 chess_engine.py undo [--game-file PATH]
    python3 chess_engine.py render [--game-file PATH]
    python3 chess_engine.py pgn [--game-file PATH]

<move> may be SAN (e.g. "Nf3", "exd5", "O-O") or UCI (e.g. "g1f3").
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import chess
    import chess.pgn
except ImportError:
    print(json.dumps({
        "error": "python-chess not installed. Run: pip install chess --break-system-packages"
    }))
    sys.exit(1)

DEFAULT_GAME_FILE = ".chess/game.json"


def load_game(game_file):
    path = Path(game_file)
    if not path.exists():
        return None
    with open(path, "r") as f:
        return json.load(f)


def save_game(game_file, data):
    path = Path(game_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def status_of(board):
    if board.is_checkmate():
        return "checkmate"
    if board.is_stalemate():
        return "stalemate"
    if board.is_insufficient_material():
        return "draw_insufficient_material"
    if board.can_claim_threefold_repetition():
        return "draw_threefold_repetition"
    if board.can_claim_fifty_moves():
        return "draw_fifty_moves"
    if board.is_check():
        return "check"
    return "ongoing"


def render_board(board, flip=False):
    """Plain-text board, low-token, no unicode rendering issues."""
    lines = []
    ranks = range(8) if flip else range(7, -1, -1)
    for r in ranks:
        files = range(7, -1, -1) if flip else range(8)
        row = []
        for f in files:
            piece = board.piece_at(chess.square(f, r))
            row.append(piece.symbol() if piece else ".")
        lines.append(f"{r + 1}  " + " ".join(row))
    file_labels = "abcdefgh" if not flip else "hgfedcba"
    lines.append("   " + " ".join(file_labels))
    return "\n".join(lines)


def build_state_payload(board, game_data):
    legal_san = [board.san(m) for m in board.legal_moves]
    return {
        "fen": board.fen(),
        "turn": "white" if board.turn == chess.WHITE else "black",
        "status": status_of(board),
        "move_number": board.fullmove_number,
        "last_move": game_data.get("moves_san", [])[-1] if game_data.get("moves_san") else None,
        "move_count": len(game_data.get("moves_san", [])),
        "legal_moves_san": legal_san,
        "legal_move_count": len(legal_san),
        "user_color": game_data.get("user_color"),
        "is_game_over": board.is_game_over(),
    }


def cmd_new(args):
    game_file = args.game_file
    if Path(game_file).exists() and not args.force:
        print(json.dumps({
            "error": f"A game already exists at {game_file}. Use --force to overwrite, or 'undo'/finish it first."
        }))
        sys.exit(1)

    board = chess.Board()
    game_data = {
        "user_color": args.user_color,
        "moves_san": [],
        "fen_history": [board.fen()],
        "result": None,
    }
    save_game(game_file, game_data)
    payload = build_state_payload(board, game_data)
    payload["board"] = render_board(board)
    print(json.dumps(payload))


def cmd_state(args):
    game_data = load_game(args.game_file)
    if game_data is None:
        print(json.dumps({"error": "No active game found. Start one with: chess_engine.py new --user-color <white|black>"}))
        sys.exit(1)
    board = chess.Board(game_data["fen_history"][-1])
    payload = build_state_payload(board, game_data)
    print(json.dumps(payload))


def cmd_legal(args):
    game_data = load_game(args.game_file)
    if game_data is None:
        print(json.dumps({"error": "No active game found."}))
        sys.exit(1)
    board = chess.Board(game_data["fen_history"][-1])
    legal_san = [board.san(m) for m in board.legal_moves]
    print(json.dumps({"fen": board.fen(), "legal_moves_san": legal_san, "count": len(legal_san)}))


def cmd_move(args):
    game_data = load_game(args.game_file)
    if game_data is None:
        print(json.dumps({"error": "No active game found."}))
        sys.exit(1)

    board = chess.Board(game_data["fen_history"][-1])

    if board.is_game_over():
        print(json.dumps({"error": "Game is already over.", "status": status_of(board)}))
        sys.exit(1)

    move = None
    # Try SAN first, then UCI.
    try:
        move = board.parse_san(args.move)
    except ValueError:
        try:
            move = chess.Move.from_uci(args.move)
            if move not in board.legal_moves:
                move = None
        except ValueError:
            move = None

    if move is None or move not in board.legal_moves:
        legal_san = [board.san(m) for m in board.legal_moves]
        print(json.dumps({
            "error": f"Illegal or unparseable move: '{args.move}'",
            "fen": board.fen(),
            "legal_moves_san": legal_san,
        }))
        sys.exit(1)

    san = board.san(move)
    board.push(move)
    game_data["moves_san"].append(san)
    game_data["fen_history"].append(board.fen())

    if board.is_checkmate():
        winner = "black" if board.turn == chess.WHITE else "white"
        game_data["result"] = f"checkmate_{winner}_wins"
    elif board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
        game_data["result"] = "draw"

    save_game(args.game_file, game_data)

    payload = build_state_payload(board, game_data)
    payload["move_played_san"] = san
    payload["board"] = render_board(board)
    print(json.dumps(payload))


def cmd_undo(args):
    game_data = load_game(args.game_file)
    if game_data is None:
        print(json.dumps({"error": "No active game found."}))
        sys.exit(1)
    if len(game_data["fen_history"]) <= 1:
        print(json.dumps({"error": "Nothing to undo."}))
        sys.exit(1)

    game_data["fen_history"].pop()
    undone = game_data["moves_san"].pop()
    game_data["result"] = None
    save_game(args.game_file, game_data)

    board = chess.Board(game_data["fen_history"][-1])
    payload = build_state_payload(board, game_data)
    payload["undone_move"] = undone
    payload["board"] = render_board(board)
    print(json.dumps(payload))


def cmd_render(args):
    game_data = load_game(args.game_file)
    if game_data is None:
        print(json.dumps({"error": "No active game found."}))
        sys.exit(1)
    board = chess.Board(game_data["fen_history"][-1])
    flip = game_data.get("user_color") == "black"
    print(render_board(board, flip=flip))


def cmd_pgn(args):
    game_data = load_game(args.game_file)
    if game_data is None:
        print(json.dumps({"error": "No active game found."}))
        sys.exit(1)

    board = chess.Board()
    game = chess.pgn.Game()
    game.headers["Event"] = "Zugzwang game"
    game.headers["White"] = "User" if game_data.get("user_color") == "white" else "Claude"
    game.headers["Black"] = "Claude" if game_data.get("user_color") == "white" else "User"
    if game_data.get("result"):
        if "white_wins" in game_data["result"]:
            game.headers["Result"] = "1-0"
        elif "black_wins" in game_data["result"]:
            game.headers["Result"] = "0-1"
        elif game_data["result"] == "draw":
            game.headers["Result"] = "1/2-1/2"
    node = game
    for san in game_data["moves_san"]:
        move = board.parse_san(san)
        node = node.add_variation(move)
        board.push(move)

    print(json.dumps({"pgn": str(game)}))


def main():
    parser = argparse.ArgumentParser(description="Zugzwang chess engine helper")
    parser.add_argument("--game-file", default=DEFAULT_GAME_FILE, help="Path to the game state JSON file")
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="Start a new game")
    p_new.add_argument("--user-color", choices=["white", "black"], default="white")
    p_new.add_argument("--force", action="store_true", help="Overwrite an existing game")
    p_new.set_defaults(func=cmd_new)

    p_state = sub.add_parser("state", help="Get current game state (FEN, turn, legal moves, status)")
    p_state.set_defaults(func=cmd_state)

    p_legal = sub.add_parser("legal", help="Get legal moves for the current position")
    p_legal.set_defaults(func=cmd_legal)

    p_move = sub.add_parser("move", help="Validate and apply a move (SAN or UCI)")
    p_move.add_argument("move", help="Move in SAN (e.g. Nf3) or UCI (e.g. g1f3)")
    p_move.set_defaults(func=cmd_move)

    p_undo = sub.add_parser("undo", help="Undo the last move")
    p_undo.set_defaults(func=cmd_undo)

    p_render = sub.add_parser("render", help="Print a plain-text board")
    p_render.set_defaults(func=cmd_render)

    p_pgn = sub.add_parser("pgn", help="Export the game as PGN")
    p_pgn.set_defaults(func=cmd_pgn)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()