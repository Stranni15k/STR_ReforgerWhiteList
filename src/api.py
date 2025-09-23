from flask import Flask, Response, jsonify, abort
import asyncio
from typing import Optional

from src.config import get_settings
from src.db import Database

app = Flask(__name__)

def run_async(coro):
    return asyncio.run(coro)

def get_db() -> Database:
    settings = get_settings()
    db = Database(settings.database_path)
    run_async(db.connect())
    return db

@app.get("/api/whitelist")
def get_whitelist():
    db = get_db()
    try:
        arma_ids = run_async(db.list_approved_arma_ids())
        body = "\n".join(arma_ids) + ("\n" if arma_ids else "")
        return Response(body, mimetype="text/plain; charset=utf-8")
    finally:
        run_async(db.close())

@app.get("/api/whitelist/<uid>")
def check_whitelist(uid: str):
    if not uid:
        abort(400)
    u = uid.strip().lower()
    if not u:
        abort(400)
    db = get_db()
    try:
        arma_ids = set(run_async(db.list_approved_arma_ids()))
        return jsonify({"uid": u, "whitelisted": u in arma_ids})
    finally:
        run_async(db.close())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)


