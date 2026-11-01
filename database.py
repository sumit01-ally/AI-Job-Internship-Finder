"""
Database module - SQLite setup and helper functions.
All tables: users, jobs, saved_jobs, applications, monitoring_history
"""

import sqlite3
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DATABASE_PATH", "jobfinder.db")


def get_db():
    """Get a database connection with row_factory for dict-like access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize all database tables."""
    conn = get_db()
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            skills TEXT DEFAULT '',
            interests TEXT DEFAULT '',
            preferred_location TEXT DEFAULT '',
            experience_level TEXT DEFAULT 'fresher',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Jobs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT DEFAULT '',
            job_type TEXT DEFAULT 'full-time',
            work_mode TEXT DEFAULT 'on-site',
            description TEXT DEFAULT '',
            skills_required TEXT DEFAULT '',
            salary TEXT DEFAULT '',
            deadline TEXT DEFAULT '',
            apply_url TEXT DEFAULT '',
            source_url TEXT DEFAULT '',
            is_internship INTEGER DEFAULT 0,
            is_expired INTEGER DEFAULT 0,
            discovered_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(title, company, apply_url)
        )
    """)

    # Saved Jobs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS saved_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            job_id INTEGER NOT NULL,
            saved_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
            UNIQUE(user_id, job_id)
        )
    """)

    # Applications table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            job_id INTEGER NOT NULL,
            status TEXT DEFAULT 'applied',
            applied_at TEXT DEFAULT (datetime('now')),
            notes TEXT DEFAULT '',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
            UNIQUE(user_id, job_id)
        )
    """)

    # Monitoring history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS monitoring_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_query TEXT NOT NULL,
            location TEXT DEFAULT '',
            jobs_found INTEGER DEFAULT 0,
            new_jobs INTEGER DEFAULT 0,
            status TEXT DEFAULT 'completed',
            ran_at TEXT DEFAULT (datetime('now')),
            details TEXT DEFAULT ''
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] Database initialized successfully.")


def row_to_dict(row):
    """Convert sqlite3.Row to plain dict."""
    if row is None:
        return None
    return dict(row)


def rows_to_list(rows):
    """Convert list of sqlite3.Row to list of dicts."""
    return [dict(r) for r in rows]


# ─── User helpers ────────────────────────────────────────────────────────────

def create_user(name, email, password_hash, skills="", interests="",
                preferred_location="", experience_level="fresher"):
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO users (name, email, password_hash, skills, interests,
                               preferred_location, experience_level)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, email, password_hash, skills, interests,
              preferred_location, experience_level))
        conn.commit()
        return True, "Account created successfully."
    except sqlite3.IntegrityError:
        return False, "Email already registered."
    finally:
        conn.close()


def get_user_by_email(email):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return row_to_dict(row)


def get_user_by_id(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return row_to_dict(row)


def update_user_profile(user_id, skills, interests, preferred_location, experience_level):
    conn = get_db()
    conn.execute("""
        UPDATE users SET skills=?, interests=?, preferred_location=?,
        experience_level=?, updated_at=datetime('now') WHERE id=?
    """, (skills, interests, preferred_location, experience_level, user_id))
    conn.commit()
    conn.close()


# ─── Job helpers ─────────────────────────────────────────────────────────────

def save_job_to_db(title, company, location="", job_type="full-time",
                   work_mode="on-site", description="", skills_required="",
                   salary="", deadline="", apply_url="", source_url="",
                   is_internship=False):
    """Insert a job, ignoring duplicates. Returns (job_id, is_new)."""
    conn = get_db()
    try:
        cursor = conn.execute("""
            INSERT OR IGNORE INTO jobs
            (title, company, location, job_type, work_mode, description,
             skills_required, salary, deadline, apply_url, source_url, is_internship)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, company, location, job_type, work_mode, description,
              skills_required, salary, deadline, apply_url, source_url,
              1 if is_internship else 0))
        conn.commit()
        if cursor.rowcount > 0:
            return cursor.lastrowid, True
        # Already exists — find the id
        row = conn.execute(
            "SELECT id FROM jobs WHERE title=? AND company=? AND apply_url=?",
            (title, company, apply_url)
        ).fetchone()
        return (row["id"] if row else None), False
    finally:
        conn.close()


def get_all_jobs(is_internship=None, limit=50, offset=0):
    conn = get_db()
    if is_internship is None:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE is_expired=0 ORDER BY discovered_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE is_internship=? AND is_expired=0 ORDER BY discovered_at DESC LIMIT ? OFFSET ?",
            (1 if is_internship else 0, limit, offset)
        ).fetchall()
    conn.close()
    return rows_to_list(rows)


