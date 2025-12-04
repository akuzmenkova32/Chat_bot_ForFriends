import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any
import json
import time

DB_PATH = Path(__file__).resolve().parent / "tusa.db"

SCHEMA = '''
CREATE TABLE IF NOT EXISTS chats (
  chat_id INTEGER PRIMARY KEY,
  quiet_mode INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  chat_id INTEGER NOT NULL,
  creator_id INTEGER NOT NULL,
  status TEXT NOT NULL,
  times_json TEXT DEFAULT '[]',
  places_json TEXT DEFAULT '[]',
  formats_json TEXT DEFAULT '[]',
  votes_json TEXT DEFAULT '{}',
  final_time TEXT,
  final_place TEXT,
  final_format TEXT,
  start_ts INTEGER NOT NULL,
  voting_msg_id INTEGER,
  fixed_ts INTEGER
);

CREATE INDEX IF NOT EXISTS idx_events_chat_status ON events(chat_id, status);
'''

@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()

def init_db():
    with conn() as c:
        c.executescript(SCHEMA)

def ensure_chat(chat_id: int):
    with conn() as c:
        c.execute("INSERT OR IGNORE INTO chats(chat_id) VALUES (?)", (chat_id,))

def set_quiet(chat_id: int, quiet: bool):
    ensure_chat(chat_id)
    with conn() as c:
        c.execute("UPDATE chats SET quiet_mode=? WHERE chat_id=?", (1 if quiet else 0, chat_id))

def get_quiet(chat_id: int) -> bool:
    ensure_chat(chat_id)
    with conn() as c:
        row = c.execute("SELECT quiet_mode FROM chats WHERE chat_id=?", (chat_id,)).fetchone()
        return bool(row["quiet_mode"]) if row else False

def create_event(chat_id: int, creator_id: int) -> int:
    with conn() as c:
        cur = c.execute(
            "INSERT INTO events(chat_id, creator_id, status, start_ts) VALUES (?, ?, 'collecting', ?)",
            (chat_id, creator_id, int(time.time()))
        )
        return cur.lastrowid

def get_active_event(chat_id: int) -> Optional[sqlite3.Row]:
    with conn() as c:
        return c.execute(
            "SELECT * FROM events WHERE chat_id=? AND status IN ('collecting','voting','fixed') ORDER BY event_id DESC LIMIT 1",
            (chat_id,)
        ).fetchone()

def update_options(event_id: int, times: List[str], places: List[str], formats: List[str]):
    with conn() as c:
        c.execute(
            "UPDATE events SET times_json=?, places_json=?, formats_json=? WHERE event_id=?",
            (json.dumps(times, ensure_ascii=False), json.dumps(places, ensure_ascii=False), json.dumps(formats, ensure_ascii=False), event_id)
        )

def set_status(event_id: int, status: str):
    with conn() as c:
        c.execute("UPDATE events SET status=? WHERE event_id=?", (status, event_id))

def set_voting_msg(event_id: int, msg_id: int):
    with conn() as c:
        c.execute("UPDATE events SET voting_msg_id=? WHERE event_id=?", (msg_id, event_id))

def set_votes(event_id: int, votes: Dict[str, Dict[str, List[int]]]):
    with conn() as c:
        c.execute("UPDATE events SET votes_json=? WHERE event_id=?", (json.dumps(votes), event_id))

def get_votes(event_row: sqlite3.Row) -> Dict[str, Dict[str, List[int]]]:
    return json.loads(event_row["votes_json"] or "{}")

def fix_plan(event_id: int, time_opt: str, place_opt: str, format_opt: str):
    with conn() as c:
        c.execute(
            "UPDATE events SET status='fixed', final_time=?, final_place=?, final_format=?, fixed_ts=? WHERE event_id=?",
            (time_opt, place_opt, format_opt, int(time.time()), event_id)
        )
