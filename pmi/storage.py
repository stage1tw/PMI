"""SQLite 캐시: 지표, 뉴스, 리포트, 수집 로그."""
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

# 테스트 등에서 PMI_DB_PATH 로 DB 위치를 분리할 수 있다.
DB_PATH = Path(os.environ.get("PMI_DB_PATH") or Path(__file__).resolve().parent.parent / "data" / "pmi.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS indicators (
    key TEXT, period TEXT, value REAL, source TEXT, collected_at TEXT,
    PRIMARY KEY (key, period)
);
CREATE TABLE IF NOT EXISTS news (
    category TEXT, title TEXT, link TEXT PRIMARY KEY, published TEXT, source TEXT, collected_at TEXT
);
CREATE TABLE IF NOT EXISTS bids (
    category TEXT, bid_no TEXT PRIMARY KEY, title TEXT, agency TEXT, notice_date TEXT, price REAL, collected_at TEXT
);
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, created_at TEXT,
    pressure_index REAL, ai_used INTEGER, payload TEXT, markdown TEXT
);
CREATE TABLE IF NOT EXISTS collect_log (
    source TEXT, status TEXT, count INTEGER, message TEXT, at TEXT
);
"""


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def now():
    return datetime.now().isoformat(timespec="seconds")


def upsert_indicator(key, period, value, source):
    with closing(connect()) as c, c:
        c.execute("INSERT OR REPLACE INTO indicators VALUES (?,?,?,?,?)", (key, period, value, source, now()))


def get_indicator_series(key):
    with closing(connect()) as c:
        return [dict(r) for r in c.execute("SELECT * FROM indicators WHERE key=? ORDER BY period", (key,))]


def save_news(category, items):
    with closing(connect()) as c, c:
        c.executemany(
            "INSERT OR IGNORE INTO news VALUES (?,?,?,?,?,?)",
            [(category, i["title"], i["link"], i["published"], i["source"], now()) for i in items],
        )


def get_news(category, limit=10):
    with closing(connect()) as c:
        rows = c.execute(
            "SELECT * FROM news WHERE category=? ORDER BY collected_at DESC, published DESC LIMIT ?", (category, limit)
        )
        return [dict(r) for r in rows]


def save_bids(category, items):
    with closing(connect()) as c, c:
        c.executemany(
            "INSERT OR IGNORE INTO bids VALUES (?,?,?,?,?,?,?)",
            [(category, b["bid_no"], b["title"], b["agency"], b["notice_date"], b["price"], now()) for b in items],
        )


def get_bids(category, limit=20):
    with closing(connect()) as c:
        rows = c.execute("SELECT * FROM bids WHERE category=? ORDER BY notice_date DESC LIMIT ?", (category, limit))
        return [dict(r) for r in rows]


def save_report(category, pressure_index, ai_used, payload: dict, markdown: str):
    with closing(connect()) as c, c:
        c.execute(
            "INSERT INTO reports (category, created_at, pressure_index, ai_used, payload, markdown) VALUES (?,?,?,?,?,?)",
            (category, now(), pressure_index, int(ai_used), json.dumps(payload, ensure_ascii=False), markdown),
        )


def list_reports(category=None):
    sql = "SELECT id, category, created_at, pressure_index, ai_used FROM reports"
    args = ()
    if category:
        sql += " WHERE category=?"
        args = (category,)
    with closing(connect()) as c:
        return [dict(r) for r in c.execute(sql + " ORDER BY id DESC", args)]


def get_report(report_id):
    with closing(connect()) as c:
        r = c.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["payload"] = json.loads(d["payload"])
        return d


def latest_report(category):
    with closing(connect()) as c:
        r = c.execute("SELECT id FROM reports WHERE category=? ORDER BY id DESC LIMIT 1", (category,)).fetchone()
    return get_report(r["id"]) if r else None


def log_collect(source, status, count=0, message=""):
    with closing(connect()) as c, c:
        c.execute("INSERT INTO collect_log VALUES (?,?,?,?,?)", (source, status, count, message[:500], now()))


def collect_status():
    with closing(connect()) as c:
        rows = c.execute(
            """SELECT l.* FROM collect_log l
               JOIN (SELECT source, MAX(at) AS at FROM collect_log GROUP BY source) m
               ON l.source=m.source AND l.at=m.at ORDER BY l.source"""
        )
        return [dict(r) for r in rows]
