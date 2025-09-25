
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

@app.get("/api/whitelist/armaId/<arma_id>")
def get_by_arma_id(arma_id: str):
    if not arma_id:
        abort(400)
    aid = arma_id.strip().lower()
    if not aid:
        abort(400)
    db = get_db()
    try:
        steam_id = run_async(db.get_steam_id_by_arma_id(aid))
        whitelisted = run_async(db.is_whitelisted_by_arma_id(aid))
        if steam_id:
            return jsonify({"whitelisted": whitelisted, "steamId": steam_id})
        else:
            return jsonify({"whitelisted": False, "steamId": None})
    finally:
        run_async(db.close())

@app.get("/api/whitelist/steamId/<steam_id>")
def get_by_steam_id(steam_id: str):
    if not steam_id:
        abort(400)
    sid = steam_id.strip().lower()
    if not sid:
        abort(400)
    db = get_db()
    try:
        arma_id = run_async(db.get_arma_id_by_steam_id(sid))
        whitelisted = run_async(db.is_whitelisted_by_steam_id(sid))
        if arma_id:
            return jsonify({"whitelisted": whitelisted, "armaId": arma_id})
        else:
            return jsonify({"whitelisted": False, "armaId": None})
    finally:
        run_async(db.close())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)


