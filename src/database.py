import os
import sqlite3
from src.config import APP_DIR

DB_FILE = os.path.join(APP_DIR, "cloned_messages.db")

def init_db():
    """
    Initializes SQLite database schema for tracking replicated messages.

    Returns:
        None
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cloned_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_chat_id INTEGER,
            dest_chat_id INTEGER,
            source_msg_id INTEGER,
            dest_msg_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_chat_id, dest_chat_id, source_msg_id)
        )
    """)
    conn.commit()
    conn.close()

def is_already_cloned(source_chat_id, dest_chat_id, source_msg_id):
    """
    Checks if a source message has already been cloned to destination.

    Parameters:
        source_chat_id (int/str): Source channel ID.
        dest_chat_id (int/str): Destination channel ID.
        source_msg_id (int): Message ID in source channel.

    Returns:
        bool: True if already cloned, False otherwise.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT dest_msg_id FROM cloned_messages
        WHERE source_chat_id = ? AND dest_chat_id = ? AND source_msg_id = ?
    """, (int(source_chat_id), int(dest_chat_id), int(source_msg_id)))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def register_clone(source_chat_id, dest_chat_id, source_msg_id, dest_msg_id):
    """
    Registers a cloned message pair in database.

    Parameters:
        source_chat_id (int/str): Source channel ID.
        dest_chat_id (int/str): Destination channel ID.
        source_msg_id (int): Source message ID.
        dest_msg_id (int): Destination message ID.

    Returns:
        None
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO cloned_messages 
            (source_chat_id, dest_chat_id, source_msg_id, dest_msg_id)
            VALUES (?, ?, ?, ?)
        """, (int(source_chat_id), int(dest_chat_id), int(source_msg_id), int(dest_msg_id)))
        conn.commit()
    except Exception:
        pass
    conn.close()

def get_cloned_message_map(source_chat_id, dest_chat_id):
    """
    Retrieves dictionary mapping source message IDs to destination message IDs.

    Parameters:
        source_chat_id (int/str): Source channel ID.
        dest_chat_id (int/str): Destination channel ID.

    Returns:
        dict: Mapping of {source_msg_id: dest_msg_id}.
    """
    init_db()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT source_msg_id, dest_msg_id FROM cloned_messages
            WHERE source_chat_id = ? AND dest_chat_id = ?
        """, (int(source_chat_id), int(dest_chat_id)))
        rows = cursor.fetchall()
        conn.close()
        return {row[0]: row[1] for row in rows}
    except Exception:
        conn.close()
        return {}

def clear_clone_history(source_chat_id=None, dest_chat_id=None):
    """
    Clears cloned message records from database.

    Parameters:
        source_chat_id (int/str, optional): Source channel ID.
        dest_chat_id (int/str, optional): Destination channel ID.

    Returns:
        None
    """
    init_db()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        if source_chat_id and dest_chat_id:
            cursor.execute("""
                DELETE FROM cloned_messages
                WHERE source_chat_id = ? AND dest_chat_id = ?
            """, (int(source_chat_id), int(dest_chat_id)))
        else:
            cursor.execute("DELETE FROM cloned_messages")
        conn.commit()
    except Exception as e:
        print(f"Error clearing clone history: {e}")
    conn.close()
