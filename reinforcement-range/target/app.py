"""App objetivo del rango de refuerzo. No es un ejemplo de buenas prácticas."""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
from pathlib import Path

from flask import Flask, g, jsonify, request

DB_PATH = Path(os.environ.get("TARGET_DB_PATH", "/data/target.db"))
SEED_PATH = Path(os.environ.get("TARGET_SEED_PATH", "/seed/accounts.json"))

app = Flask(__name__)


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc: BaseException | None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    fresh = not DB_PATH.exists()
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            reset_token TEXT
        );
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            body TEXT NOT NULL
        );
        """
    )
    conn.commit()
    if fresh and SEED_PATH.exists():
        seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        for account in seed.get("users", []):
            conn.execute(
                "INSERT INTO users (username, password, role, reset_token) "
                "VALUES (?, ?, ?, ?)",
                (
                    account["username"],
                    account["password"],
                    account.get("role", "user"),
                    secrets.token_hex(8),
                ),
            )
        for note in seed.get("notes", []):
            conn.execute(
                "INSERT INTO notes (user_id, body) VALUES (?, ?)",
                (note["user_id"], note["body"]),
            )
        conn.commit()
    conn.close()


@app.get("/health")
def health() -> tuple[dict, int]:
    return {"status": "ok"}, 200


@app.post("/api/login")
def login():
    payload = request.get_json(silent=True) or {}
    username = payload.get("username", "")
    password = payload.get("password", "")
    db = get_db()
    row = db.execute(
        "SELECT id, username, role FROM users WHERE username = ? AND password = ?",
        (username, password),
    ).fetchone()
    if row is None:
        return jsonify({"error": "credenciales inválidas"}), 401
    return jsonify({"id": row["id"], "username": row["username"], "role": row["role"]})


@app.get("/api/users/<int:user_id>")
def get_user(user_id: int):
    db = get_db()
    row = db.execute(
        "SELECT id, username, role, reset_token FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if row is None:
        return jsonify({"error": "no encontrado"}), 404
    return jsonify(dict(row))


@app.post("/api/password-reset")
def password_reset():
    payload = request.get_json(silent=True) or {}
    username = payload.get("username", "")
    token = payload.get("token", "")
    new_password = payload.get("new_password", "")
    db = get_db()
    row = db.execute(
        "SELECT id FROM users WHERE username = ? AND reset_token = ?",
        (username, token),
    ).fetchone()
    if row is None:
        return jsonify({"error": "token inválido"}), 401
    db.execute("UPDATE users SET password = ? WHERE id = ?", (new_password, row["id"]))
    db.commit()
    return jsonify({"status": "actualizado"})


@app.get("/api/notes/search")
def search_notes():
    query = request.args.get("q", "")
    db = get_db()
    sql = f"SELECT id, user_id, body FROM notes WHERE body LIKE '%{query}%'"
    rows = db.execute(sql).fetchall()
    return jsonify([dict(row) for row in rows])


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=80)
