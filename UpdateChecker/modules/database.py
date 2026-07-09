import sqlite3
import os
import csv
from datetime import datetime


DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "update_history.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            old_version TEXT,
            new_version TEXT,
            status TEXT NOT NULL,
            restore_point_id TEXT,
            computer_name TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()
    conn.close()


def log_update(name, update_type, old_version, new_version, status, restore_point_id=None, computer_name=None):
    conn = get_connection()
    cursor = conn.cursor()
    timestamp = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO updates (timestamp, name, type, old_version, new_version, status, restore_point_id, computer_name)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (timestamp, name, update_type, old_version, new_version, status, restore_point_id, computer_name))
    conn.commit()
    conn.close()


def get_history(limit=100):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM updates ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def search_history(query):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM updates
        WHERE name LIKE ? OR type LIKE ? OR status LIKE ? OR computer_name LIKE ?
        ORDER BY timestamp DESC
    """, (f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def clear_history():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM updates")
    conn.commit()
    conn.close()


def get_filtered_history(type_filter=None, status_filter=None, computer_filter=None, limit=500):
    conn = get_connection()
    cursor = conn.cursor()
    conditions = []
    params = []
    if type_filter:
        conditions.append("type = ?")
        params.append(type_filter)
    if status_filter:
        conditions.append("status = ?")
        params.append(status_filter)
    if computer_filter:
        conditions.append("computer_name = ?")
        params.append(computer_filter)
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    cursor.execute(f"SELECT * FROM updates WHERE {where_clause} ORDER BY timestamp DESC LIMIT ?", params + [limit])
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_distinct_computers():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT computer_name FROM updates WHERE computer_name IS NOT NULL ORDER BY computer_name")
    rows = cursor.fetchall()
    conn.close()
    return [row["computer_name"] for row in rows]


def export_to_csv(filepath):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM updates ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "Timestamp", "Name", "Type", "Old Version", "New Version", "Status", "Restore Point ID", "Computer Name"])
        for row in rows:
            writer.writerow([row["id"], row["timestamp"], row["name"], row["type"], row["old_version"], row["new_version"], row["status"], row["restore_point_id"], row["computer_name"]])
    return True


def import_from_csv(filepath):
    conn = get_connection()
    cursor = conn.cursor()
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute("""
                INSERT INTO updates (timestamp, name, type, old_version, new_version, status, restore_point_id, computer_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (row["Timestamp"], row["Name"], row["Type"], row["Old Version"], row["New Version"], row["Status"], row["Restore Point ID"], row["Computer Name"]))
    conn.commit()
    conn.close()
    return True


def get_setting(key, default=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key, value):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()


def merge_from_github(other_db_path):
    if not os.path.exists(other_db_path):
        return 0
    conn_local = get_connection()
    cursor_local = conn_local.cursor()
    conn_remote = sqlite3.connect(other_db_path)
    cursor_remote = conn_remote.cursor()
    cursor_remote.execute("SELECT * FROM updates")
    remote_rows = cursor_remote.fetchall()
    merged_count = 0
    for row in remote_rows:
        cursor_local.execute("SELECT COUNT(*) FROM updates WHERE id = ?", (row[0],))
        exists = cursor_local.fetchone()[0] > 0
        if not exists:
            cursor_local.execute("""
                INSERT INTO updates (id, timestamp, name, type, old_version, new_version, status, restore_point_id, computer_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8]))
            merged_count += 1
    conn_local.commit()
    conn_local.close()
    conn_remote.close()
    return merged_count
