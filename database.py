import sqlite3
from datetime import datetime, timezone
from config import Config


def get_connection():
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS metrics_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                status TEXT NOT NULL,
                http_code INTEGER NOT NULL,
                cpu_percent REAL NOT NULL,
                ram_percent REAL NOT NULL,
                disk_percent REAL NOT NULL,
                response_time_ms REAL NOT NULL,
                message TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                resolved_at TEXT,
                duration_seconds REAL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL
            )
            """
        )
        conn.commit()


def save_metric(status, http_code, cpu_percent, ram_percent, disk_percent, response_time_ms, message):
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO metrics_history (
                timestamp, status, http_code, cpu_percent, ram_percent, disk_percent, response_time_ms, message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (now, status, http_code, cpu_percent, ram_percent, disk_percent, response_time_ms, message),
        )
        conn.commit()


def sync_incident(is_ok, reason):
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()
    with get_connection() as conn:
        active = conn.execute(
            "SELECT * FROM incidents WHERE status = 'OPEN' ORDER BY id DESC LIMIT 1"
        ).fetchone()

        if not is_ok and active is None:
            conn.execute(
                """
                INSERT INTO incidents (started_at, reason, status)
                VALUES (?, ?, 'OPEN')
                """,
                (now_iso, reason),
            )
            conn.commit()
        elif is_ok and active is not None:
            started_dt = datetime.fromisoformat(active["started_at"])
            duration = round((now_dt - started_dt).total_seconds(), 2)
            conn.execute(
                """
                UPDATE incidents
                SET resolved_at = ?, duration_seconds = ?, status = 'RESOLVED'
                WHERE id = ?
                """,
                (now_iso, duration, active["id"]),
            )
            conn.commit()


def get_recent_metrics(limit=50):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM metrics_history ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_incidents(limit=50):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM incidents ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_summary_stats():
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) AS cnt FROM metrics_history").fetchone()["cnt"]
        ok_count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM metrics_history WHERE status = 'OK'"
        ).fetchone()["cnt"]
        avg_row = conn.execute(
            """
            SELECT
                ROUND(AVG(cpu_percent), 2) AS avg_cpu,
                ROUND(AVG(ram_percent), 2) AS avg_ram,
                ROUND(AVG(disk_percent), 2) AS avg_disk,
                ROUND(AVG(response_time_ms), 2) AS avg_response_ms
            FROM metrics_history
            """
        ).fetchone()
        inc_row = conn.execute(
            """
            SELECT
                COUNT(*) AS total_incidents,
                SUM(CASE WHEN status = 'OPEN' THEN 1 ELSE 0 END) AS open_incidents,
                ROUND(AVG(duration_seconds), 2) AS avg_mttr_seconds
            FROM incidents
            """
        ).fetchone()

    availability = round((ok_count / total) * 100, 3) if total > 0 else 100.0
    return {
        "total_checks": total,
        "successful_checks": ok_count,
        "availability_percent": availability,
        "avg_cpu_percent": avg_row["avg_cpu"] or 0.0,
        "avg_ram_percent": avg_row["avg_ram"] or 0.0,
        "avg_disk_percent": avg_row["avg_disk"] or 0.0,
        "avg_response_time_ms": avg_row["avg_response_ms"] or 0.0,
        "total_incidents": inc_row["total_incidents"] or 0,
        "open_incidents": inc_row["open_incidents"] or 0,
        "avg_mttr_seconds": inc_row["avg_mttr_seconds"] or 0.0,
    }