def get_job_by_id(job_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    return row_to_dict(row)


def search_jobs_in_db(query="", location="", is_internship=None, work_mode=""):
    conn = get_db()
    sql = "SELECT * FROM jobs WHERE is_expired=0"
    params = []
    if query:
        sql += " AND (title LIKE ? OR description LIKE ? OR skills_required LIKE ? OR company LIKE ?)"
        q = f"%{query}%"
        params.extend([q, q, q, q])
    if location:
        sql += " AND location LIKE ?"
        params.append(f"%{location}%")
    if is_internship is not None:
        sql += " AND is_internship=?"
        params.append(1 if is_internship else 0)
    if work_mode:
        sql += " AND work_mode LIKE ?"
        params.append(f"%{work_mode}%")
    sql += " ORDER BY discovered_at DESC LIMIT 100"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows_to_list(rows)


def get_job_count(is_internship=None):
    conn = get_db()
    if is_internship is None:
        count = conn.execute("SELECT COUNT(*) FROM jobs WHERE is_expired=0").fetchone()[0]
    else:
        count = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE is_internship=? AND is_expired=0",
            (1 if is_internship else 0,)
        ).fetchone()[0]
    conn.close()
    return count


# ─── Saved Jobs helpers ───────────────────────────────────────────────────────

def save_job_for_user(user_id, job_id):
    conn = get_db()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO saved_jobs (user_id, job_id) VALUES (?, ?)",
            (user_id, job_id)
        )
        conn.commit()
        return True, "Job saved."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def unsave_job_for_user(user_id, job_id):
    conn = get_db()
    conn.execute("DELETE FROM saved_jobs WHERE user_id=? AND job_id=?", (user_id, job_id))
    conn.commit()
    conn.close()


def get_saved_jobs(user_id):
    conn = get_db()
    rows = conn.execute("""
        SELECT j.*, sj.saved_at FROM jobs j
        JOIN saved_jobs sj ON j.id = sj.job_id
        WHERE sj.user_id = ? AND j.is_expired=0
        ORDER BY sj.saved_at DESC
    """, (user_id,)).fetchall()
    conn.close()
    return rows_to_list(rows)


def is_job_saved(user_id, job_id):
    conn = get_db()
    row = conn.execute(
        "SELECT 1 FROM saved_jobs WHERE user_id=? AND job_id=?", (user_id, job_id)
    ).fetchone()
    conn.close()
    return row is not None


def get_saved_jobs_count(user_id):
    conn = get_db()
    count = conn.execute(
        "SELECT COUNT(*) FROM saved_jobs WHERE user_id=?", (user_id,)
    ).fetchone()[0]
    conn.close()
    return count


# ─── Applications helpers ─────────────────────────────────────────────────────

def apply_to_job(user_id, job_id, notes=""):
    conn = get_db()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO applications (user_id, job_id, notes) VALUES (?, ?, ?)",
            (user_id, job_id, notes)
        )
        conn.commit()
        return True, "Application tracked."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def get_applications(user_id):
    conn = get_db()
    rows = conn.execute("""
        SELECT j.*, a.status, a.applied_at, a.notes FROM jobs j
        JOIN applications a ON j.id = a.job_id
        WHERE a.user_id = ?
        ORDER BY a.applied_at DESC
    """, (user_id,)).fetchall()
    conn.close()
    return rows_to_list(rows)


def update_application_status(user_id, job_id, status):
    conn = get_db()
    conn.execute(
        "UPDATE applications SET status=? WHERE user_id=? AND job_id=?",
        (status, user_id, job_id)
    )
    conn.commit()
    conn.close()


def get_applications_count(user_id):
    conn = get_db()
    count = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE user_id=?", (user_id,)
    ).fetchone()[0]
    conn.close()
    return count


# ─── Monitoring helpers ───────────────────────────────────────────────────────

def log_monitor_run(search_query, location, jobs_found, new_jobs, status="completed", details=""):
    conn = get_db()
    conn.execute("""
        INSERT INTO monitoring_history (search_query, location, jobs_found, new_jobs, status, details)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (search_query, location, jobs_found, new_jobs, status, details))
    conn.commit()
    conn.close()


def get_monitoring_history(limit=20):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM monitoring_history ORDER BY ran_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return rows_to_list(rows)


def get_recently_added_jobs(limit=10):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM jobs WHERE is_expired=0 ORDER BY discovered_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return rows_to_list(rows)
